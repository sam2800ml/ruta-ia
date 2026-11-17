"""Interfaz del modelo de IA. La lógica de agentes solo conoce esta clase: el proveedor se cambia con RUTA_LLM_PROVIDER.

Implementaciones:
- StubLLM: determinista, sin red. Sirve para desarrollo y pruebas.
- AnthropicLLM, OpenAILLM, GroqLLM: bucle agéntico con tool calling nativo (ver agent_tools.py) — el modelo
  busca evidencia, propone hallazgos, se autocritica, y solo entonces se verifica cada cita contra el texto
  fuente real (_parse_and_verify). Ninguna acepta evidencia que no exista literalmente en documentos o transcripciones.
"""
import json
import re
from dataclasses import dataclass, field

try:
    from langsmith import traceable
except ImportError:
    def traceable(*_dargs, **_dkwargs):  # modo stub: no depende de langsmith para funcionar
        def _decorator(fn):
            return fn
        return _decorator

from .agent_tools import PILAR_KEYWORDS, TOOL_DEFS, _find_quote, build_sources, call_tool
from .config import settings

import os


def _tracing_ready() -> bool:
    """LANGSMITH_TRACING solo sirve si además hay una clave real: evita tracear sin autenticación."""
    return os.environ.get("LANGSMITH_TRACING", "").lower() == "true" and bool(os.environ.get("LANGSMITH_API_KEY"))


NEGATIVE = re.compile(r"\b(no tenemos|no existe|no hay|sin |carece|falta|no contamos)\b", re.I)
POSITIVE = re.compile(r"\b(contamos con|tenemos|existe una|existe un|cuenta con)\b", re.I)

MAX_TOOL_TURNS = 6
AGENT_SYSTEM = (
    "Eres el agente de diagnóstico de adopción de IA. Tienes herramientas para buscar evidencia real en los "
    "documentos y transcripciones de la empresa: úsalas antes de proponer cualquier hallazgo, nunca inventes "
    "contenido. Puedes llamar herramientas varias veces. Cuando ya tengas suficiente evidencia, entrega hasta 8 "
    'hallazgos como un arreglo JSON y nada más, uno por elemento: {"pilar":"...","tipo":"...","titulo":"...",'
    '"descripcion":"...","cita":"...","indice_fuente":0}. pilar ∈ strategy, infrastructure, data, governance, '
    "talent, culture. tipo ∈ brecha, fortaleza, contradiccion. Antes de incluir una cita, confírmala con la "
    "herramienta verificar_cita. No inventes datos que no estén en las fuentes."
)
AGENT_CRITIQUE = (
    "Revisa tu propia lista de hallazgos:\n{draft}\n"
    "Para cada uno, confirma otra vez que la cita sea textual (puedes volver a usar verificar_cita) y que el pilar "
    "e índice de fuente sean correctos. Si detectas un pilar importante sin evidencia (usa listar_vacios si hace "
    "falta), simplemente omite ese hallazgo en vez de inventarlo. Devuelve la lista final corregida en el mismo "
    "formato JSON, sin texto adicional."
)


