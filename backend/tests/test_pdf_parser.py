import io

from reportlab.pdfgen import canvas

from app.tools.parser import extract_text_from_pdf


def _build_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, text)
    pdf.save()
    return buffer.getvalue()


def test_extract_text_from_pdf() -> None:
    pdf_bytes = _build_pdf("Hello ClaimPilot")
    text = extract_text_from_pdf(pdf_bytes)
    assert "Hello ClaimPilot" in text


def test_extract_text_from_blank_pdf() -> None:
    pdf_bytes = _build_pdf("")
    text = extract_text_from_pdf(pdf_bytes)
    assert text == ""
