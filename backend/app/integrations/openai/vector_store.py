from dataclasses import dataclass
from pathlib import Path

from app.integrations.openai.client import get_openai_client


@dataclass
class VectorSearchItem:
    file_id: str
    filename: str
    score: float
    content: str


class OpenAIVectorStoreGateway:
    def __init__(self, vector_store_id: str | None):
        self.vector_store_id = vector_store_id

    @property
    def configured(self) -> bool:
        # OpenAI Vector Store IDs use the `vs_` prefix. Treat a placeholder or
        # malformed env value as unavailable so local analysis can continue.
        return get_openai_client() is not None and (not self.vector_store_id or self.vector_store_id.startswith("vs_"))

    def ensure_store(self) -> str | None:
        client = get_openai_client()
        if client is None:
            return None
        if self.vector_store_id:
            return self.vector_store_id
        store = client.vector_stores.create(name="JSH Second Brain")
        self.vector_store_id = store.id
        return store.id

    def upload_and_poll(self, path: Path, filename: str) -> tuple[str, str]:
        client = get_openai_client()
        store_id = self.ensure_store()
        if client is None or store_id is None:
            raise RuntimeError("OpenAI Vector Store is not configured")
        # Keep provider latency bounded. Local SQLite/FTS analysis is the
        # authoritative fallback when indexing is unavailable.
        client = client.with_options(timeout=20.0, max_retries=0)
        with path.open("rb") as handle:
            vector_file = client.vector_stores.files.upload_and_poll(vector_store_id=store_id, file=handle, poll_interval_ms=1000)
        return vector_file.id, getattr(vector_file, "status", "completed")

    def search(self, query: str, limit: int = 3) -> list[VectorSearchItem]:
        client = get_openai_client()
        if client is None or not self.vector_store_id:
            return []
        response = client.vector_stores.search(vector_store_id=self.vector_store_id, query=query, max_num_results=limit, rewrite_query=True)
        items: list[VectorSearchItem] = []
        for item in getattr(response, "data", []) or []:
            parts = getattr(item, "content", []) or []
            text = "\n".join(getattr(part, "text", "") for part in parts if getattr(part, "text", ""))
            items.append(VectorSearchItem(str(getattr(item, "file_id", "")), str(getattr(item, "filename", "")), float(getattr(item, "score", 0.0)), text))
        return items

    def delete(self, file_id: str) -> None:
        client = get_openai_client()
        if client is not None and self.vector_store_id and file_id:
            client.vector_stores.files.delete(vector_store_id=self.vector_store_id, file_id=file_id)
