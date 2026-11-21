
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
    HTTPException,
    Depends
)

from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import Analysis, AnalysisResult, User
from app.security import get_current_user

from app.services.image import inspect_image

from app.services.prediction import (
    predict_image,
    model_status,
    _load_model
)

from app.services.gradcam import generate_gradcam

from app.services.stroke import (
    predict_stroke,
    stroke_model_status
)


logger = logging.getLogger(__name__)

router = APIRouter()


# =========================================================
# CONFIGURATION
# =========================================================

ALLOWED = {
    "image/jpeg",
    "image/png",
    "image/webp"
}

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
    user_id,
    modality,
    task,
    filename,
    status,
    result
):
    """
    Save an analysis against the authenticated user.

    Generate a unique analysis code using the database ID.
    """

    db = SessionLocal()

    try:

        user = db.query(User).filter(
            User.id == user_id
        ).first()

        if not user:
            raise ValueError(
                "Authenticated user was not found."
            )

        analysis = Analysis(
            user_id=user.id,
            modality=modality,
            task=task,
            filename=(filename or "Unknown")[:255],
            status=status
        )

        db.add(analysis)
        db.flush()

        current_year = datetime.now(
            timezone.utc
        ).year

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

            confidence_value = result.get("confidence")

            if confidence_value is None:
                confidence_value = result.get(
                    "confidence_score"
                )

            if confidence_value is not None:

                try:
                    confidence = float(
                        str(confidence_value).replace("%", "").strip()
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

            result_json=json.dumps(
                result,
                default=str
            )
        )

        db.add(stored_result)

        db.commit()
        db.refresh(analysis)

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
# AUTHENTICATED ANALYSIS HISTORY
#
# Patient: Only their own analyses
# Doctor: All patients' analyses
# =========================================================

@router.get("/analyses")
def get_analyses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if current_user.role == "patient":

        query = db.query(Analysis).filter(
            Analysis.user_id == current_user.id
        )

    elif current_user.role == "doctor":

        query = db.query(Analysis)

    else:

        raise HTTPException(
            status_code=403,
            detail="You do not have permission to view analysis history."
        )

    analyses = query.order_by(
        Analysis.created_at.desc()
    ).all()

    history = []

    for analysis in analyses:

        stored_result = analysis.result

        result_data = {}

        if (
            stored_result
            and stored_result.result_json
        ):

            try:

                parsed = json.loads(
                    stored_result.result_json
                )

                if isinstance(parsed, dict):
                    result_data = parsed

            except (json.JSONDecodeError, TypeError):

                result_data = {}

        history.append({

            "id": analysis.id,

            "analysis_id": analysis.id,

            "analysis_code": analysis.analysis_code,

            "user_id": analysis.user_id,

            "modality": analysis.modality,

            "task": analysis.task,

            "filename": analysis.filename,

            "status": analysis.status,

            "created_at": (
                analysis.created_at.isoformat()
                if analysis.created_at
                else None
            ),

            "prediction": (
                stored_result.prediction
                if stored_result
                else None
            ),

            "confidence": (
                stored_result.confidence
                if stored_result
                else None
            ),

            "result": result_data

        })

    return {
        "user_id": current_user.id,
        "role": current_user.role,
        "total": len(history),
        "analyses": history
    }


# =========================================================
# IMAGE ANALYSIS
# Pneumonia, Tuberculosis, Brain Tumour
# =========================================================

