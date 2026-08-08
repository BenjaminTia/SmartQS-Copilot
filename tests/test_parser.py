"""Tests for structure-aware BOQ PDF parsing."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, TableStyle

from src import parser as parser_module
from src.parser import parse_csv, parse_pdf

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = ROOT / "samples" / "sample_boq.csv"
FIXTURE = Path(__file__).parent / "fixtures" / "sample_boq.pdf"


def build_sample_pdf(path=FIXTURE):
    """Render the sample CSV as a realistic, multi-page landscape BOQ."""
    expected = parse_csv(SAMPLE_CSV.read_text(encoding="utf-8"))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=16 * mm,
    )
    cell = ParagraphStyle("boq-cell", fontName="Helvetica", fontSize=9, leading=12)
    header = ["Section", "Item", "Description", "Unit", "Quantity", "Rate (HK$)"]
    data = [header]
    for row in expected:
        data.append([
            row["section"],
            row["item"],
            Paragraph(row["description"], cell),
            row["unit"],
            f'{row["qty"]:,.2f}',
            f'{row["rate"]:,.2f}',
        ])

    table = LongTable(
        data,
        colWidths=[35 * mm, 15 * mm, 105 * mm, 18 * mm, 30 * mm, 30 * mm],
        repeatRows=1,
        splitByRow=True,
        spaceAfter=8 * mm,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9EAF7")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(
            landscape(A4)[0] / 2,
            8 * mm,
            f"SmartQS Sample BOQ  |  Page {document.page}",
        )
        canvas.restoreState()

    doc.build([table], onFirstPage=footer, onLaterPages=footer)
    return path


def test_parse_pdf_matches_sample_csv():
    fixture = build_sample_pdf()
    expected = parse_csv(SAMPLE_CSV.read_text(encoding="utf-8"))

    actual = parse_pdf(fixture)

    assert len(actual) == len(expected) == 27
    for parsed, source in zip(actual, expected):
        assert parsed["section"] == source["section"]
        assert parsed["item"] == source["item"]
        assert parsed["description"] == source["description"]
        assert parsed["unit"] == source["unit"]
        assert parsed["qty"] == source["qty"]
        assert parsed["rate"] == source["rate"]


def test_parse_pdf_accepts_bytes_and_filters_headers_and_footers():
    fixture = build_sample_pdf()

    rows = parse_pdf(fixture.read_bytes())

    assert len(rows) == 27
    parsed_text = " ".join(
        f'{row["item"]} {row["description"]}' for row in rows
    ).lower()
    assert "quantity" not in parsed_text
    assert "rate (hk$)" not in parsed_text
    assert "page 1" not in parsed_text
    assert "page 2" not in parsed_text


def test_parse_pdf_falls_back_to_positioned_words(monkeypatch):
    fixture = build_sample_pdf()
    expected = parse_csv(SAMPLE_CSV.read_text(encoding="utf-8"))
    monkeypatch.setattr(parser_module, "_records_from_tables", lambda document: [])

    actual = parse_pdf(fixture)

    assert len(actual) == 27
    assert [row["description"] for row in actual] == [
        row["description"] for row in expected
    ]
    assert [row["qty"] for row in actual] == [row["qty"] for row in expected]
    assert [row["rate"] for row in actual] == [row["rate"] for row in expected]
