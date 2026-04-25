"""
PDF generation service for Intervention reports.

Layout:
  ┌─────────────────────────────────┐
  │  SGOI — Reporte de Intervención │  ← header band
  ├─────────────────────────────────┤
  │  Datos generales (2-col table)  │
  ├─────────────────────────────────┤
  │  Descripción                    │
  ├─────────────────────────────────┤
  │  Equipos asociados (table)      │
  ├─────────────────────────────────┤
  │  Evidencias fotográficas        │
  │  [img] [img] [img] …            │
  └─────────────────────────────────┘
"""

import io
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.platypus.flowables import HRFlowable
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.intervention import Intervention, InterventionAsset
from app.services.intervention_service import get_intervention_or_404

# ── Brand colours ──────────────────────────────────────────────────────────────
BRAND_DARK   = colors.HexColor("#1A2B4A")   # navy — header bg
BRAND_MID    = colors.HexColor("#2563EB")   # blue — section titles
BRAND_LIGHT  = colors.HexColor("#EFF6FF")   # very light blue — table alt row
BRAND_ACCENT = colors.HexColor("#F59E0B")   # amber — separator line
GRAY_TEXT    = colors.HexColor("#374151")
GRAY_LIGHT   = colors.HexColor("#F3F4F6")
GRAY_BORDER  = colors.HexColor("#D1D5DB")
WHITE        = colors.white

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm

# ── Styles ─────────────────────────────────────────────────────────────────────

def _build_styles():
    base = getSampleStyleSheet()
    styles = {}

    styles["doc_title"] = ParagraphStyle(
        "doc_title",
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=WHITE,
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    styles["doc_subtitle"] = ParagraphStyle(
        "doc_subtitle",
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#BFDBFE"),
        alignment=TA_CENTER,
    )
    styles["section_title"] = ParagraphStyle(
        "section_title",
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=BRAND_MID,
        spaceBefore=14,
        spaceAfter=6,
    )
    styles["body"] = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=9,
        textColor=GRAY_TEXT,
        leading=14,
        spaceAfter=4,
    )
    styles["label"] = ParagraphStyle(
        "label",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=GRAY_TEXT,
    )
    styles["value"] = ParagraphStyle(
        "value",
        fontName="Helvetica",
        fontSize=9,
        textColor=GRAY_TEXT,
    )
    styles["table_header"] = ParagraphStyle(
        "table_header",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=WHITE,
        alignment=TA_CENTER,
    )
    styles["table_cell"] = ParagraphStyle(
        "table_cell",
        fontName="Helvetica",
        fontSize=8,
        textColor=GRAY_TEXT,
        leading=11,
    )
    styles["footer"] = ParagraphStyle(
        "footer",
        fontName="Helvetica",
        fontSize=7,
        textColor=colors.HexColor("#9CA3AF"),
        alignment=TA_RIGHT,
    )
    return styles


# ── Page template with header/footer ──────────────────────────────────────────

def _header_footer(canvas, doc, intervention, styles):
    canvas.saveState()

    # ── Header band ───────────────────────────────────────────────────────────
    header_h = 2.4 * cm
    canvas.setFillColor(BRAND_DARK)
    canvas.rect(0, PAGE_H - header_h, PAGE_W, header_h, fill=1, stroke=0)

    # Amber accent stripe
    canvas.setFillColor(BRAND_ACCENT)
    canvas.rect(0, PAGE_H - header_h - 4, PAGE_W, 4, fill=1, stroke=0)

    # Title text
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 1.5 * cm, "SGOI — Reporte de Intervención")

    canvas.setFillColor(colors.HexColor("#BFDBFE"))
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(
        PAGE_W / 2,
        PAGE_H - 2.05 * cm,
        f"Sistema de Gestión Operativa e Inventario  ·  Generado: "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M')}",
    )

    # ── Footer ────────────────────────────────────────────────────────────────
    canvas.setFillColor(GRAY_BORDER)
    canvas.rect(MARGIN, 1.2 * cm, PAGE_W - 2 * MARGIN, 0.5, fill=1, stroke=0)

    canvas.setFillColor(colors.HexColor("#9CA3AF"))
    canvas.setFont("Helvetica", 7)
    canvas.drawString(
        MARGIN, 0.85 * cm,
        f"Intervención #{intervention.id}  ·  RIG: {intervention.rig}  ·  Pozo: {intervention.pozo}",
    )
    canvas.drawRightString(
        PAGE_W - MARGIN, 0.85 * cm,
        f"Página {doc.page}",
    )

    canvas.restoreState()


