
from io import BytesIO
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether
)


NAVY = colors.HexColor("#102B49")
TEAL = colors.HexColor("#197D99")
MUTED = colors.HexColor("#66788D")
PALE = colors.HexColor("#EFF6F8")
BORDER = colors.HexColor("#DCE6ED")


def _safe_text(value, fallback="Not available"):
    if value is None or value == "":
        return fallback

    return str(value)


def _percentage(value):
    if value is None:
        return "Not available"

    try:
        number = float(value)

        if 0 <= number <= 1:
            number *= 100

        return f"{number:.2f}%"

    except (ValueError, TypeError):
        return _safe_text(value)


def _make_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=21,
        leading=25,
        textColor=colors.white,
        alignment=TA_LEFT,
        spaceAfter=5
    ))

    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#D7EAF0")
    ))

    styles.add(ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=NAVY,
        spaceBefore=12,
        spaceAfter=8
    ))

    styles.add(ParagraphStyle(
        name="BodyTextCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=13,
        textColor=NAVY,
        spaceAfter=5
    ))

    styles.add(ParagraphStyle(
        name="SmallMuted",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=11,
        textColor=MUTED
    ))

    styles.add(ParagraphStyle(
        name="TableLabel",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=MUTED
    ))

    styles.add(ParagraphStyle(
        name="TableValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=NAVY,
        wordWrap="CJK"
    ))

    styles.add(ParagraphStyle(
        name="PredictionValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=TEAL
    ))

    return styles


def _paragraph(value, style):
    escaped = (
        _safe_text(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    return Paragraph(escaped, style)


def _make_table(rows, styles, widths=None):
    formatted_rows = []

    for label, value in rows:
        formatted_rows.append([
            _paragraph(label, styles["TableLabel"]),
            _paragraph(value, styles["TableValue"])
        ])

    table = Table(
        formatted_rows,
        colWidths=widths,
        repeatRows=0,
        hAlign="LEFT"
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("BACKGROUND", (0, 0), (0, -1), PALE)
    ]))

    return table


def _header_footer(canvas, doc):
    canvas.saveState()

    width, height = A4

    canvas.setFillColor(NAVY)
    canvas.roundRect(
        35,
        height - 135,
        width - 70,
        102,
        10,
        fill=1,
        stroke=0
    )

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 21)
    canvas.drawString(52, height - 75, "MedVision AI")

    canvas.setFillColor(colors.HexColor("#D7EAF0"))
    canvas.setFont("Helvetica", 9)
    canvas.drawString(
        52,
        height - 96,
        "Medical Imaging Analysis - Analysis Report"
    )

    canvas.setFillColor(colors.HexColor("#B8DDE5"))
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(
        52,
        height - 117,
        "ACADEMIC PROTOTYPE  |  NOT FOR CLINICAL USE"
    )

    canvas.setStrokeColor(BORDER)
    canvas.line(52, 43, width - 52, 43)

    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(
        52,
        30,
        "MedVision AI - Academic prototype - Not for clinical use"
    )

    canvas.drawRightString(
        width - 52,
        30,
        f"Page {doc.page}"
    )

    canvas.restoreState()


