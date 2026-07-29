from pathlib import Path

from app.core.text import safe_filename, sha256_text


class LocalFileStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put_document(self, document_id: int, filename: str, content: str) -> str:
        safe = safe_filename(filename)
        relative = Path("documents") / str(document_id) / "original" / safe
        target = self._resolve(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return relative.as_posix()

    def read(self, storage_key: str) -> str:
        return self._resolve(Path(storage_key)).read_text(encoding="utf-8")

    def read_range(self, storage_key: str, start: int, end: int | None) -> tuple[str, int, int, int]:
        content = self.read(storage_key)
        safe_start = max(0, min(start, len(content)))
        safe_end = len(content) if end is None else max(safe_start, min(end, len(content)))
        return content[safe_start:safe_end], safe_start, safe_end, len(content)

    def exists(self, storage_key: str) -> bool:
        return self._resolve(Path(storage_key)).is_file()

    def delete(self, storage_key: str) -> None:
        target = self._resolve(Path(storage_key))
        if target.exists():
            target.unlink()

    def content_hash(self, content: str) -> str:
        return sha256_text(content)

    def _resolve(self, relative: Path) -> Path:
        target = (self.root / relative).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError("invalid storage path")
        return target
