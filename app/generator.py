"""Certificate rendering. One predefined template, drawn with ReportLab."""
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

NAVY = colors.HexColor("#1F3A5F")
GOLD = colors.HexColor("#B8923A")


def _fit_font_size(text: str, font: str, max_width: float, start: int, minimum: int = 14) -> int:
    size = start
    while size > minimum and stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def generate_certificate_pdf(path: str, *, name: str, title: str, event_name: str,
                             issuer: str, issue_date: str, achievement: str | None = None) -> None:
    """Render one certificate to `path`.

    Written to a temp file first and renamed, so a crash mid-render never
    leaves a half-written PDF that looks like a valid certificate.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"

    width, height = landscape(A4)
    cx = width / 2
    max_text_width = width - 160

    c = canvas.Canvas(tmp_path, pagesize=(width, height))
    c.setTitle(f"{title} - {name}")

    # Borders
    c.setStrokeColor(NAVY)
    c.setLineWidth(6)
    c.rect(25, 25, width - 50, height - 50)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.rect(38, 38, width - 76, height - 76)

    # Title
    c.setFillColor(NAVY)
    size = _fit_font_size(title, "Helvetica-Bold", max_text_width, 38)
    c.setFont("Helvetica-Bold", size)
    c.drawCentredString(cx, height - 130, title)

    c.setFillColor(colors.HexColor("#555555"))
    c.setFont("Helvetica", 16)
    c.drawCentredString(cx, height - 180, "This certificate is proudly presented to")

    # Recipient name
    c.setFillColor(GOLD)
    size = _fit_font_size(name, "Helvetica-BoldOblique", max_text_width, 44)
    c.setFont("Helvetica-BoldOblique", size)
    c.drawCentredString(cx, height - 245, name)
    name_w = stringWidth(name, "Helvetica-BoldOblique", size)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(cx - name_w / 2 - 20, height - 255, cx + name_w / 2 + 20, height - 255)

    # Event
    c.setFillColor(colors.HexColor("#555555"))
    c.setFont("Helvetica", 16)
    c.drawCentredString(cx, height - 295, "for participation in")
    c.setFillColor(NAVY)
    size = _fit_font_size(event_name, "Helvetica-Bold", max_text_width, 26)
    c.setFont("Helvetica-Bold", size)
    c.drawCentredString(cx, height - 330, event_name)

    if achievement:
        c.setFillColor(colors.HexColor("#555555"))
        size = _fit_font_size(achievement, "Helvetica-Oblique", max_text_width, 16, minimum=9)
        c.setFont("Helvetica-Oblique", size)
        c.drawCentredString(cx, height - 360, achievement)

    # Footer
    c.setFillColor(NAVY)
    c.setFont("Helvetica", 13)
    c.drawString(90, 90, f"Date: {issue_date}")
    c.drawRightString(width - 90, 90, f"Issued by {issuer}")

    c.showPage()
    c.save()
    os.replace(tmp_path, path)
