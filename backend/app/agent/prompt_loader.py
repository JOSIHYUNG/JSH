import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROMPT_ROOT = Path(__file__).resolve().parents[1] / "prompts" / "agent"


@dataclass(frozen=True)
class PromptBundle:
    system: str
    tool_policy: str
    tools: list[dict[str, Any]]
    answer_contract: dict[str, Any]
    version: str


class PromptLoader:
    def __init__(self, root: Path = PROMPT_ROOT):
        self.root = root

    def load(self) -> PromptBundle:
        system = self._read_text("system.md")
        tool_policy = "\n\n".join([
            self._read_text("tool-policy.md"),
            self._read_text("tools/web_search.md"),
        ])
        tools_config = self._read_json("tool-config.json")
        answer_contract = self._read_json("answer-contract.json")
        tools = tools_config.get("tools")
        if not isinstance(tools, list) or not tools:
            raise ValueError("Agent tool-config.json must define a non-empty tools list")
        if answer_contract.get("type") != "object":
            raise ValueError("Agent answer-contract.json must define an object schema")
        version_source = "\n".join([system, tool_policy, json.dumps(tools_config, sort_keys=True), json.dumps(answer_contract, sort_keys=True)])
        version = hashlib.sha256(version_source.encode("utf-8")).hexdigest()[:16]
        return PromptBundle(system, tool_policy, tools, answer_contract, version)

    def _read_text(self, name: str) -> str:
        path = self.root / name
        if not path.is_file():
            raise FileNotFoundError(f"Agent prompt file is missing: {name}")
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            raise ValueError(f"Agent prompt file is empty: {name}")
        return value

    def _read_json(self, name: str) -> dict[str, Any]:
        path = self.root / name
        if not path.is_file():
            raise FileNotFoundError(f"Agent JSON contract is missing: {name}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Agent JSON contract must be an object: {name}")
        return value
