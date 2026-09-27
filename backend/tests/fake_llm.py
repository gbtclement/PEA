from types import SimpleNamespace


def text_turn(*chunks: str, stop_reason: str = "end_turn", input_tokens: int = 100, output_tokens: int = 50):
    return {"events": [SimpleNamespace(type="text", text=c) for c in chunks],
            "content": [SimpleNamespace(type="text", text="".join(chunks))], "stop_reason": stop_reason,
            "usage": SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)}


def tool_turn(name: str, tool_input: dict, tool_id: str = "toolu_1", server: bool = False):
    block_type = "server_tool_use" if server else "tool_use"
    block = SimpleNamespace(type=block_type, name=name, input=tool_input, id=tool_id)
    return {"events": [SimpleNamespace(type="content_block_start", content_block=block)], "content": [block],
            "stop_reason": "pause_turn" if server else "tool_use",
            "usage": SimpleNamespace(input_tokens=100, output_tokens=20)}


def error_turn(exc: Exception, *chunks: str):
    return {"events": [SimpleNamespace(type="text", text=c) for c in chunks], "raise": exc}


class _Stream:
    def __init__(self, turn):
        self.turn = turn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        yield from self.turn["events"]
        if "raise" in self.turn:
            raise self.turn["raise"]

    def get_final_message(self):
        return SimpleNamespace(content=self.turn["content"], stop_reason=self.turn["stop_reason"], usage=self.turn["usage"])


class FakeLLM:
    """Remplace client.beta.messages : rejoue des tours scriptés et garde les paramètres reçus."""

    def __init__(self, *turns):
        self.turns = list(turns)
        self.calls: list[dict] = []
        self.api_keys: list[str] = []

    def stream(self, **params):
        self.calls.append({**params, "messages": list(params["messages"])})
        return _Stream(self.turns.pop(0))
