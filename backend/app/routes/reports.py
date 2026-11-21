
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from io import BytesIO

from app.services.report import create_demo_pdf

router = APIRouter()


class ReportRequest(BaseModel):
    modality: str
    task: str
    filename: str | None = None
    analysis_code: str | None = None
    result: dict


@router.post("/demo")
def demo_report(payload: ReportRequest):
    pdf_bytes = create_demo_pdf(payload.model_dump())

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="MedVisionAI-demo-report.pdf"'
        }
    )
