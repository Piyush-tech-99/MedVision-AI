
from functools import lru_cache
from pathlib import Path
import uuid

import numpy as np
import nibabel as nib
import tensorflow as tf
from scipy.ndimage import zoom


# =========================================================
# CONFIGURATION
# =========================================================

IMG_SIZE = 128
STROKE_THRESHOLD = 0.5

BACKEND_ROOT = Path(__file__).resolve().parents[2]

STROKE_MODEL_PATH = (
    BACKEND_ROOT / "models" / "stroke" / "stroke_unet_best.keras"
)

STROKE_RESULTS_DIR = (
    BACKEND_ROOT / "generated" / "stroke_results"
)


# =========================================================
# MRI PREPROCESSING
# =========================================================

def normalize_volume(volume):
    volume = np.nan_to_num(
        volume.astype(np.float32),
        nan=0.0,
        posinf=0.0,
        neginf=0.0
    )

    valid = volume != 0

    if not np.any(valid):
        return volume

    low, high = np.percentile(volume[valid], [1, 99])

    if high <= low:
        return np.zeros_like(volume, dtype=np.float32)

    normalized = np.zeros_like(volume, dtype=np.float32)

    normalized[valid] = np.clip(
        (volume[valid] - low) / (high - low),
        0,
        1
    )

    return normalized


def resize_image(image):
    resized = zoom(
        image,
        (
            IMG_SIZE / image.shape[0],
            IMG_SIZE / image.shape[1]
        ),
        order=1
    ).astype(np.float32)

    if resized.shape != (IMG_SIZE, IMG_SIZE):
        raise ValueError(
            f"Unexpected resized image shape: {resized.shape}"
        )

    return resized


def resize_mask_to_original(mask, original_shape):
    resized = zoom(
        mask.astype(np.uint8),
        (
            original_shape[0] / mask.shape[0],
            original_shape[1] / mask.shape[1]
        ),
        order=0
    )

    if resized.shape != original_shape:
        raise ValueError(
            f"Unexpected mask shape: {resized.shape}"
        )

    return (resized > 0).astype(np.uint8)


# =========================================================
# LOAD TRAINED MODEL
# =========================================================

@lru_cache(maxsize=1)
def load_stroke_model():

    if not STROKE_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Stroke model not found: {STROKE_MODEL_PATH}"
        )

    model = tf.keras.models.load_model(
        str(STROKE_MODEL_PATH),
        compile=False
    )

    if tuple(model.input_shape[1:]) != (128, 128, 2):
        raise ValueError(
            f"Unexpected model input shape: {model.input_shape}"
        )

    if tuple(model.output_shape[1:]) != (128, 128, 1):
        raise ValueError(
            f"Unexpected model output shape: {model.output_shape}"
        )

    return model


# =========================================================
# MODEL STATUS
# =========================================================

def stroke_model_status():

    if not STROKE_MODEL_PATH.exists():
        return {
            "connected": False,
            "model_name": "MedVision AI Stroke U-Net",
            "message": "Stroke model file not found."
        }

    try:
        model = load_stroke_model()

        return {
            "connected": True,
            "model_name": "MedVision AI Stroke U-Net",
            "architecture": "U-Net",
            "input_shape": list(model.input_shape),
            "output_shape": list(model.output_shape),
            "modality": "Brain MRI",
            "input_modalities": ["DWI", "ADC"],
            "message": "Stroke model loaded successfully."
        }

    except Exception as exc:
        return {
            "connected": False,
            "model_name": "MedVision AI Stroke U-Net",
            "message": str(exc)
        }


# =========================================================
# LOAD MRI VOLUMES
# =========================================================

