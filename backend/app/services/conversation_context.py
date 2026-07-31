from dataclasses import dataclass

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import QuestionHistory


@dataclass(frozen=True)
class ConversationTurnContext:
    turn_index: int
    question: str
    answer: str


@dataclass(frozen=True)
class ConversationContext:
    turns: list[ConversationTurnContext]
    truncated: bool


class ConversationContextService:
    def build(self, session: Session, conversation_id: int | None, *, exclude_history_id: int | None = None, max_turns: int | None = None) -> ConversationContext:
        if conversation_id is None:
            return ConversationContext([], False)
        rows = session.exec(
            select(QuestionHistory)
            .where(
                QuestionHistory.conversation_id == conversation_id,
                QuestionHistory.status == "completed",
                QuestionHistory.answer_markdown.is_not(None),
                QuestionHistory.id != exclude_history_id,
            )
            .order_by(QuestionHistory.turn_index.desc())
        ).all()
        settings = get_settings()
        turn_limit = max_turns or settings.chat_context_turn_limit
        selected: list[ConversationTurnContext] = []
        used_chars = 0
        truncated = False
        for row in rows:
            if len(selected) >= turn_limit:
                truncated = True
                break
            question = row.question.strip()
            answer = (row.answer_markdown or "").strip()
            item_chars = len(question) + len(answer)
            remaining = settings.chat_context_max_chars - used_chars
            if remaining <= 0:
                truncated = True
                break
            if item_chars > remaining:
                answer_limit = max(0, remaining - len(question) - 32)
                answer = f"{answer[:answer_limit]}\n[이전 답변 일부 생략]" if answer_limit else "[이전 답변 생략]"
                truncated = True
            selected.append(
                ConversationTurnContext(
                    turn_index=row.turn_index or 0,
                    question=question,
                    answer=answer,
                )
            )
            used_chars += len(question) + len(answer)
        selected.reverse()
        return ConversationContext(selected, truncated)

    @staticmethod
    def fallback_query(question: str, context: ConversationContext) -> str:
        previous_questions = [turn.question for turn in context.turns[-3:]]
        if not previous_questions:
            return question.strip()[:1_000]
        # OR keeps lexical fallback useful when a short follow-up and its
        # antecedent use different vocabulary.
        return " OR ".join(f"({value})" for value in [question.strip(), *previous_questions])[:1_000]
