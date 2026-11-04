"""Lectura de transcripciones TXT, VTT, SRT y DOCX en segmentos citables (03-R5, R6)."""
import io
import re

TS = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{3})\s*-->\s*(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{3})")


def _sec(h, m, s) -> int:
    return int(h or 0) * 3600 + int(m) * 60 + int(s)


def parse(name: str, data: bytes) -> tuple[list[tuple[int | None, int | None, str]], bool]:
    """Devuelve (segmentos [(inicio, fin, texto)], ¿trae marcas de tiempo?)."""
    ext = name.lower().rsplit(".", 1)[-1]
    if ext == "docx":
        import docx
        d = docx.Document(io.BytesIO(data))
        return [(None, None, p.text.strip()) for p in d.paragraphs if p.text.strip()], False
    if ext not in ("txt", "vtt", "srt"):
        raise ValueError("Formato no permitido: TXT, VTT, SRT o DOCX")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    segs: list[tuple[int | None, int | None, str]] = []
    if ext in ("vtt", "srt"):
        for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
            lines = [l for l in block.split("\n") if l.strip()]
            for i, l in enumerate(lines):
                m = TS.search(l)
                if m:
                    g = m.groups()
                    body = " ".join(x.strip() for x in lines[i + 1:])
                    if body:
                        segs.append((_sec(*g[0:3]), _sec(*g[4:7]), body))
                    break
        if segs:
            return segs, True
    segs = [(None, None, p.strip()) for p in text.splitlines() if p.strip() and p.strip() != "WEBVTT"]
    return segs, False