def _parse_and_verify(text: str, sources: list) -> list["Candidate"]:
    """Único lugar donde se interpreta la respuesta final del agente y se verifica cada cita contra la fuente real.
    Esto es lo que de verdad impide inventar evidencia: no importa qué tan convencido esté el modelo de su propia cita."""
    try:
        items = json.loads(text[text.index("["):text.rindex("]") + 1])
    except (ValueError, json.JSONDecodeError):
        items = []
    out: list[Candidate] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        pillar, kind = item.get("pilar"), item.get("tipo")
        if pillar not in PILAR_KEYWORDS or kind not in ("brecha", "fortaleza", "contradiccion"):
            continue
        try:
            i = int(item.get("indice_fuente"))
        except (TypeError, ValueError):
            continue
        if not (0 <= i < len(sources)):
            continue
        stype, sid, src_text, ref = sources[i]
        found = _find_quote(str(item.get("cita", "")), src_text)
        if not found:
            continue
        out.append(Candidate(kind, pillar, str(item.get("titulo", "")), str(item.get("descripcion", "")),
                              [{"source_type": stype, "source_id": sid, "quote": found, "ref": ref}]))
    return out[:8]


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
        sources = build_sources(fragments, segments)
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
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        if _tracing_ready():
            from langsmith.wrappers import wrap_anthropic
            client = wrap_anthropic(client)
        self.client = client

    @traceable(name="agente_diagnostico.propose_findings", run_type="chain")
    def propose_findings(self, fragments, segments):
        """Bucle agéntico: el modelo busca evidencia con herramientas, propone hallazgos, se autocritica,
        y solo entonces se verifica cada cita contra el texto fuente real (_parse_and_verify)."""
        sources = build_sources(fragments, segments)
        if not sources:
            return []
        tools = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in TOOL_DEFS]
        msgs = [{"role": "user", "content": f"Hay {len(sources)} fuentes numeradas de [0] a [{len(sources) - 1}]. "
                 "Investígalas con las herramientas antes de proponer hallazgos."}]
        draft = ""
        for _ in range(MAX_TOOL_TURNS):
            resp = self.client.messages.create(model=settings.anthropic_model, max_tokens=1500,
                                               system=AGENT_SYSTEM, tools=tools, messages=msgs)
            tool_uses = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
            if not tool_uses:
                draft = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
                break
            msgs.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})
            results = [{"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(call_tool(sources, tu.name, tu.input))}
                       for tu in tool_uses]
            msgs.append({"role": "user", "content": results})
        msgs.append({"role": "user", "content": AGENT_CRITIQUE.format(draft=draft)})
        critique = self.client.messages.create(model=settings.anthropic_model, max_tokens=1500, system=AGENT_SYSTEM, messages=msgs)
        final_text = "".join(b.text for b in critique.content if getattr(b, "type", "") == "text") or draft
        return _parse_and_verify(final_text, sources)

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


class OpenAICompatibleLLM(LLM):
    """Base para proveedores con API tipo OpenAI (Chat Completions): OpenAI y Groq.
    Sin "citations" nativas como Anthropic, así que se le pide al modelo citar texto literal
    y se verifica contra la fuente antes de aceptar el hallazgo (ver _find_quote)."""
    base_url: str | None = None

    def __init__(self, api_key: str, model: str):
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=self.base_url)
        if _tracing_ready():
            from langsmith.wrappers import wrap_openai
            client = wrap_openai(client)
        self.client = client
        self.model = model

    @traceable(name="agente_diagnostico.propose_findings", run_type="chain")
    def propose_findings(self, fragments, segments):
        """Bucle agéntico vía tool calling nativo: el modelo busca evidencia, propone, se autocritica,
        y solo entonces se verifica cada cita contra el texto fuente real (_parse_and_verify)."""
        sources = build_sources(fragments, segments)
        if not sources:
            return []
        tools = [{"type": "function", "function": t} for t in TOOL_DEFS]
        msgs = [{"role": "system", "content": AGENT_SYSTEM},
                {"role": "user", "content": f"Hay {len(sources)} fuentes numeradas de [0] a [{len(sources) - 1}]. "
                 "Investígalas con las herramientas antes de proponer hallazgos."}]
        draft = ""
        for _ in range(MAX_TOOL_TURNS):
            resp = self.client.chat.completions.create(model=self.model, max_tokens=1500, messages=msgs, tools=tools)
            msg = resp.choices[0].message
            if not msg.tool_calls:
                draft = msg.content or ""
                break
            msgs.append({"role": "assistant", "content": msg.content,
                         "tool_calls": [{"id": tc.id, "type": "function",
                                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                        for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(call_tool(sources, tc.function.name, args))})
        msgs.append({"role": "user", "content": AGENT_CRITIQUE.format(draft=draft)})
        critique = self.client.chat.completions.create(model=self.model, max_tokens=1500, messages=msgs)
        final_text = critique.choices[0].message.content or draft
        return _parse_and_verify(final_text, sources)

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


def get_llm(provider: str | None = None) -> LLM:
    return _PROVIDERS.get(provider or settings.llm_provider, StubLLM)()
