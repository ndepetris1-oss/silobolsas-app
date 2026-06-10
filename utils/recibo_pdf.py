# utils/recibo_pdf.py
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from datetime import datetime

def generar_recibo_pdf(pago):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    verde = colors.HexColor("#1b5e20")
    verde_claro = colors.HexColor("#e8f5e9")
    gris = colors.HexColor("#666666")

    estilo_titulo = ParagraphStyle(
        "titulo", fontSize=22, textColor=verde,
        fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4
    )
    estilo_subtitulo = ParagraphStyle(
        "subtitulo", fontSize=11, textColor=gris,
        fontName="Helvetica", alignment=TA_CENTER, spaceAfter=2
    )
    estilo_normal = ParagraphStyle(
        "normal", fontSize=10, fontName="Helvetica", spaceAfter=4
    )
    estilo_bold = ParagraphStyle(
        "bold", fontSize=10, fontName="Helvetica-Bold", spaceAfter=4
    )
    estilo_derecha = ParagraphStyle(
        "derecha", fontSize=10, fontName="Helvetica", alignment=TA_RIGHT
    )
    estilo_recibo = ParagraphStyle(
        "recibo", fontSize=9, textColor=gris,
        fontName="Helvetica", alignment=TA_RIGHT
    )

    story = []

    # ENCABEZADO
    story.append(Paragraph("SILO BOLSAS", estilo_titulo))
    story.append(Paragraph("Sistema de Gestión de Silo Bolsas", estilo_subtitulo))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=verde))
    story.append(Spacer(1, 0.4*cm))

    # NÚMERO DE RECIBO Y FECHA
    num_recibo = f"REC-{pago.get('id', '0'):05d}"
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")

    datos_header = [
        [Paragraph("<b>RECIBO DE PAGO</b>", ParagraphStyle("rh", fontSize=14, fontName="Helvetica-Bold", textColor=verde)),
         Paragraph(f"N° {num_recibo}<br/>Emitido: {fecha_emision}", estilo_recibo)]
    ]
    tabla_header = Table(datos_header, colWidths=[10*cm, 7*cm])
    tabla_header.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(tabla_header)
    story.append(Spacer(1, 0.5*cm))

    # DATOS DE LA EMPRESA
    story.append(Paragraph("DATOS DEL CLIENTE", ParagraphStyle("sec", fontSize=9, textColor=gris, fontName="Helvetica-Bold", spaceAfter=4)))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 0.2*cm))

    datos_empresa = [
        ["Empresa:", pago.get("empresa_nombre", "-")],
        ["Fecha de pago:", pago.get("fecha_pago", "-")],
        ["Tipo de cobro:", pago.get("tipo_periodo", "-")],
    ]
    if pago.get("periodo"):
        datos_empresa.append(["Periodo:", pago.get("periodo")])

    tabla_empresa = Table(datos_empresa, colWidths=[4*cm, 13*cm])
    tabla_empresa.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("TEXTCOLOR", (0,0), (0,-1), verde),
    ]))
    story.append(tabla_empresa)
    story.append(Spacer(1, 0.5*cm))

    # DETALLE DEL PAGO
    story.append(Paragraph("DETALLE DEL PAGO", ParagraphStyle("sec2", fontSize=9, textColor=gris, fontName="Helvetica-Bold", spaceAfter=4)))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 0.2*cm))

    detalle_data = [
        ["Concepto", "Cantidad", "Importe"]
    ]

    concepto = f"Servicio Silo Bolsas - {pago.get('tipo_periodo', '')}"
    if pago.get("periodo"):
        concepto += f" ({pago.get('periodo')})"

    silos = pago.get("silos_cobrados", 0) or 0
    monto = pago.get("monto", 0) or 0

    detalle_data.append([
        concepto,
        f"{silos} silo/s" if silos else "-",
        f"$ {float(monto):,.2f}"
    ])

    tabla_detalle = Table(detalle_data, colWidths=[10*cm, 3*cm, 4*cm])
    tabla_detalle.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), verde),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("ALIGN", (1,0), (-1,-1), "CENTER"),
        ("ALIGN", (2,0), (2,-1), "RIGHT"),
        ("BACKGROUND", (0,1), (-1,-1), verde_claro),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
    ]))
    story.append(tabla_detalle)
    story.append(Spacer(1, 0.4*cm))

    # TOTAL
    total_data = [
        ["", "TOTAL:", f"$ {float(monto):,.2f}"]
    ]
    tabla_total = Table(total_data, colWidths=[10*cm, 3*cm, 4*cm])
    tabla_total.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 12),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("TEXTCOLOR", (1,0), (-1,-1), verde),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(tabla_total)
    story.append(Spacer(1, 0.5*cm))

    # MÉTODO DE PAGO
    story.append(Paragraph("MÉTODO DE PAGO", ParagraphStyle("sec3", fontSize=9, textColor=gris, fontName="Helvetica-Bold", spaceAfter=4)))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 0.2*cm))

    metodo_data = [["Método:", pago.get("metodo_pago", "-")]]
    if pago.get("comprobante"):
        metodo_data.append(["Comprobante N°:", pago.get("comprobante")])
    if pago.get("alias_cvu"):
        metodo_data.append(["Alias/CVU:", pago.get("alias_cvu")])
    if pago.get("observacion"):
        metodo_data.append(["Observación:", pago.get("observacion")])

    tabla_metodo = Table(metodo_data, colWidths=[4*cm, 13*cm])
    tabla_metodo.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("TEXTCOLOR", (0,0), (0,-1), verde),
    ]))
    story.append(tabla_metodo)
    story.append(Spacer(1, 1*cm))

    # PIE
    story.append(HRFlowable(width="100%", thickness=1, color=verde))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Este documento es un comprobante de pago válido generado por el sistema Silo Bolsas.",
        ParagraphStyle("pie", fontSize=8, textColor=gris, fontName="Helvetica", alignment=TA_CENTER)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer
