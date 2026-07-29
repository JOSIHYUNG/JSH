from dataclasses import dataclass
from typing import Literal, TypeVar

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.integrations.openai.client import get_openai_client


ConceptType = Literal[
    "organization",
    "organization_unit",
    "person",
    "country",
    "region",
    "place",
    "technology",
    "equipment",
    "system",
    "project_program",
    "policy_law",
    "event",
    "document",
]


class DocumentAnalysisSchema(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=1000)
    keywords: list[str] = Field(min_length=1, max_length=32)


class ConceptExtractionSchema(BaseModel):
    concept_type: ConceptType
    canonical_name: str = Field(min_length=1, max_length=255)
    english_name: str | None = Field(default=None, max_length=255)
    abbreviation: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=160)
    mention: str = Field(min_length=1, max_length=255)
    mention_start: int | None = Field(default=None, ge=0)
    mention_end: int | None = Field(default=None, ge=0)
    confidence: float = Field(ge=0, le=1)


class ChunkConceptExtractionSchema(BaseModel):
    concepts: list[ConceptExtractionSchema] = Field(default_factory=list, max_length=64)


class RelationExtractionSchema(BaseModel):
    source_mention: str = Field(min_length=1, max_length=255)
    target_mention: str = Field(min_length=1, max_length=255)
    relation_type: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


class ChunkRelationExtractionSchema(BaseModel):
    relations: list[RelationExtractionSchema] = Field(default_factory=list, max_length=96)


@dataclass
class DocumentAnalysisOutput:
    title: str
    summary: str
    keywords: list[str]


@dataclass
class ExtractedConcept:
    concept_type: str
    canonical_name: str
    english_name: str | None
    abbreviation: str | None
    description: str
    mention: str
    mention_start: int | None
    mention_end: int | None
    confidence: float


