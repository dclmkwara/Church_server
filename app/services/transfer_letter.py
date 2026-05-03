"""
Transfer Letter PDF Generator.

Generates an official DCLM church transfer/reference letter
for workers moving from one location to another.

PDF contents:
- Church letterhead (DCLM / state)
- Reference number (TRF-YYYY-NNNN)
- Worker details snapshot
- From/To location details
- Authorizing pastor details
- Formal transfer language
- Signature placeholder
"""
import os
import tempfile
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.transfers import WorkerTransfer


async def generate_transfer_letter(db: AsyncSession, *, transfer: "WorkerTransfer") -> str:
    """
    Generate a PDF transfer letter for a completed worker transfer.

    Returns the file path to the generated PDF (stored in /tmp for now;
    in production, upload to Supabase Storage and return the URL).
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
    except ImportError:
        raise RuntimeError("reportlab is not installed. Add 'reportlab' to requirements.txt")

    # Resolve relationship data (load eagerly if needed)
    worker = transfer.worker
    from_loc = transfer.from_location
    to_loc = transfer.to_location
    requester = transfer.requested_by

    # Build output path
    output_dir = tempfile.gettempdir()
    filename = f"transfer_letter_{transfer.reference_number}.pdf"
    output_path = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2.5 * cm,
        leftMargin=2.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # ── STYLES ──────────────────────────────────────────────────────────
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#4A1D8E"),
        alignment=TA_CENTER,
        spaceAfter=2,
        fontName="Helvetica-Bold",
    )
    subheader_style = ParagraphStyle(
        "SubHeader",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#6B7280"),
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#6B7280"),
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=16,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )
    ref_style = ParagraphStyle(
        "Ref",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#374151"),
    )
    gold_line_color = colors.HexColor("#D4AF37")
    purple_color = colors.HexColor("#4A1D8E")

    # ── LETTERHEAD ──────────────────────────────────────────────────────
    elements.append(Paragraph("DEEPER LIFE BIBLE CHURCH", header_style))
    elements.append(Paragraph("Kwara State, Nigeria", subheader_style))
    elements.append(Paragraph("Worker Transfer Reference Letter", subheader_style))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(HRFlowable(width="100%", thickness=2, color=gold_line_color))
    elements.append(Spacer(1, 0.3 * cm))

    # ── REFERENCE & DATE ────────────────────────────────────────────────
    ref_date = datetime.now().strftime("%d %B %Y")
    ref_data = [
        ["Reference:", transfer.reference_number or "N/A"],
        ["Date:", ref_date],
    ]
    ref_table = Table(ref_data, colWidths=[4 * cm, 12 * cm])
    ref_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6B7280")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(ref_table)
    elements.append(Spacer(1, 0.5 * cm))

    # ── WORKER DETAILS ──────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB")))
    elements.append(Spacer(1, 0.2 * cm))
    elements.append(Paragraph("WORKER INFORMATION", label_style))
    elements.append(Spacer(1, 0.2 * cm))

    worker_name = getattr(worker, "name", "N/A")
    worker_uid = getattr(worker, "user_id", "N/A")
    worker_unit = getattr(worker, "unit", "N/A")
    worker_phone = getattr(worker, "phone", "N/A")

    worker_data = [
        ["Full Name:", worker_name, "Worker ID:", str(worker_uid)],
        ["Serving Unit:", worker_unit, "Phone:", worker_phone],
    ]
    worker_table = Table(worker_data, colWidths=[4 * cm, 8 * cm, 3 * cm, 5 * cm])
    worker_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#374151")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6B7280")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#6B7280")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(worker_table)
    elements.append(Spacer(1, 0.4 * cm))

    # ── TRANSFER DETAILS ────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB")))
    elements.append(Spacer(1, 0.2 * cm))
    elements.append(Paragraph("TRANSFER DETAILS", label_style))
    elements.append(Spacer(1, 0.2 * cm))

    from_loc_name = getattr(from_loc, "location_name", transfer.from_location_id)
    to_loc_name = getattr(to_loc, "location_name", transfer.to_location_id)
    eff_date = transfer.effective_date.strftime("%d %B %Y") if transfer.effective_date else "N/A"

    transfer_data = [
        ["From Location:", from_loc_name],
        ["To Location:", to_loc_name],
        ["Effective Date:", eff_date],
        ["Transfer Reason:", transfer.transfer_reason or ""],
    ]
    transfer_table = Table(transfer_data, colWidths=[4 * cm, 12 * cm])
    transfer_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6B7280")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#374151")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(transfer_table)
    elements.append(Spacer(1, 0.5 * cm))

    # ── FORMAL LETTER BODY ──────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB")))
    elements.append(Spacer(1, 0.4 * cm))
    elements.append(Paragraph("TO WHOM IT MAY CONCERN", label_style))
    elements.append(Spacer(1, 0.3 * cm))

    salutation = "Brother" if getattr(worker, "gender", "").lower() == "male" else "Sister"
    formal_text = (
        f"This is to certify that <b>{salutation} {worker_name}</b> "
        f"(Worker ID: <b>{worker_uid}</b>, Serving Unit: <b>{worker_unit}</b>) "
        f"has served faithfully at <b>{from_loc_name}</b> and is hereby formally transferred to "
        f"<b>{to_loc_name}</b> with effect from <b>{eff_date}</b>."
        f"<br/><br/>"
        f"This transfer has been duly approved by the leadership of both the releasing and receiving assemblies. "
        f"We commend {salutation} {worker_name} to the receiving assembly and request that they be "
        f"received in the Lord and fully integrated into the work of the ministry."
        f"<br/><br/>"
        f"Please contact us if you require any further information."
    )
    elements.append(Paragraph(formal_text, body_style))
    elements.append(Spacer(1, 1 * cm))

    # ── SIGNATURE BLOCK ─────────────────────────────────────────────────
    sig_data = [
        ["___________________________", "___________________________"],
        ["Authorizing Pastor", "Receiving Pastor"],
        ["Name: _____________________", "Name: _____________________"],
        ["Date: _____________________", "Date: _____________________"],
    ]
    sig_table = Table(sig_data, colWidths=[8 * cm, 8 * cm])
    sig_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#374151")),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ]))
    elements.append(sig_table)
    elements.append(Spacer(1, 0.5 * cm))

    # ── FOOTER ──────────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=1, color=gold_line_color))
    elements.append(Spacer(1, 0.2 * cm))
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#9CA3AF"),
        alignment=TA_CENTER,
    )
    elements.append(Paragraph(
        f"Generated by DCLM Church Management System | Ref: {transfer.reference_number} | {ref_date}",
        footer_style
    ))

    doc.build(elements)
    return output_path
