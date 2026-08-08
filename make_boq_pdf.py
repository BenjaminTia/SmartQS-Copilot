"""Generate a professional BOQ PDF: Repairs and Renovation Works for a Community Hall.
Different project, trades, and anomalies vs the demo BOQ. Planted anomalies:
  C2 emulsion painting rate 10x high (550 vs 55)      -> CRITICAL
  C4 waterproofing rate 2x high (530 vs 265)          -> WARNING
  B4 duplicate of B1 (demolition of partition walls)  -> WARNING
Everything else is deliberately clean to test precision (no false positives)."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak)

OUT = r"C:\Users\Benjamin\Downloads\SmartQS-Copilot\samples\boq_community_hall.pdf"

SECTIONS = [
    ("A", "PRELIMINARIES", [
        ("1", "Site establishment, safety and temporary works", "LS", "1", "150,000"),
        ("2", "Building services testing and commissioning", "LS", "1", "95,000"),
    ]),
    ("B", "DEMOLITION", [
        ("1", "Demolition of existing partition walls", "m2", "180", "480"),
        ("2", "Removal of existing floor finishes", "m2", "350", "95"),
        ("3", "Disposal of debris off site", "m3", "45", "320"),
        ("4", "Demolition of existing partition walls", "m2", "60", "485"),
    ]),
    ("C", "FINISHES", [
        ("1", "Cement sand plastering to walls (patch work)", "m2", "600", "175"),
        ("2", "Emulsion painting to walls and ceilings", "m2", "300", "550"),
        ("3", "Ceramic wall tiling to toilets", "m2", "220", "310"),
        ("4", "Waterproofing membrane to wet areas", "m2", "140", "530"),
        ("5", "Ceramic floor tiling to entrance lobby", "m2", "150", "330"),
        ("6", "Suspended ceiling with metal frame", "m2", "480", "375"),
        ("7", "Floor screeding to receive finishes", "m2", "500", "135"),
    ]),
    ("D", "DOORS AND WINDOWS", [
        ("1", "Hollow core door with frame and ironmongery", "no.", "12", "2,750"),
        ("2", "Aluminium window with glazing", "m2", "35", "3,150"),
    ]),
    ("E", "SERVICES", [
        ("1", "Electrical installation point", "no.", "160", "950"),
        ("2", "Plumbing installation point", "no.", "40", "1,080"),
        ("3", "Fire alarm detection point", "no.", "30", "1,250"),
        ("4", "LV switchboard supply and install", "no.", "1", "185,000"),
        ("5", "AC outlet point", "no.", "25", "1,350"),
        ("6", "Sanitary fitting supply and install", "no.", "10", "980"),
    ]),
    ("F", "EXTERNAL AND MISCELLANEOUS", [
        ("1", "Scaffolding to external walls", "m2", "400", "118"),
        ("2", "Stainless steel handrail supply and fix", "m", "45", "850"),
        ("3", "Builder's work for services openings", "no.", "30", "450"),
    ]),
]

styles = getSampleStyleSheet()
title_st = ParagraphStyle("t", parent=styles["Title"], fontSize=16, spaceAfter=2, textColor=colors.HexColor("#1a1a1a"))
sub_st = ParagraphStyle("s", parent=styles["Normal"], fontSize=9.5, leading=13, textColor=colors.HexColor("#333333"))
head_st = ParagraphStyle("h", parent=styles["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=4,
                         textColor=colors.white, backColor=colors.HexColor("#2f3b46"),
                         borderPadding=(4, 6, 4, 6))
th_st = ParagraphStyle("th", parent=styles["Normal"], fontSize=8.5, textColor=colors.white)
td_st = ParagraphStyle("td", parent=styles["Normal"], fontSize=8.5)
tdr_st = ParagraphStyle("tdr", parent=td_st, alignment=2)

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=16*mm, rightMargin=16*mm,
                        topMargin=16*mm, bottomMargin=18*mm,
                        title="Bill of Quantities - Community Hall Renovation", author="Smart QS Copilot")

def footer(canvas, doc_):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(16*mm, 10*mm, "BILL OF QUANTITIES - Repairs and Renovation Works for a Community Hall")
    canvas.drawRightString(A4[0]-16*mm, 10*mm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()

story = []
story.append(Paragraph("BILL OF QUANTITIES", title_st))
story.append(Paragraph("Repairs and Renovation Works for a Community Hall", sub_st))
story.append(Paragraph("Contract No. CH/2026/014 &nbsp;|&nbsp; Client: District Council &nbsp;|&nbsp; August 2026", sub_st))
story.append(Paragraph("This document is a test sample generated for the Smart QS Copilot screening app. "
                       "Rates are illustrative and must not be used for tendering.", sub_st))
story.append(Spacer(1, 4*mm))

def item_table(rows):
    data = [[Paragraph("Item", th_st), Paragraph("Description", th_st), Paragraph("Unit", th_st),
             Paragraph("Qty", th_st), Paragraph("Rate (HK$)", th_st)]]
    for item, desc, unit, qty, rate in rows:
        data.append([Paragraph(item, td_st), Paragraph(desc, td_st), Paragraph(unit, td_st),
                     Paragraph(qty, tdr_st), Paragraph(rate, tdr_st)])
    t = Table(data, colWidths=[16*mm, 106*mm, 16*mm, 14*mm, 24*mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f3b46")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8b8b8")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f6")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t

for sec, name, items in SECTIONS:
    story.append(Paragraph(f"{sec}. {name}", head_st))
    story.append(item_table([(f"{sec}{item}", desc, unit, qty, rate) for item, desc, unit, qty, rate in items]))
    story.append(Spacer(1, 2*mm))

doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("PDF written:", OUT, os.path.getsize(OUT), "bytes")
