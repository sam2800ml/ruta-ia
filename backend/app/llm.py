"""Interfaz del modelo de IA. La lógica de agentes solo conoce esta clase: el proveedor se cambia con RUTA_LLM_PROVIDER.

Implementaciones:
- StubLLM: determinista, sin red. Sirve para desarrollo y pruebas.
- AnthropicLLM: usa Claude, con citas nativas (Citations API).
- OpenAILLM / GroqLLM: comparten la API tipo OpenAI; sin citas nativas, así que se le pide al
  modelo una cita textual y se verifica contra la fuente antes de aceptar el hallazgo.
Ninguna acepta evidencia que no exista literalmente en los documentos o transcripciones.
"""
import re
from dataclasses import dataclass, field

from langsmith import traceable

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
        from langsmith.wrappers import wrap_anthropic
        # wrap_anthropic solo envía trazas si LANGSMITH_TRACING=true; si no, es transparente.
        self.client = wrap_anthropic(anthropic.Anthropic(api_key=settings.anthropic_api_key))

    @traceable(name="agente_diagnostico.propose_findings", run_type="chain")
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

    @traceable(name="agente_estrategia.strategy_turn", run_type="chain")
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


def _find_quote(quote: str, source: str) -> str | None:
    """Confirma que la cita exista literalmente en la fuente (ignora mayúsculas y espacios de más).
    Si el modelo no puede señalar un fragmento real, el hallazgo se descarta en vez de inventarlo."""
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    q, s = norm(quote), norm(source)
    if not q or q.lower() not in s.lower():
        return None
    i = s.lower().index(q.lower())
    return s[i:i + len(q)]


class OpenAICompatibleLLM(LLM):
    """Base para proveedores con API tipo OpenAI (Chat Completions): OpenAI y Groq.
    Sin "citations" nativas como Anthropic, así que se le pide al modelo citar texto literal
    y se verifica contra la fuente antes de aceptar el hallazgo (ver _find_quote)."""
    base_url: str | None = None

    def __init__(self, api_key: str, model: str):
        from openai import OpenAI
        from langsmith.wrappers import wrap_openai
        self.client = wrap_openai(OpenAI(api_key=api_key, base_url=self.base_url))
        self.model = model

    @traceable(name="agente_diagnostico.propose_findings", run_type="chain")
    def propose_findings(self, fragments, segments):
        sources = ([("document", f["id"], f["text"], {"document": f["document"], "page": f["page"]}) for f in fragments] +
                   [("transcript", s["id"], s["text"], {"transcript": s["transcript"], "start_sec": s["start_sec"]}) for s in segments])
        if not sources:
            return []
        numbered = "\n".join(f"[{i}] {t}" for i, (_, _, t, _) in enumerate(sources))
        system = ("Eres consultor de adopción de IA. Con las fuentes numeradas que te dan, lista hasta 8 hallazgos, una línea por "
                  "hallazgo, con el formato exacto: pilar|tipo|título|descripción|cita textual|índice de fuente. "
                  "pilar ∈ strategy, infrastructure, data, governance, talent, culture. tipo ∈ brecha, fortaleza, contradiccion. "
                  "La 'cita textual' debe ser una copia EXACTA de un fragmento de la fuente indicada, sin parafrasear. "
                  "No agregues texto fuera de ese formato. No inventes datos que no estén en las fuentes.")
        resp = self.client.chat.completions.create(model=self.model, max_tokens=2000,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": numbered}])
        text = resp.choices[0].message.content or ""
        out: list[Candidate] = []
        for line in text.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 6:
                continue
            pillar, kind, title, desc, quote, idx = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
            if pillar not in PILAR_KEYWORDS or kind not in ("brecha", "fortaleza", "contradiccion"):
                continue
            try:
                i = int(idx)
            except ValueError:
                continue
            if not (0 <= i < len(sources)):
                continue
            stype, sid, src_text, ref = sources[i]
            found = _find_quote(quote, src_text)
            if not found:
                continue
            out.append(Candidate(kind, pillar, title, desc, [{"source_type": stype, "source_id": sid, "quote": found, "ref": ref}]))
        return out[:8]

    @traceable(name="agente_estrategia.strategy_turn", run_type="chain")
    def strategy_turn(self, stage, context, history, user_message):
        if user_message is None:
            return scripted_strategy_turn(stage, context, history, None)
        system = (f"Eres un asistente de IA que guía a una empresa a definir su estrategia de IA. Etapa: {STAGE_LABELS[stage]}. "
                  f"Usa solo estos datos del diagnóstico: {context}. Si falta un dato, pregúntalo. Sé breve. "
                  "Cuando la persona dé un contenido concreto, responde en la primera línea con 'PROPUESTA: <texto>' y luego tu mensaje.")
        msgs = [{"role": "system", "content": system}]
        msgs += [{"role": h["author"] if h["author"] in ("user", "assistant") else "user", "content": h["text"]} for h in history]
        msgs.append({"role": "user", "content": user_message})
        r = self.client.chat.completions.create(model=self.model, max_tokens=600, messages=msgs)
        text = r.choices[0].message.content or ""
        if text.startswith("PROPUESTA:"):
            first, _, rest = text.partition("\n")
            return Turn(rest.strip() or "¿Lo guarda o lo edita?", {"kind": STAGE_KIND[stage], "text": first[10:].strip(), "basis": None})
        return Turn(text)


class OpenAILLM(OpenAICompatibleLLM):
    name = "openai"

    def __init__(self):
        super().__init__(settings.openai_api_key, settings.openai_model)


class GroqLLM(OpenAICompatibleLLM):
    name = "groq"
    base_url = "https://api.groq.com/openai/v1"

    def __init__(self):
        super().__init__(settings.groq_api_key, settings.groq_model)


_PROVIDERS = {"stub": StubLLM, "anthropic": AnthropicLLM, "openai": OpenAILLM, "groq": GroqLLM}


def get_llm() -> LLM:
    return _PROVIDERS.get(settings.llm_provider, StubLLM)()