# ── Section helpers ────────────────────────────────────────────────────────────

def _section_title(text: str, styles) -> list:
    return [
        Paragraph(text, styles["section_title"]),
        HRFlowable(width="100%", thickness=1, color=BRAND_MID, spaceAfter=6),
    ]


def _info_table(rows: list[tuple[str, str]], styles) -> Table:
    """Two-column label/value table for general data."""
    col_w = (PAGE_W - 2 * MARGIN) / 2 - 0.3 * cm
    data = [
        [
            Paragraph(label, styles["label"]),
            Paragraph(str(value or "—"), styles["value"]),
        ]
        for label, value in rows
    ]
    t = Table(data, colWidths=[col_w * 0.38, col_w * 0.62] * 1, repeatRows=0)
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, GRAY_LIGHT]),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.5, GRAY_BORDER),
    ]))
    return t


def _assets_table(intervention_assets: list, styles) -> Table:
    """Table listing all assets associated with the intervention."""
    full_w = PAGE_W - 2 * MARGIN
    col_widths = [
        full_w * 0.07,  # #
        full_w * 0.20,  # Part Number
        full_w * 0.30,  # Nombre
        full_w * 0.18,  # Serial / Código
        full_w * 0.13,  # Estado
        full_w * 0.12,  # Ubicación
    ]
    header = [
        Paragraph(h, styles["table_header"])
        for h in ["#", "Part Number", "Nombre del equipo", "Serial / Código", "Estado", "Ubicación"]
    ]
    rows = [header]

    for idx, ia in enumerate(intervention_assets, start=1):
        asset = ia.asset
        identifier = asset.serial_number or asset.internal_code or "—"
        rows.append([
            Paragraph(str(idx), styles["table_cell"]),
            Paragraph(asset.part.part_number if asset.part else "—", styles["table_cell"]),
            Paragraph(asset.item_name, styles["table_cell"]),
            Paragraph(identifier, styles["table_cell"]),
            Paragraph(asset.status.value.replace("_", " ").title(), styles["table_cell"]),
            Paragraph(asset.location or "—", styles["table_cell"]),
        ])

    t = Table(rows, colWidths=col_widths, repeatRows=1)
    row_colors = [BRAND_LIGHT, WHITE]
    t.setStyle(TableStyle([
        # Header
        ("BACKGROUND",    (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 8),
        ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
        # Body
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), row_colors),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 8),
        ("TOPPADDING",    (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",          (0, 0), (-1, -1), 0.5, GRAY_BORDER),
    ]))
    return t


