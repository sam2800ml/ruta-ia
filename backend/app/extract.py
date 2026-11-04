"""Extrae texto de PDF, DOCX y TXT en fragmentos que recuerdan su página (02-R7)."""
import io
import zipfile

CHUNK = 1200


class ExtractError(Exception):
    pass


def detect_kind(filename: str, head: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf") and head.startswith(b"%PDF"):
        return "pdf"
    if name.endswith(".docx") and head.startswith(b"PK"):
        return "docx"
    if name.endswith(".txt"):
        return "txt"
    raise ExtractError("Formato no permitido: solo PDF, DOCX o TXT")


def _chunks(text: str) -> list[str]:
    out, cur = [], ""
    for para in [p.strip() for p in text.splitlines() if p.strip()]:
        while len(para) > CHUNK:
            if cur:
                out.append(cur); cur = ""
            out.append(para[:CHUNK]); para = para[CHUNK:]
        if len(cur) + len(para) + 1 > CHUNK and cur:
            out.append(cur); cur = para
        else:
            cur = f"{cur}\n{para}".strip()
    if cur:
        out.append(cur)
    return out


def extract(data: bytes, kind: str) -> list[tuple[int | None, str]]:
    """Devuelve [(página, texto)]. La página es None en formatos sin páginas."""
    pages: list[tuple[int | None, str]] = []
    if kind == "pdf":
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(data))
            for i, p in enumerate(reader.pages, start=1):
                pages.append((i, p.extract_text() or ""))
        except Exception as e:
            raise ExtractError("No se pudo leer el PDF") from e
    elif kind == "docx":
        import docx
        try:
            d = docx.Document(io.BytesIO(data))
        except (zipfile.BadZipFile, KeyError, ValueError) as e:
            raise ExtractError("No se pudo leer el DOCX") from e
        parts = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                parts.append(" | ".join(c.text for c in row.cells))
        pages.append((None, "\n".join(parts)))
    else:
        try:
            pages.append((None, data.decode("utf-8")))
        except UnicodeDecodeError:
            pages.append((None, data.decode("latin-1")))
    frags = [(page, c) for page, text in pages for c in _chunks(text)]
    if not frags:
        # Decisión 8 pendiente: los PDF escaneados se rechazan con aviso, sin reconocimiento de texto.
        raise ExtractError("El documento no tiene texto extraíble (¿es un escaneo?)")
    return frags