def load_mri_volumes(dwi_path, adc_path):

    dwi_img = nib.load(str(dwi_path))
    adc_img = nib.load(str(adc_path))

    if len(dwi_img.shape) != 3 or len(adc_img.shape) != 3:
        raise ValueError(
            "Only 3D DWI and ADC MRI volumes are supported."
        )

    if dwi_img.shape != adc_img.shape:
        raise ValueError(
            "DWI and ADC volumes must have identical dimensions."
        )

    if not np.allclose(
        dwi_img.affine,
        adc_img.affine,
        atol=1e-4
    ):
        raise ValueError(
            "DWI and ADC spatial orientations do not match."
        )

    dwi = normalize_volume(
        dwi_img.get_fdata(dtype=np.float32)
    )

    adc = normalize_volume(
        adc_img.get_fdata(dtype=np.float32)
    )

    return dwi, adc, dwi_img


# =========================================================
# SAVE SEGMENTATION AS NIFTI
# =========================================================

def save_segmentation_mask(predicted_volume, reference_img):

    STROKE_RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    filename = (
        f"stroke_segmentation_{uuid.uuid4().hex}.nii.gz"
    )

    output_path = STROKE_RESULTS_DIR / filename

    header = reference_img.header.copy()
    header.set_data_dtype(np.uint8)

    mask_img = nib.Nifti1Image(
        predicted_volume.astype(np.uint8),
        reference_img.affine,
        header=header
    )

    nib.save(
        mask_img,
        str(output_path)
    )

    return filename


# =========================================================
# STROKE MRI SEGMENTATION
# =========================================================

def predict_stroke(dwi_path, adc_path):

    model = load_stroke_model()

    dwi, adc, reference_img = load_mri_volumes(
        dwi_path,
        adc_path
    )

    original_shape = dwi.shape

    if not np.any(dwi) or not np.any(adc):
        raise ValueError(
            "DWI or ADC volume contains no usable nonzero data."
        )

    predicted_volume = np.zeros(
        original_shape,
        dtype=np.uint8
    )

    slice_results = []

    processed_slices = 0
    positive_slices = 0
    total_lesion_pixels = 0

    for z in range(original_shape[2]):

        dwi_slice = dwi[:, :, z]
        adc_slice = adc[:, :, z]

        if (
            not np.any(dwi_slice)
            and not np.any(adc_slice)
        ):
            continue

        dwi_resized = resize_image(dwi_slice)
        adc_resized = resize_image(adc_slice)

        model_input = np.stack(
            [dwi_resized, adc_resized],
            axis=-1
        )

        model_input = np.expand_dims(
            model_input,
            axis=0
        )

        probabilities = model.predict(
            model_input,
            verbose=0
        )[0, :, :, 0]

        predicted_mask = (
            probabilities >= STROKE_THRESHOLD
        ).astype(np.uint8)

        original_mask = resize_mask_to_original(
            predicted_mask,
            original_shape[:2]
        )

        predicted_volume[:, :, z] = original_mask

        lesion_pixels = int(np.sum(original_mask))

        processed_slices += 1
        total_lesion_pixels += lesion_pixels

        if lesion_pixels > 0:
            positive_slices += 1

        slice_results.append({
            "slice_index": int(z),
            "lesion_pixels": lesion_pixels,
            "lesion_detected_by_model": lesion_pixels > 0
        })

    total_voxels = int(np.prod(original_shape))

    lesion_percentage = (
        (total_lesion_pixels / total_voxels) * 100
        if total_voxels else 0.0
    )

    segmentation_filename = save_segmentation_mask(
        predicted_volume,
        reference_img
    )

    return {
        "status": "PREDICTION_GENERATED",
        "model_name": "MedVision AI Stroke U-Net",
        "architecture": "U-Net",
        "modality": "Brain MRI",
        "input_modalities": ["DWI", "ADC"],
        "original_volume_shape": list(original_shape),
        "processed_slices": processed_slices,
        "slices_with_predicted_lesions": positive_slices,
        "total_lesion_pixels": total_lesion_pixels,
        "lesion_pixel_percentage": round(
            lesion_percentage,
            4
        ),
        "threshold": STROKE_THRESHOLD,
        "slice_results": slice_results,
        "segmentation_file": segmentation_filename,
        "segmentation_saved": True,
        "note": (
            "Research prototype output. "
            "Predicted regions are not a clinical diagnosis."
        )
    }
