
import logging
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException
)
from fastapi.responses import FileResponse

from app.database import SessionLocal
from app.models import Analysis, AnalysisResult, User

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
# DATABASE PERSISTENCE
# =========================================================

def save_analysis_to_database(
    modality,
    task,
    filename,
    status,
    result,
    guest_token
):
    """
    Identify or create a guest user and associate
    every analysis with that user in PostgreSQL.

    Generate a unique public Analysis Code using
    the database analysis ID.
    """

    db = SessionLocal()

    try:
        user = db.query(User).filter(
            User.guest_token == guest_token
        ).first()

        if not user:
            user = User(
                guest_token=guest_token,
                name="Guest User",
                email=f"{guest_token}@guest.medvision.local",
                hashed_password="guest-account-no-login",
                role="guest"
            )

            db.add(user)
            db.flush()

        analysis = Analysis(
            user_id=user.id,
            modality=modality,
            task=task,
            filename=(filename or "Unknown")[:255],
            status=status
        )

        db.add(analysis)
        db.flush()

        # Generate a readable and unique Analysis Code.
        current_year = datetime.now(timezone.utc).year

        analysis.analysis_code = (
            f"MVA-{current_year}-{analysis.id:06d}"
        )

        prediction = None
        confidence = None

        if isinstance(result, dict):
            prediction = (
                result.get("prediction")
                or result.get("predicted_class")
                or result.get("class_name")
            )

            confidence_value = (
                result.get("confidence")
                or result.get("confidence_score")
            )

            if confidence_value is not None:
                try:
                    confidence = float(
                        str(confidence_value).replace("%", "")
                    )
                except (ValueError, TypeError):
                    confidence = None

        stored_result = AnalysisResult(
            analysis_id=analysis.id,
            prediction=(
                str(prediction)[:150]
                if prediction is not None
                else None
            ),
            confidence=confidence,
            result_json=json.dumps(result, default=str)
        )

        db.add(stored_result)
        db.commit()

        saved_ids = {
            "user_id": user.id,
            "analysis_id": analysis.id,
            "analysis_code": analysis.analysis_code
        }

        logger.info(
            "Analysis %s (%s) saved for user %s",
            analysis.id,
            analysis.analysis_code,
            user.id
        )

        return saved_ids

    except Exception:
        db.rollback()
        logger.exception(
            "Could not save analysis to PostgreSQL"
        )
        return None

    finally:
        db.close()


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
    task: str = Form(...),
    guest_token: str = Form(...)
):

    if not guest_token.strip() or len(guest_token) > 100:
        raise HTTPException(
            status_code=400,
            detail="Invalid guest identifier."
        )

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
            result["gradcam_note"] = (
                f"Prediction generated, but Grad-CAM failed: {exc}"
            )

    connected = (
        result.get("status") == "PREDICTION_GENERATED"
    )

    response_status = (
        "ANALYSIS_COMPLETED"
        if connected
        else result.get(
            "status",
            "MODEL_NOT_CONNECTED"
        )
    )

    saved_ids = save_analysis_to_database(
        modality=modality,
        task=task,
        filename=file.filename,
        status=response_status,
        result=result,
        guest_token=guest_token.strip()
    )

    return {
        "status": response_status,
        "mode": (
            "model"
            if connected
            else "validation-only"
        ),
        "message": result.get(
            "note",
            "No trained medical imaging model was called."
        ),
        "task": task,
        "modality": modality,
        "image": image_info,
        "result": result,
        "gradcam_overlay": gradcam_overlay,
        "user_id": saved_ids["user_id"] if saved_ids else None,
        "analysis_id": saved_ids["analysis_id"] if saved_ids else None,
        "analysis_code": saved_ids["analysis_code"] if saved_ids else None
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
    adc_file: UploadFile = File(...),
    guest_token: str = Form(...)
):

    if not guest_token.strip() or len(guest_token) > 100:
        raise HTTPException(
            status_code=400,
            detail="Invalid guest identifier."
        )

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

        response_status = "ANALYSIS_COMPLETED"

        saved_ids = save_analysis_to_database(
            modality="Brain MRI",
            task="Stroke screening",
            filename=(
                f"{dwi_file.filename} + {adc_file.filename}"
            ),
            status=response_status,
            result=result,
            guest_token=guest_token.strip()
        )

        return {
            "status": response_status,
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
            ),
            "user_id": saved_ids["user_id"] if saved_ids else None,
            "analysis_id": saved_ids["analysis_id"] if saved_ids else None,
            "analysis_code": saved_ids["analysis_code"] if saved_ids else None
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
