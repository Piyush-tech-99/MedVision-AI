
import json
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Analysis, User
from app.security import get_current_user
from app.services.report import create_demo_pdf


router = APIRouter()


class ReportRequest(BaseModel):
    analysis_id: int = Field(gt=0)


@router.post("/demo")
def demo_report(
    payload: ReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Find the requested analysis.
    analysis = db.query(Analysis).filter(
        Analysis.id == payload.analysis_id
    ).first()

    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found."
        )

    # Patients can access only their own analyses.
    # Doctors can access all analyses.
    if current_user.role == "patient":
        if analysis.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You cannot access this patient's report."
            )

    elif current_user.role != "doctor":
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to generate reports."
        )

    # Retrieve the actual stored result.
    analysis_result = analysis.result

    if analysis_result is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis result is not available."
        )

    result_data = {}

    if analysis_result.result_json:
        try:
            result_data = json.loads(
                analysis_result.result_json
            )
        except (json.JSONDecodeError, TypeError):
            result_data = {}

    if not isinstance(result_data, dict):
        result_data = {}

    # Preserve the existing PDF generation service.
    report_data = {
        "modality": analysis.modality,
        "task": analysis.task,
        "filename": analysis.filename,
        "analysis_code": analysis.analysis_code,
        "status": analysis.status,
        "prediction": analysis_result.prediction,
        "confidence": analysis_result.confidence,
        "result": result_data
    }

    try:
        pdf_bytes = create_demo_pdf(report_data)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Could not generate the PDF report."
        )

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'attachment; filename="MedVisionAI-demo-report.pdf"'
            )
        }
    )