@dataclass
class ExtractedRelation:
    source_mention: str
    target_mention: str
    relation_type: str
    explanation: str
    confidence: float


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class OpenAIResponsesGateway:
    def __init__(self):
        self.settings = get_settings()

    def analyze_document(self, filename: str, content: str) -> DocumentAnalysisOutput:
        client = get_openai_client()
        if client is None:
            return self._fallback_document_analysis(filename, content)

        prompt = f"파일명: {filename}\n문서 원문:\n{self._bounded_text(content, 180_000)}"
        instructions = """
문서의 표시 제목, 핵심 요약, 검색용 키워드를 추출한다.
규칙:
- title은 문서의 실제 주제를 반영하고 파일명을 그대로 복사하지 않는다.
- summary는 문서의 목적·핵심 주장·중요한 수치나 범위를 2~4문장으로 요약한다.
- keywords는 12~24개를 목표로 한다. 고유명사, 조직·인물·지역·기술·장비·정책·사건,
  핵심 주제와 동의어를 포함하고 한국어·영문·약어가 원문에 있으면 함께 포함한다.
- 조사, 접속사, 일반적인 서술어(있다, 한다, 높다, 낮다, 중요하다 등), 너무 일반적인 단어는 제외한다.
- 키워드는 1~5단어의 검색어로 작성하며 중복·동의어 반복을 최소화한다.
한국어로 출력한다.
"""
        try:
            parsed = self._parse(DocumentAnalysisSchema, instructions, prompt, max_output_tokens=2048)
        except Exception:
            return self._fallback_document_analysis(filename, content)
        return DocumentAnalysisOutput(parsed.title.strip(), parsed.summary.strip(), self._clean_keywords(parsed.keywords))

    def extract_concepts(self, chunk_index: int, content: str) -> list[ExtractedConcept]:
        client = get_openai_client()
        if client is None:
            return []
        instructions = """
주어진 문서 청크에서 지식 그래프에 유의미한 모든 개념을 추출한다.
개념 분류:
organization=정부기관·기업·군·연구기관·대학·부서·국제기구,
organization_unit=사령부·부대·연구소·부서 등 상위 조직의 단위,
person=인물·연구자·정치인·지휘관·저자,
country=국가·국가 그룹·동맹, region=도시·주·도·지역·전역·해역·국경,
place=기지·공항·항구·시설·특정 장소, technology=기술·알고리즘·소프트웨어·통신·센서 기술,
equipment=무기·차량·항공기·함정·드론·센서·장비,
system=방어체계·정보체계·무기체계·운영체계,
project_program=사업·프로젝트·개발·조달 프로그램,
policy_law=정책·법률·규정·지침·교리,
event=전쟁·분쟁·작전·회의·사고·발표·시험,
document=보고서·논문·법안·공식 문서·데이터셋.
규칙:
- 청크에 실제로 언급되거나 명확히 설명된 개념만 추출하고 추측하지 않는다.
- 개념별 설명은 무엇인지 한 문장 이내로 짧게 쓴다.
- canonical_name은 한국어 표준명, english_name은 원문에 있거나 확실한 영문명,
  abbreviation은 원문에 있거나 널리 쓰이는 약어를 작성한다. 모르면 null이다.
- mention은 청크 원문에 실제로 등장한 표현을 그대로 작성한다.
- mention_start/end는 청크 내부 문자 위치이며 불확실하면 null이다.
- 중요 개념을 누락하지 않도록 최대한 많이 추출하되 일반 명사·서술어는 제외한다.
- 동일 개념의 반복 언급은 하나로 합친다.
"""
        try:
            parsed = self._parse(
                ChunkConceptExtractionSchema,
                instructions,
                f"chunk_index={chunk_index}\n청크 원문:\n{content}",
                max_output_tokens=8192,
            )
        except Exception:
            return []
        return [self._concept_from_schema(item, content) for item in parsed.concepts]

    def extract_relations(self, chunk_index: int, content: str, concepts: list[ExtractedConcept]) -> list[ExtractedRelation]:
        client = get_openai_client()
        if client is None or len(concepts) < 2:
            return []
        concept_context = [
            {
                "mention": concept.mention,
                "canonical_name": concept.canonical_name,
                "english_name": concept.english_name,
                "abbreviation": concept.abbreviation,
                "concept_type": concept.concept_type,
            }
            for concept in concepts
        ]
        instructions = """
문서 청크와 추출된 개념 목록을 바탕으로 개념 사이의 직접적이고 근거가 있는 관계를 모두 추출한다.
규칙:
- 청크 원문에서 확인되는 관계만 추출하고 배경지식으로 추측하지 않는다.
- source_mention과 target_mention은 아래 개념 목록의 mention/canonical_name/english_name/abbreviation 중 하나를 사용한다.
- relation_type은 짧고 재사용 가능한 동사형 또는 명사형으로 쓴다(예: 개발, 보유, 소속, 위치, 참여, 규제, 사용).
- explanation은 청크의 근거를 한 문장으로 짧게 설명한다.
- 동일한 쌍의 중복 관계는 합친다.
"""
        try:
            parsed = self._parse(
                ChunkRelationExtractionSchema,
                instructions,
                f"chunk_index={chunk_index}\n개념 목록:\n{concept_context}\n청크 원문:\n{content}",
                max_output_tokens=6144,
            )
        except Exception:
            return []
        return [
            ExtractedRelation(
                source_mention=item.source_mention.strip(),
                target_mention=item.target_mention.strip(),
                relation_type=item.relation_type.strip() or "related",
                explanation=item.explanation.strip(),
                confidence=self._score(item.confidence),
            )
            for item in parsed.relations
            if item.source_mention.strip() != item.target_mention.strip()
        ]

    def grounded_answer(self, question: str, evidence: list[tuple[str, str]]) -> str:
        client = get_openai_client()
        if client is None:
            return "AI 답변을 생성하려면 `backend/.env`에 `OPENAI_API_KEY`를 입력하세요.\n\n관련 근거:\n" + "\n\n".join(f"[{key}] {text[:500]}" for key, text in evidence)
        context = "\n\n".join(f"[{key}] {text}" for key, text in evidence)
        try:
            response = client.responses.create(model=self.settings.openai_chat_model, reasoning={"effort": "low"}, text={"verbosity": "low"}, store=False, instructions="제공된 개인 지식 근거만 사용해 한국어로 답한다. 근거에 없는 사실은 추정하지 않는다. 문장 끝에 실제 사용한 근거 키 [S1] 형식을 붙인다. 근거가 부족하면 부족하다고 명시한다.", input=f"질문: {question}\n\n근거:\n{context}")
            return response.output_text.strip()
        except Exception:
            return "AI 응답을 일시적으로 생성하지 못해 관련 근거를 표시합니다.\n\n" + "\n\n".join(f"[{key}] {text[:500]}" for key, text in evidence)

    def _parse(self, schema: type[SchemaT], instructions: str, input_text: str, max_output_tokens: int) -> SchemaT:
        client = get_openai_client()
        if client is None:
            raise RuntimeError("OpenAI client is not configured")
        response = client.responses.parse(
            model=self.settings.openai_chat_model,
            reasoning={"effort": "low"},
            text={"verbosity": "low"},
            text_format=schema,
            store=False,
            instructions=instructions,
            input=input_text,
            max_output_tokens=max_output_tokens,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("Structured output was empty")
        return parsed

    @staticmethod
    def _concept_from_schema(item: ConceptExtractionSchema, content: str) -> ExtractedConcept:
        mention = item.mention.strip() or item.canonical_name.strip()
        start = item.mention_start
        end = item.mention_end
        if start is None or end is None or start < 0 or end <= start or end > len(content) or content[start:end] != mention:
            found = content.casefold().find(mention.casefold())
            start, end = (found, found + len(mention)) if found >= 0 else (None, None)
        return ExtractedConcept(
            item.concept_type,
            item.canonical_name.strip(),
            item.english_name.strip() if item.english_name else None,
            item.abbreviation.strip() if item.abbreviation else None,
            item.description.strip(),
            mention,
            start,
            end,
            OpenAIResponsesGateway._score(item.confidence),
        )

    @staticmethod
    def _fallback_document_analysis(filename: str, content: str) -> DocumentAnalysisOutput:
        first = next((part.strip() for part in content.split("\n\n") if part.strip()), content[:280])
        return DocumentAnalysisOutput(filename.rsplit(".", 1)[0][:255], first[:1000], OpenAIResponsesGateway._fallback_keywords(content))

    @staticmethod
    def _clean_keywords(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            keyword = " ".join(str(value).strip().split())[:100]
            normalized = keyword.casefold()
            if keyword and normalized not in seen:
                seen.add(normalized)
                result.append(keyword)
        return result[:32]

    @staticmethod
    def _bounded_text(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        head = int(limit * 0.75)
        return f"{text[:head]}\n\n[중략]\n\n{text[-(limit - head):]}"

    @staticmethod
    def _score(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _fallback_keywords(text: str) -> list[str]:
        from app.core.text import fallback_keywords
        return fallback_keywords(text)
