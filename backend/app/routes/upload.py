import logging
import os
import tempfile
from pathlib import Path

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException
)
from fastapi.responses import FileResponse

from app.services.image import inspect_image
from app.services.prediction import predict_image, model_status, _load_model
from app.services.gradcam import generate_gradcam
from app.services.stroke import predict_stroke, stroke_model_status


logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 15 * 1024 * 1024
MAX_MRI_BYTES = 200 * 1024 * 1024

BACKEND_ROOT = Path(__file__).resolve().parents[2]

STROKE_RESULTS_DIR = (
    BACKEND_ROOT / "generated" / "stroke_results"
)


# =========================================================
# MODEL STATUS
# =========================================================

@router.get("/model-status")
def get_model_status(
    modality: str = "Chest X-ray",
    task: str = "Pneumonia screening"
):
    modality = modality.strip()
    task = task.strip()

    if (
        modality.casefold() == "brain mri"
        and task.casefold() == "stroke screening"
    ):
        return stroke_model_status()

    return model_status(modality, task)


# =========================================================
# IMAGE ANALYSIS
# Pneumonia, Tuberculosis, Brain Tumour
# =========================================================

@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    modality: str = Form(...),
    task: str = Form(...)
):

    if file.content_type not in ALLOWED:
        raise HTTPException(
            status_code=415,
            detail="Only JPG, PNG and WEBP images are accepted."
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty."
        )

    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Maximum upload size is 15 MB."
        )

    try:
        image_info = inspect_image(content)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    result = predict_image(
        content,
        modality,
        task
    )

    gradcam_overlay = None

    if result.get("status") == "PREDICTION_GENERATED":
        try:
            model = _load_model(result["model_path"])
            gradcam_overlay = generate_gradcam(model, content)
        except Exception as exc:
            logger.exception("Grad-CAM generation failed")
            result["gradcam_note"] = f"Prediction generated, but Grad-CAM failed: {exc}"

    connected = (
        result.get("status") == "PREDICTION_GENERATED"
    )

    return {
        "status": (
            "ANALYSIS_COMPLETED"
            if connected
            else result.get(
                "status",
                "MODEL_NOT_CONNECTED"
            )
        ),
        "mode": (
            "model"
            if connected
            else "validation-only"
        ),
        "message": result.get(
            "note",
            "No trained model was called."
        ),
        "task": task,
        "modality": modality,
        "image": image_info,
        "result": result,
        "gradcam_overlay": gradcam_overlay
    }


# =========================================================
# STROKE MRI UPLOAD VALIDATION
# =========================================================

def validate_nifti_filename(filename):

    if not filename:
        return False

    lower_name = filename.lower()

    return (
        lower_name.endswith(".nii")
        or lower_name.endswith(".nii.gz")
    )


async def save_mri_upload(upload: UploadFile, destination: str):

    if not validate_nifti_filename(upload.filename):
        raise HTTPException(
            status_code=415,
            detail="Only .nii and .nii.gz MRI files are accepted."
        )

    total_size = 0

    try:
        with open(destination, "wb") as output:

            while True:

                chunk = await upload.read(1024 * 1024)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_MRI_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Each MRI file must be smaller than 200 MB."
                    )

                output.write(chunk)

    except Exception:
        if os.path.exists(destination):
            os.remove(destination)
        raise

    if total_size == 0:
        raise HTTPException(
            status_code=400,
            detail="An uploaded MRI file is empty."
        )


# =========================================================
# STROKE MRI ANALYSIS
# Requires DWI + ADC NIfTI files
# =========================================================

@router.post("/analyze-stroke")
async def analyze_stroke(
    dwi_file: UploadFile = File(...),
    adc_file: UploadFile = File(...)
):

    if not validate_nifti_filename(dwi_file.filename):
        raise HTTPException(
            status_code=415,
            detail="DWI must be a .nii or .nii.gz file."
        )

    if not validate_nifti_filename(adc_file.filename):
        raise HTTPException(
            status_code=415,
            detail="ADC must be a .nii or .nii.gz file."
        )

    dwi_suffix = (
        ".nii.gz"
        if dwi_file.filename.lower().endswith(".nii.gz")
        else ".nii"
    )

    adc_suffix = (
        ".nii.gz"
        if adc_file.filename.lower().endswith(".nii.gz")
        else ".nii"
    )

    dwi_path = None
    adc_path = None

    try:

        with tempfile.NamedTemporaryFile(
            suffix=dwi_suffix,
            delete=False
        ) as dwi_temp:
            dwi_path = dwi_temp.name

        with tempfile.NamedTemporaryFile(
            suffix=adc_suffix,
            delete=False
        ) as adc_temp:
            adc_path = adc_temp.name

        await save_mri_upload(
            dwi_file,
            dwi_path
        )

        await save_mri_upload(
            adc_file,
            adc_path
        )

        result = predict_stroke(
            dwi_path,
            adc_path
        )

        segmentation_filename = result.get(
            "segmentation_file"
        )

        download_url = None

        if segmentation_filename:
            download_url = (
                f"/api/stroke-result/{segmentation_filename}"
            )

        return {
            "status": "ANALYSIS_COMPLETED",
            "mode": "model",
            "modality": "Brain MRI",
            "task": "Stroke screening",
            "input_files": {
                "dwi": dwi_file.filename,
                "adc": adc_file.filename
            },
            "result": result,
            "segmentation_download_url": download_url,
            "gradcam_overlay": None,
            "message": (
                "Stroke segmentation completed. "
                "This output is for research purposes "
                "and is not a clinical diagnosis."
            )
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Stroke analysis failed: {str(exc)}"
        )

    finally:

        for path in (dwi_path, adc_path):

            if path and os.path.exists(path):
                os.remove(path)

        await dwi_file.close()
        await adc_file.close()


# =========================================================
# DOWNLOAD STROKE SEGMENTATION
# =========================================================

@router.get("/stroke-result/{filename}")
def download_stroke_result(filename: str):

    if (
        not filename.startswith("stroke_segmentation_")
        or not filename.endswith(".nii.gz")
        or Path(filename).name != filename
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid segmentation filename."
        )

    file_path = (
        STROKE_RESULTS_DIR / filename
    ).resolve()

    if file_path.parent != STROKE_RESULTS_DIR.resolve():
        raise HTTPException(
            status_code=400,
            detail="Invalid file path."
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Stroke segmentation file not found."
        )

    return FileResponse(
        path=str(file_path),
        media_type="application/gzip",
        filename=filename
    )