def _evidence_grid(evidences, styles) -> list:
    """Renders evidence images in a 3-column grid with captions."""
    if not evidences:
        return [Paragraph("No se adjuntaron evidencias fotográficas.", styles["body"])]

    IMG_W = (PAGE_W - 2 * MARGIN - 2 * 0.4 * cm) / 3
    IMG_H = IMG_W * 0.75  # 4:3 aspect ratio

    elements = []
    row = []

    for idx, ev in enumerate(evidences, start=1):
        abs_path = Path(settings.media_dir) / ev.file_path

        if abs_path.exists():
            try:
                img = Image(str(abs_path), width=IMG_W, height=IMG_H)
                img.hAlign = "CENTER"
                caption = Paragraph(
                    f"<font size='7' color='#6B7280'>{idx}. {ev.original_filename or 'imagen'}</font>",
                    ParagraphStyle("cap", alignment=TA_CENTER, leading=9),
                )
                cell_content = [img, Spacer(1, 3), caption]
            except Exception:
                cell_content = [
                    Paragraph(
                        f"<font size='8' color='#EF4444'>⚠ No se pudo cargar imagen #{idx}</font>",
                        styles["body"],
                    )
                ]
        else:
            cell_content = [
                Paragraph(
                    f"<font size='8' color='#9CA3AF'>[Archivo no encontrado: {ev.original_filename}]</font>",
                    styles["body"],
                )
            ]

        row.append(cell_content)

        if len(row) == 3:
            t = Table([row], colWidths=[IMG_W] * 3)
            t.setStyle(TableStyle([
                ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING",   (0, 0), (-1, -1), 4),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            elements.append(t)
            row = []

    # Remaining images (< 3 in last row)
    if row:
        # Pad with empty cells
        while len(row) < 3:
            row.append([Spacer(1, 1)])
        t = Table([row], colWidths=[IMG_W] * 3)
        t.setStyle(TableStyle([
            ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(t)

    return elements


# ── Main generator ─────────────────────────────────────────────────────────────

def generate_intervention_pdf(db: Session, intervention_id: int) -> bytes:
    """
    Generates a PDF report for the given intervention.
    Returns the raw PDF bytes ready to be streamed.
    """
    intervention: Intervention = get_intervention_or_404(db, intervention_id)
    styles = _build_styles()

    buffer = io.BytesIO()

    # ── Document setup ─────────────────────────────────────────────────────────
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=3.2 * cm,   # space for header band
        bottomMargin=1.8 * cm,
    )

    frame = Frame(
        MARGIN, 1.8 * cm,
        PAGE_W - 2 * MARGIN,
        PAGE_H - 3.2 * cm - 1.8 * cm,
        id="main",
    )

    def _page_cb(canvas, doc):
        _header_footer(canvas, doc, intervention, styles)

    doc.addPageTemplates([
        PageTemplate(id="main", frames=[frame], onPage=_page_cb)
    ])

    # ── Story (content) ────────────────────────────────────────────────────────
    story = []

    # ── 1. General data ────────────────────────────────────────────────────────
    story += _section_title("Datos Generales de la Intervención", styles)

    type_label = intervention.type.value.replace("_", " ").title()
    date_str = intervention.date.strftime("%d / %m / %Y")

    # Split into two side-by-side info tables
    left_rows = [
        ("ID de Intervención", f"#{intervention.id}"),
        ("Tipo de evento",     type_label),
        ("RIG",                intervention.rig),
        ("Pozo",               intervention.pozo),
    ]
    right_rows = [
        ("Técnico responsable", intervention.technician),
        ("Fecha de intervención", date_str),
        ("Equipos asociados",   str(len(intervention.intervention_assets))),
        ("Evidencias",          str(len(intervention.evidences))),
    ]

    full_w = PAGE_W - 2 * MARGIN
    half_w = full_w / 2 - 0.2 * cm

    def _half_info(rows):
        col_w_l = half_w * 0.42
        col_w_r = half_w * 0.58
        data = [
            [Paragraph(l, styles["label"]), Paragraph(str(v or "—"), styles["value"])]
            for l, v in rows
        ]
        t = Table(data, colWidths=[col_w_l, col_w_r])
        t.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, GRAY_LIGHT]),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("GRID",          (0, 0), (-1, -1), 0.5, GRAY_BORDER),
        ]))
        return t

    two_col = Table(
        [[_half_info(left_rows), _half_info(right_rows)]],
        colWidths=[half_w, half_w],
        hAlign="LEFT",
    )
    two_col.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("INNERGRID",     (0, 0), (-1, -1), 0, WHITE),
        ("BOX",           (0, 0), (-1, -1), 0, WHITE),
    ]))
    story.append(KeepTogether(two_col))

    # ── 2. Description ─────────────────────────────────────────────────────────
    story += _section_title("Descripción de la Intervención", styles)
    desc_text = intervention.description or "Sin descripción registrada."
    story.append(Paragraph(desc_text, styles["body"]))

    # ── 3. Associated assets ───────────────────────────────────────────────────
    story += _section_title(
        f"Equipos Asociados ({len(intervention.intervention_assets)})", styles
    )
    if intervention.intervention_assets:
        story.append(_assets_table(intervention.intervention_assets, styles))

        # Per-asset notes (if any)
        notes_with_data = [
            ia for ia in intervention.intervention_assets if ia.notes
        ]
        if notes_with_data:
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph("Notas por equipo:", styles["label"]))
            for ia in notes_with_data:
                identifier = ia.asset.serial_number or ia.asset.internal_code
                story.append(
                    Paragraph(
                        f"• <b>{identifier}</b> — {ia.notes}",
                        styles["body"],
                    )
                )
    else:
        story.append(Paragraph("No se asociaron equipos a esta intervención.", styles["body"]))

    # ── 4. Evidence photos ─────────────────────────────────────────────────────
    story += _section_title(
        f"Evidencias Fotográficas ({len(intervention.evidences)})", styles
    )
    story += _evidence_grid(intervention.evidences, styles)

    # ── Build PDF ──────────────────────────────────────────────────────────────
    doc.build(story)
    buffer.seek(0)
    return buffer.read()
