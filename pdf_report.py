import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable)
from reportlab.lib.enums import TA_JUSTIFY


def build_pdf_report(data):
    """Construye un PDF en memoria (BytesIO) con el resumen de resultados."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                             topMargin=2 * cm, bottomMargin=2 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY, fontSize=10, leading=14))
    title_style = styles['Title']
    heading_style = styles['Heading2']

    story = []
    story.append(Paragraph("Reporte de Deteccion de Plagio", title_style))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"Documento analizado: {data.get('documento', 'N/A')}", styles['Normal']))
    story.append(Paragraph(f"Fecha de generacion: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    story.append(Paragraph(f"Similitud global estimada: <b>{data.get('similitud_global', 0)}%</b>", styles['Normal']))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", color=colors.grey))
    story.append(Spacer(1, 0.5 * cm))

    resultados = data.get('resultados', [])
    if not resultados:
        story.append(Paragraph("No se encontraron coincidencias significativas.", styles['Normal']))
    else:
        story.append(Paragraph("Coincidencias encontradas", heading_style))
        story.append(Spacer(1, 0.3 * cm))

        table_data = [["#", "Similitud", "URL", "Consulta usada"]]
        for i, r in enumerate(resultados, start=1):
            table_data.append([
                str(i),
                f"{r['similitud']}%",
                Paragraph(r['url'], styles['Normal']),
                Paragraph(r['consulta'], styles['Normal'])
            ])

        table = Table(table_data, colWidths=[1 * cm, 2.2 * cm, 8 * cm, 5.5 * cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.6 * cm))

        for i, r in enumerate(resultados, start=1):
            frases = r.get('frases_similares', [])
            if not frases:
                continue
            story.append(Paragraph(f"Detalle de coincidencia #{i} ({r['url']})", styles['Heading3']))
            for f in frases:
                story.append(Paragraph(f"<b>Original:</b> {f['frase_original']}", styles['Justify']))
                if f.get('frase_web'):
                    story.append(Paragraph(f"<b>Fuente web:</b> {f['frase_web']}", styles['Justify']))
                story.append(Paragraph(f"<b>Coincidencia:</b> {f['coincidencia']}%", styles['Normal']))
                story.append(Spacer(1, 0.3 * cm))

    doc.build(story)
    buffer.seek(0)
    return buffer