@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    modality: str = Form(...),
    task: str = Form(...),
    current_user: User = Depends(get_current_user)
):

    if current_user.role not in ("patient", "doctor"):

        raise HTTPException(
            status_code=403,
            detail="You do not have permission to perform analysis."
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

    try:

        result = predict_image(
            content,
            modality,
            task
        )

        if not isinstance(result, dict):

            raise ValueError(
                "Invalid prediction response."
            )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception:

        logger.exception(
            "Image prediction failed."
        )

        raise HTTPException(
            status_code=500,
            detail="Image analysis failed."
        )

    gradcam_overlay = None

    if result.get("status") == "PREDICTION_GENERATED":

        try:

            model = _load_model(
                result["model_path"]
            )

            gradcam_overlay = generate_gradcam(
                model,
                content
            )

        except Exception as exc:

            logger.exception(
                "Grad-CAM generation failed."
            )

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
        user_id=current_user.id,
        modality=modality,
        task=task,
        filename=file.filename,
        status=response_status,
        result=result
    )

    if not saved_ids:

        raise HTTPException(
            status_code=500,
            detail="Analysis was generated but could not be saved."
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

        "user_id": saved_ids["user_id"],

        "analysis_id": saved_ids["analysis_id"],

        "analysis_code": saved_ids["analysis_code"]

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


async def save_mri_upload(
    upload: UploadFile,
    destination: str
):

    if not validate_nifti_filename(upload.filename):

        raise HTTPException(
            status_code=415,
            detail="Only .nii and .nii.gz MRI files are accepted."
        )

    total_size = 0

    try:

        with open(destination, "wb") as output:

            while True:

                chunk = await upload.read(
                    1024 * 1024
                )

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
    current_user: User = Depends(get_current_user)
):

    if current_user.role not in ("patient", "doctor"):

        raise HTTPException(
            status_code=403,
            detail="You do not have permission to perform analysis."
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

        if not isinstance(result, dict):

            raise ValueError(
                "Invalid stroke prediction response."
            )

        segmentation_filename = result.get(
            "segmentation_file"
        )

        response_status = "ANALYSIS_COMPLETED"

        saved_ids = save_analysis_to_database(
            user_id=current_user.id,
            modality="Brain MRI",
            task="Stroke screening",
            filename=(
                f"{dwi_file.filename} + {adc_file.filename}"
            ),
            status=response_status,
            result=result
        )

        if not saved_ids:

            raise HTTPException(
                status_code=500,
                detail="Stroke analysis could not be saved."
            )

        download_url = None

        if segmentation_filename:

            download_url = (
                f"/api/stroke-result/"
                f"{saved_ids['analysis_id']}/"
                f"{segmentation_filename}"
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

            "user_id": saved_ids["user_id"],

            "analysis_id": saved_ids["analysis_id"],

            "analysis_code": saved_ids["analysis_code"]

        }

    except HTTPException:

        raise

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception:

        logger.exception(
            "Stroke analysis failed."
        )

        raise HTTPException(
            status_code=500,
            detail="Stroke analysis failed."
        )

    finally:

        for path in (dwi_path, adc_path):

            if path and os.path.exists(path):
                os.remove(path)

        await dwi_file.close()
        await adc_file.close()


# =========================================================
# SECURE STROKE SEGMENTATION DOWNLOAD
# =========================================================

@router.get("/stroke-result/{analysis_id}/{filename}")
def download_stroke_result(
    analysis_id: int,
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if (
        not filename.startswith("stroke_segmentation_")
        or not filename.endswith(".nii.gz")
        or Path(filename).name != filename
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid segmentation filename."
        )

    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id
    ).first()

    if not analysis:

        raise HTTPException(
            status_code=404,
            detail="Analysis not found."
        )

    if (
        current_user.role == "patient"
        and analysis.user_id != current_user.id
    ):

        raise HTTPException(
            status_code=403,
            detail="You cannot access another patient's segmentation."
        )

    if current_user.role not in ("patient", "doctor"):

        raise HTTPException(
            status_code=403,
            detail="You do not have permission to download this file."
        )

    if (
        analysis.modality != "Brain MRI"
        or analysis.task != "Stroke screening"
    ):

        raise HTTPException(
            status_code=400,
            detail="This analysis is not a stroke MRI analysis."
        )

    stored_result = db.query(AnalysisResult).filter(
        AnalysisResult.analysis_id == analysis.id
    ).first()

    if (
        not stored_result
        or not stored_result.result_json
    ):

        raise HTTPException(
            status_code=404,
            detail="Segmentation record not found."
        )

    try:

        result_data = json.loads(
            stored_result.result_json
        )

    except (ValueError, TypeError):

        raise HTTPException(
            status_code=500,
            detail="Stored segmentation information is invalid."
        )

    if not isinstance(result_data, dict):

        raise HTTPException(
            status_code=500,
            detail="Stored segmentation information is invalid."
        )

    if result_data.get("segmentation_file") != filename:

        raise HTTPException(
            status_code=403,
            detail="This segmentation does not belong to this analysis."
        )

    results_root = STROKE_RESULTS_DIR.resolve()

    file_path = (
        results_root / filename
    ).resolve()

    if file_path.parent != results_root:

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
