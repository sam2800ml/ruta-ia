"""Interfaz del modelo de IA. La lógica de agentes solo conoce esta clase: el proveedor se cambia sin rehacerla.

Dos implementaciones:
- StubLLM: determinista, sin red. Sirve para desarrollo y pruebas.
- AnthropicLLM: usa Claude. Aún NO se ha ejecutado contra la API real (sin clave en este entorno); verificar antes de usar con datos reales.
"""
import re
from dataclasses import dataclass, field

from .config import settings

PILAR_KEYWORDS = {
    "strategy": ["estrategia", "presupuesto", "objetivos", "visión", "dirección"],
    "infrastructure": ["infraestructura", "nube", "integración", "servidores", "core bancario", "sistemas"],
    "data": ["datos", "calidad de los datos", "información", "bases de datos"],
    "governance": ["política", "gobernanza", "riesgo", "ética", "comité", "regulación"],
    "talent": ["talento", "formación", "capacitación", "habilidades", "equipo técnico"],
    "culture": ["cultura", "confianza", "experimentación", "resistencia", "cambio"],
}
NEGATIVE = re.compile(r"\b(no tenemos|no existe|no hay|sin |carece|falta|no contamos)\b", re.I)
POSITIVE = re.compile(r"\b(contamos con|tenemos|existe una|existe un|cuenta con)\b", re.I)


@dataclass
class Candidate:
    kind: str            # contradiccion | brecha | fortaleza
    pillar: str
    title: str
    description: str
    evidence: list[dict] = field(default_factory=list)   # {source_type, source_id, quote, ref}


@dataclass
class Turn:
    reply: str
    proposal: dict | None = None     # {kind, text, basis}


class LLM:
    name = "base"

    def propose_findings(self, fragments: list[dict], segments: list[dict]) -> list[Candidate]:
        raise NotImplementedError

    def strategy_turn(self, stage: str, context: dict, history: list[dict], user_message: str | None) -> Turn:
        raise NotImplementedError


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


class StubLLM(LLM):
    name = "stub"

    def propose_findings(self, fragments, segments):
        out: list[Candidate] = []
        sources = ([("document", f["id"], f["text"], {"document": f["document"], "page": f["page"]}) for f in fragments] +
                   [("transcript", s["id"], s["text"], {"transcript": s["transcript"], "start_sec": s["start_sec"]}) for s in segments])
        for stype, sid, text, ref in sources:
            for sent in _sentences(text):
                low = sent.lower()
                for pillar, kws in PILAR_KEYWORDS.items():
                    if any(k in low for k in kws):
                        kind = "brecha" if NEGATIVE.search(sent) else "fortaleza" if POSITIVE.search(sent) else None
                        if kind:
                            out.append(Candidate(kind, pillar, sent[:90].rstrip(".") , f"Según la fuente: «{sent}»",
                                                 [{"source_type": stype, "source_id": sid, "quote": sent, "ref": ref}]))
                            break
        return out[:8]

    def strategy_turn(self, stage, context, history, user_message):
        return scripted_strategy_turn(stage, context, history, user_message)


STAGES = ["vision", "objetivos", "gobernanza", "oportunidades", "okrs"]
STAGE_LABELS = {"vision": "Visión", "objetivos": "Objetivos de negocio", "gobernanza": "Principios de gobernanza",
                "oportunidades": "Oportunidades", "okrs": "OKRs"}
STAGE_KIND = {"vision": "vision", "objetivos": "objetivo", "gobernanza": "principio", "oportunidades": "oportunidad", "okrs": "okr"}
OPENERS = {
    "vision": "Empecemos por la visión. ¿Qué papel quiere que tenga la IA en su organización en tres años?",
    "objetivos": "Ahora los objetivos de negocio. ¿Qué resultado concreto quiere lograr con IA el próximo año?",
    "gobernanza": "Pasemos a los principios de gobernanza. ¿Qué reglas deben cumplir todos los usos de IA?",
    "oportunidades": "Ahora las oportunidades. ¿En qué proceso concreto ve mayor potencial de ahorro o mejora?",
    "okrs": "Por último, los OKRs. ¿Cómo mediría el éxito de su estrategia en 90 días?",
}