def create_demo_pdf(payload: dict) -> bytes:
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=52,
        leftMargin=52,
        topMargin=155,
        bottomMargin=58,
        title="MedVision AI - Analysis Report",
        author="MedVision AI"
    )

    styles = _make_styles()
    story = []

    result = payload.get("result")

    if not isinstance(result, dict):
        result = {}

    prediction = (
        payload.get("prediction")
        or result.get("prediction")
        or result.get("predicted_class")
        or result.get("class_name")
    )

    confidence = payload.get("confidence")

    if confidence is None:
        confidence = result.get("confidence")
        if confidence is None:
            confidence = result.get("confidence_score")

    result_status = result.get("status", "UNKNOWN")
    model_name = result.get("model_name", "Not available")

    # 1. Session details

    story.append(Paragraph("1. Session details", styles["SectionHeading"]))

    details = [
        (
            "Report generated",
            datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
        ),
        ("Analysis ID", _safe_text(payload.get("analysis_code"))),
        ("Imaging modality", _safe_text(payload.get("modality"))),
        ("Analysis task", _safe_text(payload.get("task"))),
        ("Uploaded filename", _safe_text(payload.get("filename"))),
        ("Processing status", _safe_text(payload.get("status"))),
        ("Model execution status", _safe_text(result_status))
    ]

    story.append(_make_table(details, styles, [135, 355]))
    story.append(Spacer(1, 10))

    # 2. Actual model output

    story.append(
        Paragraph("2. Actual model analysis output", styles["SectionHeading"])
    )

    if result_status == "PREDICTION_GENERATED":

        if prediction is not None:
            story.append(
                Paragraph("Model prediction", styles["BodyTextCustom"])
            )
            story.append(
                Paragraph(
                    _safe_text(prediction),
                    styles["PredictionValue"]
                )
            )
            story.append(Spacer(1, 6))

        if confidence is not None:
            story.append(_make_table(
                [("Prediction confidence", _percentage(confidence))],
                styles,
                [135, 355]
            ))
            story.append(Spacer(1, 8))

        probabilities = result.get("class_probabilities")

        if isinstance(probabilities, dict) and probabilities:
            story.append(
                Paragraph(
                    "Class-wise probabilities",
                    styles["BodyTextCustom"]
                )
            )

            probability_rows = [
                (str(class_name), _percentage(probability))
                for class_name, probability in probabilities.items()
            ]

            story.append(
                _make_table(probability_rows, styles, [245, 245])
            )
            story.append(Spacer(1, 8))

        # Stroke segmentation results

        if "processed_slices" in result:
            story.append(
                Paragraph(
                    "Stroke segmentation statistics",
                    styles["BodyTextCustom"]
                )
            )

            stroke_rows = [
                (
                    "Model architecture",
                    _safe_text(result.get("architecture"))
                ),
                (
                    "Input modalities",
                    ", ".join(result.get("input_modalities", []))
                ),
                (
                    "Original volume dimensions",
                    str(result.get("original_volume_shape", "Not available"))
                ),
                (
                    "Processed slices",
                    str(result.get("processed_slices"))
                ),
                (
                    "Slices with predicted regions",
                    str(result.get("slices_with_predicted_lesions"))
                ),
                (
                    "Total predicted lesion pixels",
                    str(result.get("total_lesion_pixels"))
                ),
                (
                    "Predicted lesion pixel percentage",
                    f"{result.get('lesion_pixel_percentage', 'Not available')}%"
                ),
                (
                    "Segmentation threshold",
                    str(result.get("threshold", "Not available"))
                ),
                (
                    "Segmentation file",
                    _safe_text(result.get("segmentation_file"))
                ),
                (
                    "Segmentation saved",
                    str(result.get("segmentation_saved", False))
                )
            ]

            story.append(
                _make_table(stroke_rows, styles, [190, 300])
            )
            story.append(Spacer(1, 8))

        story.append(
            Paragraph(
                f"Model used: {_safe_text(model_name)}",
                styles["SmallMuted"]
            )
        )

    elif result_status == "MODEL_NOT_CONNECTED":
        story.append(
            Paragraph(
                "No prediction was generated because the trained model "
                "was not connected or available for this analysis.",
                styles["BodyTextCustom"]
            )
        )

    elif result_status == "PREDICTION_ERROR":
        story.append(
            Paragraph(
                "The prediction process failed. No valid model prediction "
                "is available for this analysis.",
                styles["BodyTextCustom"]
            )
        )

    else:
        story.append(
            Paragraph(
                "A completed model prediction is not available in the "
                "stored analysis result.",
                styles["BodyTextCustom"]
            )
        )

    # 3. Explainability

    story.append(
        Paragraph(
            "3. Explainability and additional outputs",
            styles["SectionHeading"]
        )
    )

    gradcam_note = result.get("gradcam_note")

    if gradcam_note:
        story.append(
            Paragraph(
                f"Grad-CAM status: {gradcam_note}",
                styles["BodyTextCustom"]
            )
        )
    else:
        story.append(
            Paragraph(
                "A Grad-CAM overlay was not included in the stored analysis "
                "result. Therefore, this PDF cannot confirm whether a "
                "heatmap was generated for this analysis.",
                styles["BodyTextCustom"]
            )
        )

    if result.get("note"):
        story.append(
            Paragraph(
                f"Model note: {result.get('note')}",
                styles["SmallMuted"]
            )
        )

    story.append(Spacer(1, 8))

    # 4. Safety and limitations

    story.append(
        Paragraph(
            "4. Safety and limitations",
            styles["SectionHeading"]
        )
    )

    safety_text = [
        "This document is generated by an academic medical imaging "
        "software prototype.",
        "Model predictions and segmentation outputs are research outputs, "
        "not confirmed medical diagnoses.",
        "Confidence scores and predicted regions do not establish the "
        "presence, absence or severity of a disease.",
        "Do not use this report to make treatment, medication or triage "
        "decisions.",
        "A qualified healthcare professional must interpret medical images "
        "alongside clinical findings and patient history."
    ]

    safety_rows = [
        [Paragraph(
            text,
            styles["BodyTextCustom"]
        )]
        for text in safety_text
    ]

    safety_table = Table(
        safety_rows,
        colWidths=[490]
    )

    safety_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5)
    ]))

    story.append(safety_table)

    doc.build(
        story,
        onFirstPage=_header_footer,
        onLaterPages=_header_footer
    )

    return buffer.getvalue()
