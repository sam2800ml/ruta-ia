"""Herramientas del agente de diagnóstico. Todas operan sobre las fuentes ya cargadas en memoria
(fragmentos de documentos y segmentos de transcripciones de la empresa) — no hacen IO adicional ni
llaman a ningún modelo. El agente las invoca para buscar evidencia real antes de proponer un hallazgo,
en vez de recibir todo el contenido de una vez en el prompt.
"""
import re

PILAR_KEYWORDS = {
    "strategy": ["estrategia", "presupuesto", "objetivos", "visión", "dirección"],
    "infrastructure": ["infraestructura", "nube", "integración", "servidores", "core bancario", "sistemas"],
    "data": ["datos", "calidad de los datos", "información", "bases de datos"],
    "governance": ["política", "gobernanza", "riesgo", "ética", "comité", "regulación"],
    "talent": ["talento", "formación", "capacitación", "habilidades", "equipo técnico"],
    "culture": ["cultura", "confianza", "experimentación", "resistencia", "cambio"],
}

Source = tuple[str, str, str, dict]  # (source_type, source_id, text, ref)


def build_sources(fragments: list[dict], segments: list[dict]) -> list[Source]:
    return ([("document", f["id"], f["text"], {"document": f["document"], "page": f["page"]}) for f in fragments] +
            [("transcript", s["id"], s["text"], {"transcript": s["transcript"], "start_sec": s["start_sec"]}) for s in segments])


def _find_quote(quote: str, source: str) -> str | None:
    """Confirma que la cita exista literalmente en la fuente (ignora mayúsculas y espacios de más).
    Si el modelo no puede señalar un fragmento real, el hallazgo se descarta en vez de inventarlo."""
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    q, s = norm(quote), norm(source)
    if not q or q.lower() not in s.lower():
        return None
    i = s.lower().index(q.lower())
    return s[i:i + len(q)]


def buscar_evidencia(sources: list[Source], query: str, limite: int = 5) -> list[dict]:
    """Busca una palabra o frase dentro de las fuentes. Devuelve el índice de cada fuente donde aparece, con un extracto."""
    q = (query or "").strip().lower()
    if not q:
        return []
    hits = []
    for i, (_, _, text, _) in enumerate(sources):
        low = text.lower()
        pos = low.find(q)
        if pos == -1:
            continue
        start, end = max(0, pos - 60), min(len(text), pos + len(q) + 60)
        hits.append({"indice_fuente": i, "extracto": text[start:end]})
        if len(hits) >= limite:
            break
    return hits


def verificar_cita(sources: list[Source], indice_fuente: int, cita: str) -> dict:
    """Confirma si una cita textual existe literalmente en la fuente indicada."""
    if not isinstance(indice_fuente, int) or not (0 <= indice_fuente < len(sources)):
        return {"valido": False, "motivo": "índice de fuente fuera de rango"}
    _, _, text, _ = sources[indice_fuente]
    found = _find_quote(cita or "", text)
    return {"valido": bool(found), "cita_real": found}


def listar_vacios(sources: list[Source]) -> list[str]:
    """Pilares (de los 6) para los que ninguna fuente tiene evidencia relacionada todavía."""
    covered = set()
    for _, _, text, _ in sources:
        low = text.lower()
        for pillar, kws in PILAR_KEYWORDS.items():
            if any(k in low for k in kws):
                covered.add(pillar)
    return [p for p in PILAR_KEYWORDS if p not in covered]


TOOL_DEFS = [
    {"name": "buscar_evidencia", "description":
        "Busca una palabra o frase dentro de los documentos y transcripciones de la empresa. "
        "Devuelve los índices de fuente donde aparece, con un extracto de contexto.",
     "parameters": {"type": "object", "properties": {
        "query": {"type": "string", "description": "palabra o frase a buscar"}}, "required": ["query"]}},
    {"name": "verificar_cita", "description":
        "Confirma si una cita textual existe literalmente en una fuente, antes de usarla en un hallazgo.",
     "parameters": {"type": "object", "properties": {
        "indice_fuente": {"type": "integer", "description": "índice de la fuente a verificar"},
        "cita": {"type": "string", "description": "texto exacto que se quiere citar"}}, "required": ["indice_fuente", "cita"]}},
    {"name": "listar_vacios", "description":
        "Devuelve cuáles de los 6 pilares (strategy, infrastructure, data, governance, talent, culture) "
        "no tienen ninguna evidencia encontrada todavía en las fuentes.",
     "parameters": {"type": "object", "properties": {}}},
]


def call_tool(sources: list[Source], name: str, args: dict) -> dict:
    if name == "buscar_evidencia":
        return {"resultados": buscar_evidencia(sources, args.get("query", ""))}
    if name == "verificar_cita":
        return verificar_cita(sources, args.get("indice_fuente", -1), args.get("cita", ""))
    if name == "listar_vacios":
        return {"pilares_sin_evidencia": listar_vacios(sources)}
    return {"error": f"herramienta desconocida: {name}"}
