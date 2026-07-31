import json
from dataclasses import dataclass
from typing import Any

from app.agent.prompt_loader import PromptBundle
from app.core.config import get_settings
from app.integrations.openai.client import get_openai_client


@dataclass
class AgentModelResponse:
    raw: Any
    output: list[dict[str, Any]]
    output_text: str


class AgentResponsesGateway:
    @property
    def configured(self) -> bool:
        return get_openai_client() is not None

    def create(self, input_items: list[dict[str, Any]], bundle: PromptBundle, tool_schemas: list[dict[str, Any]]) -> AgentModelResponse:
        client = get_openai_client()
        if client is None:
            raise RuntimeError("OpenAI API is not configured")
        settings = get_settings()
        tools = [*tool_schemas, {"type": "web_search", "search_context_size": settings.agent_web_search_context_size}]
        response = client.with_options(timeout=settings.question_timeout_seconds).responses.create(
            model=settings.effective_agent_model,
            reasoning={"effort": "low"},
            text={
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": "agent_answer",
                    "strict": True,
                    "schema": bundle.answer_contract,
                },
            },
            store=False,
            include=["reasoning.encrypted_content", "web_search_call.action.sources"],
            parallel_tool_calls=False,
            tool_choice="auto",
            instructions=f"{bundle.system}\n\n{bundle.tool_policy}",
            input=input_items,
            tools=tools,
            max_output_tokens=settings.agent_max_output_tokens,
        )
        return AgentModelResponse(response, self.output_items(response), str(getattr(response, "output_text", "") or "").strip())

    @staticmethod
    def output_items(response: Any) -> list[dict[str, Any]]:
        # Response output objects are not identical to input items. In particular,
        # `status` is a response-side field and the Responses API rejects it when
        # the previous output is supplied as the next request's input.
        items: list[dict[str, Any]] = []
        for item in (getattr(response, "output", None) or []):
            normalized = _as_dict(item)
            normalized.pop("status", None)
            items.append(normalized)
        return items

    @staticmethod
    def function_calls(response: AgentModelResponse) -> list[dict[str, Any]]:
        return [item for item in response.output if item.get("type") == "function_call"]

    @staticmethod
    def web_search_calls(response: AgentModelResponse) -> list[dict[str, Any]]:
        return [item for item in response.output if item.get("type") == "web_search_call"]

    @staticmethod
    def web_sources(response: AgentModelResponse) -> list[dict[str, str]]:
        sources: list[dict[str, str]] = []
        for item in response.output:
            for source in _source_items(item):
                url = str(source.get("url") or source.get("link") or "").strip()
                if not url.startswith("https://"):
                    continue
                sources.append({"url": url, "title": str(source.get("title") or "Web source")[:500], "publisher": str(source.get("publisher") or "")[:255]})
        unique: dict[str, dict[str, str]] = {}
        for source in sources:
            unique.setdefault(source["url"], source)
        return list(unique.values())

    @staticmethod
    def web_query(call: dict[str, Any]) -> str:
        action = call.get("action") or {}
        if isinstance(action, dict):
            query = action.get("query") or action.get("queries")
            if isinstance(query, list):
                return " · ".join(str(item) for item in query)
            return str(query or "")
        return ""


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return {}


def _source_items(item: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for annotation in _walk_annotations(item):
        if annotation.get("type") in {"url_citation", "url_citation_annotation"}:
            output.append(annotation)
    action = item.get("action")
    if isinstance(action, dict):
        for source in action.get("sources", []) or []:
            if isinstance(source, dict):
                output.append(source)
    return output


def _walk_annotations(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        result: list[dict[str, Any]] = []
        if isinstance(value.get("annotations"), list):
            result.extend(item for item in value["annotations"] if isinstance(item, dict))
        for child in value.values():
            result.extend(_walk_annotations(child))
        return result
    if isinstance(value, list):
        result: list[dict[str, Any]] = []
        for child in value:
            result.extend(_walk_annotations(child))
        return result
    return []
