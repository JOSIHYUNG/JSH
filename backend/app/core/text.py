import hashlib
import re
from collections import Counter
from pathlib import PurePath


def normalize_text(value: str) -> str:
    return re.sub(r"\r\n?", "\n", value).strip()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_name(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", value.casefold())


def preview(value: str, limit: int = 500) -> str:
    value = value.strip()
    return value if len(value) <= limit else value[: max(0, limit - 1)].rstrip() + "…"


def safe_filename(filename: str | None, fallback: str = "document.txt") -> str:
    name = PurePath(filename or fallback).name.replace("\x00", "")
    name = re.sub(r"[^0-9A-Za-z가-힣._ -]", "_", name).strip(" .")
    return (name or fallback)[:255]


def fallback_keywords(text: str, limit: int = 12) -> list[str]:
    tokens = re.findall(r"[가-힣A-Za-z][가-힣A-Za-z0-9_-]{1,}", text.casefold())
    stopwords = {
        "그리고", "그러나", "대한", "에서", "으로", "있는", "하는", "또는", "따라", "통해", "대해", "경우",
        "있다", "없다", "한다", "된다", "했다", "하는", "되는", "높다", "높은", "낮다", "낮은", "중요하다",
        "중요한", "실제", "다른", "전체", "관련", "필요", "사용", "설명", "구성", "포함", "확인", "가능",
        "증가", "감소", "제공", "수준", "안정적", "보유", "발생", "의미", "the", "and", "this", "that", "with", "from",
    }
    counts = Counter(token for token in tokens if token not in stopwords and not token.isdigit())
    ranked = sorted(counts.items(), key=lambda item: (item[1] * min(len(item[0]), 12), len(item[0])), reverse=True)
    return [token for token, _ in ranked[:limit]]


def chunk_text(text: str, chunk_size: int = 24_000, overlap: int = 500) -> list[tuple[int, int, str]]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")
    result: list[tuple[int, int, str]] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            boundary = max(normalized.rfind("\n\n", start, end), normalized.rfind("\n", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary + (2 if normalized.startswith("\n\n", boundary) else 1)
        content = normalized[start:end]
        if content.strip():
            result.append((start, end, content))
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return result
