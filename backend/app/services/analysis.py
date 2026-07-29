from dataclasses import dataclass, field
from pathlib import Path

from sqlmodel import Session, delete, select

from app.core.config import get_settings
from app.core.text import chunk_text, normalize_name, sha256_text
from app.db import engine
from app.integrations.filesystem.storage import LocalFileStorage
from app.integrations.openai.responses import ExtractedConcept, ExtractedRelation, OpenAIResponsesGateway
from app.integrations.openai.vector_store import OpenAIVectorStoreGateway
from app.models import AnalysisJob, AppSetting, ChunkConcept, Concept, ConceptAlias, ConceptRelation, Document, DocumentChunk, DocumentKeyword
from app.services.jobs import now, update_job


@dataclass
class ChunkResult:
    index: int
    start: int
    end: int
    content: str
    concepts: list[ExtractedConcept] = field(default_factory=list)
    relations: list[ExtractedRelation] = field(default_factory=list)


class AnalysisWorkflow:
    def __init__(self, storage: LocalFileStorage, vector_store: OpenAIVectorStoreGateway, responses: OpenAIResponsesGateway):
        self.storage = storage
        self.vector_store = vector_store
        self.responses = responses

    def run(self, job_id: int) -> None:
        with Session(engine) as session:
            job = session.get(AnalysisJob, job_id)
            if job is None:
                return
            document = session.get(Document, job.document_id)
            if document is None:
                return
        try:
            self._run(job_id)
        except Exception as exc:
            with Session(engine) as session:
                job = session.get(AnalysisJob, job_id)
                document = session.get(Document, job.document_id) if job else None
                if job:
                    job.status = "failed"
                    job.stage = "failed"
                    job.progress = min(job.progress, 99)
                    job.error_code = "ANALYSIS_OUTPUT_INVALID" if isinstance(exc, (ValueError, KeyError)) else "INTERNAL_ERROR"
                    job.error_message = "자료 분석에 실패했습니다. 다시 시도해 주세요."
                    job.completed_at = now()
                    job.updated_at = now()
                    session.add(job)
                if document:
                    document.status = "failed"
                    document.active_job_id = None
                    document.updated_at = now()
                    session.add(document)
                session.commit()

    def _run(self, job_id: int) -> None:
        with Session(engine) as session:
            job = session.get(AnalysisJob, job_id)
            document = session.get(Document, job.document_id if job else 0) if job else None
            if not job or not document:
                return
            update_job(session, job_id, status="running", stage="stored", progress=5, message="원문을 확인했습니다.")
            content = self.storage.read(document.storage_key)
            if self.vector_store.configured:
                update_job(session, job_id, stage="vector_store_uploading", progress=15, message="AI 검색 저장소에 원문을 등록하고 있습니다.")
                try:
                    file_id, _ = self.vector_store.upload_and_poll(self.storage.root / document.storage_key, document.original_filename or "document.txt")
                    document.vector_store_file_id = file_id
                    document.vector_store_status = "indexed"
                except Exception:
                    document.vector_store_status = "failed"
                    document.vector_store_error_code = "OPENAI_UNAVAILABLE"
                session.add(document)
                if document.vector_store_status == "indexed":
                    store_setting = session.get(AppSetting, "vector_store_id")
                    if store_setting is None:
                        session.add(AppSetting(key="vector_store_id", value=self.vector_store.vector_store_id or "", updated_at=now()))
                    else:
                        store_setting.value = self.vector_store.vector_store_id or store_setting.value
                        store_setting.updated_at = now()
                        session.add(store_setting)
                session.commit()
            else:
                document.vector_store_status = "not_uploaded"
                session.add(document)
                session.commit()
            update_job(session, job_id, stage="chunking", progress=25, message="원문을 근거 청크로 나누고 있습니다.")
            chunks = [ChunkResult(index=i, start=start, end=end, content=chunk) for i, (start, end, chunk) in enumerate(chunk_text(content))]
            analysis = self.responses.analyze_document(document.original_filename or document.title, content)
            update_job(session, job_id, stage="summarizing", progress=35, message="제목·요약·키워드를 추출했습니다.")
            for chunk in chunks:
                update_job(session, job_id, stage="extracting_concepts", progress=min(80, 40 + int(35 * (chunk.index + 1) / max(len(chunks), 1))), message=f"청크 {chunk.index + 1}/{len(chunks)}의 개념을 연결하고 있습니다.")
                chunk.concepts = self.responses.extract_concepts(chunk.index, chunk.content)
                if not chunk.concepts:
                    chunk.concepts = self._fallback_concepts(chunk.content, analysis.keywords)
                chunk.relations = self.responses.extract_relations(chunk.index, chunk.content, chunk.concepts)
            update_job(session, job_id, stage="finalizing", progress=85, message="분석 결과를 저장하고 있습니다.")
            self._commit_result(session, document, job, content, analysis.title, analysis.summary, analysis.keywords, chunks)

    def _commit_result(self, session: Session, document: Document, job: AnalysisJob, content: str, title: str, summary: str, keywords: list[str], chunks: list[ChunkResult]) -> None:
        old_chunks = session.exec(select(DocumentChunk).where(DocumentChunk.document_id == document.id)).all()
        old_chunk_ids = [row.id for row in old_chunks if row.id is not None]
        if old_chunk_ids:
            session.exec(delete(ChunkConcept).where(ChunkConcept.chunk_id.in_(old_chunk_ids)))
            session.exec(delete(ConceptRelation).where(ConceptRelation.evidence_chunk_id.in_(old_chunk_ids)))
            session.exec(delete(DocumentChunk).where(DocumentChunk.id.in_(old_chunk_ids)))
        session.exec(delete(DocumentKeyword).where(DocumentKeyword.document_id == document.id))
        document.title = title[:255] or document.title
        document.summary = summary[:1000]
        document.character_count = len(content)
        document.analysis_version = job.analysis_version
        document.status = "ready"
        document.active_job_id = None
        document.updated_at = now()
        session.add(document)
        for rank, keyword in enumerate(dict.fromkeys(keywords), 1):
            value = str(keyword).strip()
            if value:
                session.add(DocumentKeyword(document_id=document.id or 0, normalized_keyword=normalize_name(value), keyword=value[:255], rank=rank, source="ai" if get_settings().openai_api_key else "fallback", created_at=now()))
        concept_by_mention: dict[tuple[int, str], int] = {}
        relation_keys: set[tuple[int, int, str]] = set()
        for chunk_result in chunks:
            chunk = DocumentChunk(document_id=document.id or 0, chunk_index=chunk_result.index, start_char=chunk_result.start, end_char=chunk_result.end, content=chunk_result.content, character_count=len(chunk_result.content), content_hash=sha256_text(chunk_result.content), created_at=now())
            session.add(chunk)
            session.flush()
            for extracted in chunk_result.concepts:
                concept = self._get_or_create_concept(session, extracted)
                mention = extracted.mention[:255]
                session.add(ChunkConcept(chunk_id=chunk.id or 0, concept_id=concept.id or 0, mention=mention, mention_start=extracted.mention_start, mention_end=extracted.mention_end, extraction_confidence=extracted.confidence, description_snapshot=extracted.description[:500], created_at=now()))
                self._add_alias(session, concept, extracted, chunk.id or 0)
                concept_id = concept.id or 0
                for value in (extracted.mention, extracted.canonical_name, extracted.english_name, extracted.abbreviation):
                    if value:
                        concept_by_mention[(chunk_result.index, normalize_name(value))] = concept_id
            for relation in chunk_result.relations:
                source = concept_by_mention.get((chunk_result.index, normalize_name(relation.source_mention)))
                target = concept_by_mention.get((chunk_result.index, normalize_name(relation.target_mention)))
                if source and target and source != target:
                    relation_key = (source, target, normalize_name(relation.relation_type))
                    if relation_key in relation_keys:
                        continue
                    relation_keys.add(relation_key)
                    session.add(ConceptRelation(source_concept_id=source, target_concept_id=target, relation_type=relation.relation_type[:80], is_directed=True, strength=max(0.5, relation.confidence), extraction_confidence=relation.confidence, explanation=relation.explanation[:500], evidence_chunk_id=chunk.id, visibility="visible", created_at=now(), updated_at=now()))
        self._sync_fts(session, document, chunks, keywords)
        job.status = "completed"
        job.stage = "completed"
        job.progress = 100
        job.message = "분석이 완료되었습니다."
        job.completed_at = now()
        job.updated_at = now()
        session.add(job)
        session.commit()

    def _get_or_create_concept(self, session: Session, extracted: ExtractedConcept) -> Concept:
        candidates = [extracted.canonical_name, extracted.english_name or "", extracted.abbreviation or "", extracted.mention]
        normalized = [normalize_name(value) for value in candidates if value]
        concept = None
        if normalized:
            concept = session.exec(select(Concept).where(Concept.concept_type == extracted.concept_type, Concept.normalized_name.in_(normalized))).first()
            if concept is None:
                aliases = session.exec(select(ConceptAlias).where(ConceptAlias.normalized_alias.in_(normalized))).all()
                for alias in aliases:
                    candidate = session.get(Concept, alias.concept_id)
                    if candidate and candidate.concept_type == extracted.concept_type:
                        concept = candidate
                        break
            if concept is None:
                for candidate in session.exec(select(Concept).where(Concept.concept_type == extracted.concept_type)).all():
                    values = {normalize_name(candidate.canonical_name), normalize_name(candidate.english_name or ""), normalize_name(candidate.abbreviation or "")}
                    if values.intersection(normalized):
                        concept = candidate
                        break
        if concept is None:
            concept = Concept(concept_type=extracted.concept_type, canonical_name=extracted.canonical_name[:255], english_name=extracted.english_name, abbreviation=extracted.abbreviation, normalized_name=normalize_name(extracted.canonical_name), description=extracted.description[:500], merge_confidence=extracted.confidence, visibility="visible", created_at=now(), updated_at=now())
            session.add(concept)
            session.flush()
        else:
            changed = False
            if extracted.english_name and not concept.english_name:
                concept.english_name = extracted.english_name[:255]
                changed = True
            if extracted.abbreviation and not concept.abbreviation:
                concept.abbreviation = extracted.abbreviation[:100]
                changed = True
            if len(extracted.description) > len(concept.description):
                concept.description = extracted.description[:500]
                changed = True
            if extracted.confidence > concept.merge_confidence:
                concept.merge_confidence = extracted.confidence
                changed = True
            if changed:
                concept.updated_at = now()
                session.add(concept)
        return concept

    def _add_alias(self, session: Session, concept: Concept, extracted: ExtractedConcept, chunk_id: int) -> None:
        canonical_type = "ko" if any("가" <= char <= "힣" for char in extracted.canonical_name) else "en"
        for value, alias_type in [(extracted.canonical_name, canonical_type), (extracted.english_name, "en"), (extracted.abbreviation, "abbreviation"), (extracted.mention, "source_mention")]:
            if not value:
                continue
            normalized = normalize_name(value)
            existing = session.exec(select(ConceptAlias).where(ConceptAlias.concept_id == concept.id, ConceptAlias.normalized_alias == normalized, ConceptAlias.alias_type == alias_type)).first()
            if existing is None:
                session.add(ConceptAlias(concept_id=concept.id or 0, alias=value[:255], normalized_alias=normalized, alias_type=alias_type, source_chunk_id=chunk_id, confidence=extracted.confidence, created_at=now()))

    @staticmethod
    def _fallback_concepts(content: str, keywords: list[str]) -> list[ExtractedConcept]:
        values = [value for value in keywords if value and value.casefold() in content.casefold()][:12]
        concepts = []
        for value in values:
            start = content.casefold().find(value.casefold())
            concepts.append(ExtractedConcept(AnalysisWorkflow._fallback_type(value), value[:255], None, None, "원문에서 반복적으로 확인된 핵심 용어", value[:255], start if start >= 0 else None, start + len(value) if start >= 0 else None, 0.35))
        return concepts

    @staticmethod
    def _fallback_type(value: str) -> str:
        groups = {
            "organization_unit": ("사령부", "부대", "연구소", "센터", "본부"),
            "organization": ("정부", "기관", "기업", "회사", "대학", "연구원"),
            "country": ("한국", "미국", "중국", "일본", "러시아", "나토", "nato"),
            "region": ("도시", "지역", "전역", "해역", "국경"),
            "place": ("기지", "공항", "항구", "시설"),
            "policy_law": ("정책", "법률", "법안", "규정", "지침", "교리"),
            "event": ("전쟁", "분쟁", "작전", "회의", "사고", "발표", "시험"),
            "document": ("보고서", "논문", "데이터셋", "공식 문서"),
            "equipment": ("무기", "미사일", "차량", "항공기", "함정", "드론", "장비"),
            "system": ("체계", "시스템"),
            "technology": ("기술", "알고리즘", "소프트웨어", "통신", "센서", "인공지능", "ai"),
        }
        lowered = value.casefold()
        for concept_type, markers in groups.items():
            if any(marker.casefold() in lowered for marker in markers):
                return concept_type
        return "technology"

    @staticmethod
    def _sync_fts(session: Session, document: Document, chunks: list[ChunkResult], keywords: list[str]) -> None:
        connection = session.connection()
        connection.exec_driver_sql("DELETE FROM chunk_fts WHERE document_id = ?", (document.id,))
        for chunk in session.exec(select(DocumentChunk).where(DocumentChunk.document_id == document.id)).all():
            connection.exec_driver_sql("INSERT INTO chunk_fts(chunk_id, document_id, title, content, keywords) VALUES (?, ?, ?, ?, ?)", (chunk.id, document.id, document.title, chunk.content, " ".join(keywords)))
