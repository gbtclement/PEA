from dataclasses import dataclass

from app.core.config import get_settings

FALLBACK_BETA = "server-side-fallback-2026-07-01"
WEB_SEARCH_COST = 0.01  # 10 $ les 1 000 recherches


@dataclass(frozen=True)
class AssistantModel:
    id: str
    label: str
    input_per_mtok: float
    output_per_mtok: float
    adaptive_thinking: bool = True
    fallback: str | None = None
    web_search_type: str = "web_search_20260209"


MODELS: tuple[AssistantModel, ...] = (
    AssistantModel("claude-opus-5", "Claude Opus 5 (recommandé)", 5.0, 25.0, fallback="default"),
    AssistantModel("claude-sonnet-5", "Claude Sonnet 5 (plus rapide)", 3.0, 15.0),
    AssistantModel("claude-haiku-4-5", "Claude Haiku 4.5 (économique)", 1.0, 5.0, adaptive_thinking=False,
                   web_search_type="web_search_20250305"),
    AssistantModel("claude-fable-5-1", "Claude Fable 5.1 (le plus puissant, plus cher)", 10.0, 50.0),
)
_BY_ID = {m.id: m for m in MODELS}


def get_model(model_id: str | None) -> AssistantModel:
    return _BY_ID.get(model_id or "") or _BY_ID.get(get_settings().assistant_model) or MODELS[0]


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    web_searches: int = 0

    def add(self, usage: object) -> None:
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.cache_write_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        server = getattr(usage, "server_tool_use", None)
        self.web_searches += (getattr(server, "web_search_requests", 0) or 0) if server else 0


def estimate_cost(model: AssistantModel, usage: Usage) -> float:
    """Coût estimé en dollars (tarifs publics ; lecture du cache 0,1 x, écriture 1,25 x l'entrée)."""
    per_input = model.input_per_mtok / 1_000_000
    return round(
        usage.input_tokens * per_input
        + usage.cache_read_tokens * per_input * 0.1
        + usage.cache_write_tokens * per_input * 1.25
        + usage.output_tokens * model.output_per_mtok / 1_000_000
        + usage.web_searches * WEB_SEARCH_COST,
        6,
    )
