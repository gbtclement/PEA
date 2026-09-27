import logging
from collections.abc import Callable, Iterator
from typing import Any, Protocol

import anthropic

from app.services.assistant.catalog import FALLBACK_BETA, AssistantModel, Usage
from app.services.assistant.tools import TOOL_SPECS, tool_label

logger = logging.getLogger(__name__)
REFUSAL = "Claude a refusé de répondre à cette demande. Reformulez votre question."
TRUNCATED = "La réponse a été coupée car elle était trop longue."
TOO_MANY_STEPS = "L'assistant a atteint la limite d'étapes pour cette question. Posez une question plus précise."
UNAVAILABLE = "Le service Claude est momentanément indisponible. Réessayez dans un instant."


class LLM(Protocol):
    def stream(self, **params: Any) -> Any: ...


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, anthropic.AuthenticationError):
        return "Clé API invalide ou révoquée. Vérifiez-la dans les Réglages."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "Cette clé API n'a pas accès au modèle choisi. Changez de modèle dans les Réglages."
    if isinstance(exc, anthropic.NotFoundError):
        return "Modèle introuvable. Choisissez un autre modèle dans les Réglages."
    if isinstance(exc, anthropic.RateLimitError):
        return "Limite d'utilisation de l'API atteinte. Patientez quelques minutes puis réessayez."
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.InternalServerError)):
        return UNAVAILABLE
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code == 402:
            return "Crédit insuffisant sur votre compte Anthropic. Rechargez-le sur console.anthropic.com."
        if exc.status_code >= 500:
            return UNAVAILABLE
        return f"L'API Claude a refusé la requête (erreur {exc.status_code})."
    return "Erreur inattendue de l'assistant."


class ChatRun:
    """Un tour de conversation : appels successifs à Claude tant qu'il demande des outils."""

    def __init__(self, llm: LLM, *, model: AssistantModel, system: str, history: list[dict],
                 execute_tool: Callable[[str, dict, str], dict], max_tokens: int, max_rounds: int) -> None:
        self.llm, self.model, self.system, self.history = llm, model, system, history
        self.execute_tool, self.max_tokens, self.max_rounds = execute_tool, max_tokens, max_rounds
        self.parts: list[str] = []
        self.tools: list[str] = []
        self.usage = Usage()
        self.completed = False
        self.error: str | None = None

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def _params(self, messages: list) -> dict:
        tools = [*TOOL_SPECS, {"type": self.model.web_search_type, "name": "web_search", "max_uses": 3}]
        params: dict = dict(model=self.model.id, max_tokens=self.max_tokens, system=self.system,
                            messages=messages, tools=tools)
        if self.model.adaptive_thinking:
            params["thinking"] = {"type": "adaptive"}
        if self.model.fallback:
            params["betas"] = [FALLBACK_BETA]
            params["extra_body"] = {"fallbacks": self.model.fallback}
        return params

    def events(self) -> Iterator[dict]:
        messages: list = list(self.history)
        try:
            for _ in range(self.max_rounds):
                new_round = True
                with self.llm.stream(**self._params(messages)) as stream:
                    for event in stream:
                        if event.type == "text" and event.text:
                            if new_round and self.parts and not self.text.endswith("\n"):
                                self.parts.append("\n\n")  # sépare le texte de deux tours
                                yield {"type": "text", "text": "\n\n"}
                            new_round = False
                            self.parts.append(event.text)
                            yield {"type": "text", "text": event.text}
                        elif event.type == "content_block_start" and event.content_block.type in ("tool_use", "server_tool_use"):
                            name = event.content_block.name
                            self.tools.append(name)
                            yield {"type": "tool", "name": name, "label": tool_label(name)}
                    final = stream.get_final_message()
                self.usage.add(final.usage)
                if final.stop_reason == "refusal":
                    self.error = REFUSAL
                    return
                if final.stop_reason == "pause_turn":
                    messages.append({"role": "assistant", "content": final.content})
                    continue
                if final.stop_reason == "max_tokens":
                    self.error = TRUNCATED
                    return
                tool_uses = [b for b in final.content if b.type == "tool_use"]
                if not tool_uses:
                    self.completed = True
                    return
                messages.append({"role": "assistant", "content": final.content})
                messages.append({"role": "user", "content": [self.execute_tool(b.name, b.input, b.id) for b in tool_uses]})
            self.error = TOO_MANY_STEPS
        except Exception as exc:  # erreurs API ou réseau : message lisible, sans détails techniques
            logger.warning("Assistant error: %s", type(exc).__name__)
            self.error = friendly_error(exc)