def scripted_strategy_turn(stage, context, history, user_message) -> Turn:
    """Asistente guiado sin modelo: pregunta por etapa, apoya la sugerencia en el diagnóstico publicado
    y solo propone con lo que la persona dijo (no inventa datos)."""
    if user_message is None:
        weak = context.get("weakest")
        hint = f" Su diagnóstico muestra {weak['label']}: {weak['score']:.1f} de 5." if weak and stage in ("gobernanza", "objetivos") else ""
        return Turn(OPENERS[stage] + hint)
    text = user_message.strip()
    basis = None
    if stage == "gobernanza" and context.get("weakest"):
        basis = f"{context['weakest']['label']}: {context['weakest']['score']:.1f} de 5"
    return Turn("Entiendo. Le propongo dejarlo así. ¿Lo guarda, lo edita o seguimos conversando?",
                {"kind": STAGE_KIND[stage], "text": text, "basis": basis})


class AnthropicLLM(LLM):
    name = "anthropic"

    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def propose_findings(self, fragments, segments):
        """Hallazgos con Citations: cada fragmento o segmento es un documento citable (la cita apunta a su texto exacto)."""
        sources = ([("document", f["id"], f["text"], {"document": f["document"], "page": f["page"]}) for f in fragments] +
                   [("transcript", s["id"], s["text"], {"transcript": s["transcript"], "start_sec": s["start_sec"]}) for s in segments])
        if not sources:
            return []
        blocks = [{"type": "document", "source": {"type": "content", "content": [{"type": "text", "text": t}]},
                   "title": f"{i}", "citations": {"enabled": True}} for i, (_, _, t, _) in enumerate(sources)]
        prompt = ("Eres consultor de adopción de IA. Con los documentos dados, lista hasta 8 hallazgos. Una línea por hallazgo con el "
                  "formato: pilar|tipo|título|descripción. pilar ∈ strategy, infrastructure, data, governance, talent, culture. "
                  "tipo ∈ brecha, fortaleza, contradiccion. Cada línea debe apoyarse en una cita del texto. No inventes datos.")
        msg = self.client.messages.create(model=settings.anthropic_model, max_tokens=2000,
                                          messages=[{"role": "user", "content": blocks + [{"type": "text", "text": prompt}]}])
        out: list[Candidate] = []
        for block in msg.content:
            if getattr(block, "type", "") != "text" or not getattr(block, "citations", None):
                continue
            parts = [p.strip() for p in block.text.strip().split("|")]
            if len(parts) < 4 or parts[0] not in PILAR_KEYWORDS or parts[1] not in ("brecha", "fortaleza", "contradiccion"):
                continue
            ev = []
            for c in block.citations:
                stype, sid, _, ref = sources[c.document_index]
                ev.append({"source_type": stype, "source_id": sid, "quote": c.cited_text, "ref": ref})
            out.append(Candidate(parts[1], parts[0], parts[2], "|".join(parts[3:]), ev))
        return out

    def strategy_turn(self, stage, context, history, user_message):
        if user_message is None:
            return scripted_strategy_turn(stage, context, history, None)
        system = (f"Eres un asistente de IA que guía a una empresa a definir su estrategia de IA. Etapa: {STAGE_LABELS[stage]}. "
                  f"Usa solo estos datos del diagnóstico: {context}. Si falta un dato, pregúntalo. Sé breve. "
                  "Cuando la persona dé un contenido concreto, responde en la primera línea con 'PROPUESTA: <texto>' y luego tu mensaje.")
        msgs = [{"role": h["author"] if h["author"] in ("user", "assistant") else "user", "content": h["text"]} for h in history]
        msgs.append({"role": "user", "content": user_message})
        r = self.client.messages.create(model=settings.anthropic_model, max_tokens=600, system=system, messages=msgs)
        text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        if text.startswith("PROPUESTA:"):
            first, _, rest = text.partition("\n")
            return Turn(rest.strip() or "¿Lo guarda o lo edita?", {"kind": STAGE_KIND[stage], "text": first[10:].strip(), "basis": None})
        return Turn(text)


def get_llm() -> LLM:
    return AnthropicLLM() if settings.llm_provider == "anthropic" else StubLLM()
