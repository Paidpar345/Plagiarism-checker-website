import io
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, Image)
from reportlab.lib.enums import TA_JUSTIFY


def _build_similarity_chart(resultados):
    if not resultados:
        return None

    top = resultados[:10]
    labels = [r["url"][:40] + ("..." if len(r["url"]) > 40 else "") for r in top]
    values = [r["similitud"] for r in top]

    fig, ax = plt.subplots(figsize=(6, max(2, len(top) * 0.4)))
    bars = ax.barh(labels, values, color="#0d6efd")
    ax.set_xlabel("Similitud (%)")
    ax.set_title("Similitud por fuente encontrada")
    ax.invert_yaxis()
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2, f"{val}%", va="center", fontsize=8)

    plt.tight_layout()
    img_buffer = io.BytesIO()
    fig.savefig(img_buffer, format="png", dpi=150)
    plt.close(fig)
    img_buffer.seek(0)
    return img_buffer


def build_pdf_report(data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                             topMargin=2 * cm, bottomMargin=2 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Justify", alignment=TA_JUSTIFY, fontSize=10, leading=14))
    title_style = styles["Title"]
    heading_style = styles["Heading2"]

    story = []
    story.append(Paragraph("Reporte de Deteccion de Plagio", title_style))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"Documento analizado: {data.get('documento', 'N/A')}", styles["Normal"]))
    story.append(Paragraph(f"Fecha de generacion: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
    story.append(Paragraph(f"Similitud global estimada: <b>{data.get('similitud_global', 0)}%</b>", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", color=colors.grey))
    story.append(Spacer(1, 0.5 * cm))

    resultados = data.get("resultados", [])

    chart_buffer = _build_similarity_chart(resultados)
    if chart_buffer:
        story.append(Paragraph("Resumen visual de similitud", heading_style))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Image(chart_buffer, width=16 * cm, height=min(12, len(resultados[:10]) * 0.8 + 2) * cm))
        story.append(Spacer(1, 0.5 * cm))

    if not resultados:
        story.append(Paragraph("No se encontraron coincidencias significativas.", styles["Normal"]))
    else:
        story.append(Paragraph("Coincidencias encontradas", heading_style))
        story.append(Spacer(1, 0.3 * cm))

        table_data = [["#", "Similitud", "TF-IDF", "N-gramas", "Shingling", "URL"]]
        for i, r in enumerate(resultados, start=1):
            table_data.append([
                str(i),
                f"{r['similitud']}%",
                f"{r.get('similitud_tfidf', 0)}%",
                f"{r.get('similitud_ngramas', 0)}%",
                f"{r.get('similitud_shingling', 0)}%",
                Paragraph(r["url"], styles["Normal"]),
            ])

        table = Table(table_data, colWidths=[1 * cm, 2 * cm, 2 * cm, 2 * cm, 2.2 * cm, 7.5 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.6 * cm))

        for i, r in enumerate(resultados, start=1):
            frases = r.get("frases_similares", [])
            if not frases:
                continue
            story.append(Paragraph(f"Detalle de coincidencia #{i} ({r['url']})", styles["Heading3"]))
            for f in frases:
                story.append(Paragraph(f"<b>Original:</b> {f['frase_original']}", styles["Justify"]))
                if f.get("frase_web"):
                    story.append(Paragraph(f"<b>Fuente web:</b> {f['frase_web']}", styles["Justify"]))
                story.append(Paragraph(f"<b>Coincidencia:</b> {f['coincidencia']}%", styles["Normal"]))
                story.append(Spacer(1, 0.3 * cm))

    doc.build(story)
    buffer.seek(0)
    return buffer