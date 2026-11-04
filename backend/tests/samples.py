import io

import docx
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def make_pdf(pages: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for text in pages:
        y = 800
        for line in text.splitlines() or [""]:
            if line:
                c.drawString(50, y, line)
            y -= 16
        c.showPage()
    c.save()
    return buf.getvalue()


def make_docx(paragraphs: list[str]) -> bytes:
    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


# Los seis documentos de ejemplo del diseño (02, criterio 1).
def six_samples() -> list[tuple[str, str, str, bytes, str]]:
    return [
        ("plan_estrategico", "Plan_Estrategico_2026.pdf", "application/pdf",
         make_pdf(["Visión 2030\nCrecer en banca digital", "Objetivos\nReducir costos operativos"]), "pdf"),
        ("organigrama", "Organigrama.pdf", "application/pdf", make_pdf(["Presidencia\nVicepresidencia de Tecnología"]), "pdf"),
        ("mapa_procesos", "Mapa_de_procesos.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         make_docx(["Proceso de crédito", "Proceso de atención al cliente"]), "docx"),
        ("informe_tecnologia", "Informe_Tecnologia.pdf", "application/pdf", make_pdf(["Core bancario\nNube híbrida"]), "pdf"),
        ("politica_datos", "Politica_Datos_Personales.txt", "text/plain",
         "Política de tratamiento de datos personales conforme a la Ley 1581 de 2012.".encode(), "txt"),
        ("operaciones", "Operaciones.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         make_docx(["Volumen mensual de solicitudes: 400"]), "docx"),
    ]
