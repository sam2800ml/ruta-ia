import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

KIND = {"contradiccion": "Contradicción", "brecha": "Brecha", "fortaleza": "Fortaleza"}


def _esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def report_pdf(r: dict) -> bytes:
    st = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=f"Diagnóstico {r['company_name']}", leftMargin=48, rightMargin=48, topMargin=48, bottomMargin=48)
    out = [Paragraph(f"Diagnóstico de adopción de IA · {_esc(r['company_name'])}", st["Title"]),
           Paragraph(f"Versión {r['version']} · metodología v{r['methodology_version']} · "
                     f"{r['published_at']:%Y-%m-%d} · respaldado por {r['roles_responded']} de {r['roles_total']} roles", st["Normal"]),
           Spacer(1, 8),
           Paragraph(f"Nivel de madurez: {r['level']} de 5 · {_esc(r['level_name'] or '')} (promedio {r['average']:.1f})", st["Heading2"]),
           Paragraph(_esc(r["level_description"] or ""), st["Normal"]), Spacer(1, 8)]
    rows = [["Pilar", "Puntaje"]] + [[p["label"], f"{p['score']:.1f} de 5"] for p in r["pillars"]]
    t = Table(rows, colWidths=[300, 100])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]))
    out += [t, Spacer(1, 10), Paragraph("Hallazgos", st["Heading2"])]
    for f in r["findings"]:
        out.append(Paragraph(f"<b>{KIND[f['kind']]} · {_esc(f['pillar_label'] or '')}</b> — {_esc(f['title'])}", st["Normal"]))
        out.append(Paragraph(_esc(f["description"]), st["Normal"]))
        for e in f["evidence"]:
            out.append(Paragraph(f"<i>Evidencia ({e['source_type']}):</i> {_esc(e['quote'])}", st["Italic"]))
        out.append(Spacer(1, 6))
    out.append(Paragraph("Recomendaciones prioritarias", st["Heading2"]))
    for x in r["recommendations"]:
        out.append(Paragraph(f"{x['position']}. {_esc(x['text'])}", st["Normal"]))
    out += [Spacer(1, 14), Paragraph(_esc(r["declaration"]), st["Italic"])]
    doc.build(out)
    return buf.getvalue()
