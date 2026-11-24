"""UC-39 — hội thoại roleplay với nhân vật AI (ASR + LLM + TTS).

Ba mảnh đều đã có sẵn trong module luyện nói, UC này chỉ nối chúng thành một
vòng hội thoại: Whisper nghe (`app.speaking.asr`), Ollama trả lời
(`app.speaking.scoring.ollama_client`), trình duyệt đọc bằng Web Speech API.

## Ràng buộc kế thừa từ module luyện nói (CLAUDE.md mục 7)

**ĐỘC LẬP với lõi DKT.** Không đọc/ghi KNOWLEDGE_STATE, không sinh INTERACTION,
không đụng lịch ôn. Một câu nói trong hội thoại không phải một lượt trả lời về
một từ cụ thể, nên đưa nó vào DKT sẽ làm bẩn đúng thứ đề tài đang đo.

**Chạy cục bộ.** Không gọi dịch vụ ngoài; audio xóa ngay sau khi chép.

## Vì sao câu mở đầu là văn bản cố định, không do LLM sinh

Để **mở hội thoại được kể cả khi Ollama chưa chạy**, và để mỗi kịch bản luôn bắt
đầu giống nhau. Người học bấm vào rồi nhận một câu chào khác nhau mỗi lần thì
không luyện lại được cùng một tình huống.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ConversationTurn
from app.models.user import User
from app.schemas.conversation import (
    ConversationDetail,
    ConversationRow,
    ConversationTurnRow,
    ScenarioDefinition,
    VoiceGender,
)
from app.speaking.scoring import ollama_client
from app.speaking.scoring.ollama_client import OllamaUnavailable

logger = logging.getLogger(__name__)

#: Số lượt gần nhất đưa vào prompt. Đủ để giữ mạch, mà không đẩy model nhỏ vào
#: một ngữ cảnh dài khiến nó quên mất vai đang đóng.
CONTEXT_TURNS = 10
MAX_USER_TEXT = 600
#: Trần lượt mỗi phiên — hội thoại dài vô hạn với model nhỏ sẽ trôi dần khỏi
#: kịch bản, và người học cũng cần một điểm dừng để xem lại.
MAX_TURNS = 40


@dataclass(frozen=True)
class Scenario:
    key: str
    name: str
    description: str
    persona: str
    #: Giới tính giọng đọc TTS — phải khớp với nhân vật (bug #11).
    voice: VoiceGender
    #: Mô tả vai cho LLM — viết bằng tiếng Anh vì đó là ngôn ngữ model đóng vai.
    persona_prompt: str
    opening: str
    cefr: str


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        key="cafe", name="Gọi đồ ở quán cà phê",
        description="Đặt món, hỏi giá, đổi ý - tình huống giao tiếp cơ bản nhất.",
        persona="Emma (barista)",
        voice="female",
        persona_prompt=(
            "You are Emma, a friendly barista in a small coffee shop in Melbourne. "
            "Serve the customer, take their order, suggest items, and handle payment."
        ),
        opening="Hi there! Welcome in. What can I get for you today?",
        cefr="A2",
    ),
    Scenario(
        key="airport", name="Làm thủ tục ở sân bay",
        description="Ký gửi hành lý, hỏi cửa ra máy bay, xử lý khi chuyến bị đổi giờ.",
        persona="David (nhân viên check-in)",
        voice="male",
        persona_prompt=(
            "You are David, a check-in agent at Sydney airport. Help the passenger "
            "check in, weigh their baggage, and answer questions about the gate."
        ),
        opening="Good morning. May I see your passport and booking reference, please?",
        cefr="B1",
    ),
    Scenario(
        key="interview", name="Phỏng vấn xin việc",
        description="Giới thiệu bản thân, nói về kinh nghiệm và điểm mạnh.",
        persona="Ms. Clark (nhà tuyển dụng)",
        voice="female",
        persona_prompt=(
            "You are Ms. Clark, a hiring manager interviewing a junior candidate. "
            "Ask one interview question at a time and follow up on their answers."
        ),
        opening="Thanks for coming in. To start, could you tell me a little about yourself?",
        cefr="B2",
    ),
    Scenario(
        key="smalltalk", name="Làm quen người mới",
        description="Chào hỏi, hỏi về sở thích, giữ mạch chuyện.",
        persona="Alex (bạn cùng lớp)",
        voice="male",
        persona_prompt=(
            "You are Alex, a friendly classmate meeting the learner for the first "
            "time at a language exchange meetup. Keep the small talk going."
        ),
        opening="Hey! I don't think we've met - I'm Alex. Is this your first time here?",
        cefr="A2",
    ),
)

_BY_KEY = {s.key: s for s in SCENARIOS}


def list_scenarios() -> list[ScenarioDefinition]:
    return [
        ScenarioDefinition(
            key=s.key, name=s.name, description=s.description,
            persona=s.persona, voice=s.voice, cefr=s.cefr, opening=s.opening,
        )
        for s in SCENARIOS
    ]


def _scenario(key: str) -> Scenario:
    scenario = _BY_KEY.get(key)
    if scenario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Không có kịch bản '{key}'")
    return scenario


def _owned(db: Session, user: User, conversation_id: int) -> Conversation:
    convo = db.get(Conversation, conversation_id)
    if convo is None or convo.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy hội thoại")
    return convo


def _turns(db: Session, conversation_id: int) -> list[ConversationTurn]:
    return list(db.execute(
        select(ConversationTurn)
        .where(ConversationTurn.conversation_id == conversation_id)
        .order_by(ConversationTurn.ordinal)
    ).scalars())


def _add_turn(db: Session, convo: Conversation, speaker: str, text: str,
              correction: str | None = None, confidence: float | None = None) -> ConversationTurn:
    turn = ConversationTurn(
        conversation_id=convo.id,
        ordinal=convo.turn_count,
        speaker=speaker,
        text=text,
        correction=correction,
        asr_confidence=confidence,
        created_at=datetime.now(timezone.utc),
    )
    db.add(turn)
    convo.turn_count += 1
    return turn


def _detail(db: Session, convo: Conversation) -> ConversationDetail:
    scenario = _BY_KEY.get(convo.scenario)
    return ConversationDetail(
        id=convo.id,
        scenario=convo.scenario,
        scenario_name=scenario.name if scenario else convo.scenario,
        persona=scenario.persona if scenario else "",
        voice=scenario.voice if scenario else "female",
        cefr=scenario.cefr if scenario else "",
        status=convo.status,
        started_at=convo.started_at,
        ended_at=convo.ended_at,
        turns=[
            ConversationTurnRow(
                ordinal=t.ordinal, speaker=t.speaker, text=t.text,
                correction=t.correction, asr_confidence=t.asr_confidence,
                created_at=t.created_at,
            )
            for t in _turns(db, convo.id)
        ],
    )


def start(db: Session, user: User, scenario_key: str) -> ConversationDetail:
    """Mở một phiên hội thoại. Câu chào là văn bản cố định của kịch bản."""
    scenario = _scenario(scenario_key)
    convo = Conversation(
        user_id=user.id, scenario=scenario.key, status="active",
        started_at=datetime.now(timezone.utc), turn_count=0,
    )
    db.add(convo)
    db.flush()
    _add_turn(db, convo, "ai", scenario.opening)
    db.commit()
    db.refresh(convo)
    return _detail(db, convo)


def _system_prompt(scenario: Scenario) -> str:
    return (
        f"{scenario.persona_prompt}\n\n"
        f"The person you are talking to is an English learner at CEFR level "
        f"{scenario.cefr}. Follow these rules strictly:\n"
        f"- Stay in character. Never mention that you are an AI or a language model.\n"
        f"- Reply in English, 1 to 3 short sentences, at {scenario.cefr} level.\n"
        f"- Always end with a question or a prompt so the conversation continues.\n"
        f"- If the learner's last message has a clear grammar or word-choice mistake, "
        f"put a short corrected version in \"correction\". If it is fine, use null. "
        f"Never correct spelling of transcribed speech.\n"
        f'Answer ONLY as JSON: {{"reply": "...", "correction": "..." or null}}'
    )


def _history_block(turns: list[ConversationTurn], scenario: Scenario) -> str:
    recent = turns[-CONTEXT_TURNS:]
    lines = [
        f"{'You' if t.speaker == 'ai' else 'Learner'}: {t.text}"
        for t in recent
    ]
    return f"Conversation so far (you are {scenario.persona}):\n" + "\n".join(lines)


def reply(db: Session, user: User, conversation_id: int, text: str,
          confidence: float | None = None) -> ConversationDetail:
    """Ghi lượt của người học rồi lấy lượt trả lời của nhân vật.

    Ollama không chạy được -> **503**, và lượt của người học KHÔNG được ghi. Ghi
    một mình lượt người học sẽ để lại hội thoại lệch vai, lần sau mở lên thấy
    mình nói hai câu liền mà nhân vật im lặng.
    """
    convo = _owned(db, user, conversation_id)
    if convo.status != "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Hội thoại đã kết thúc")

    clean = (text or "").strip()
    if not clean:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Chưa có nội dung để gửi")
    if convo.turn_count >= MAX_TURNS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Hội thoại đã đạt {MAX_TURNS} lượt. Hãy kết thúc và mở phiên mới.",
        )

    scenario = _scenario(convo.scenario)
    history = _turns(db, convo.id)
    user_block = (
        f"{_history_block(history, scenario)}\n"
        f"Learner: {clean[:MAX_USER_TEXT]}\n\n"
        f"Reply as {scenario.persona}."
    )

    try:
        parsed = ollama_client.chat_json(_system_prompt(scenario), user_block)
    except OllamaUnavailable as exc:
        logger.warning("UC-39: Ollama không sẵn sàng — %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Nhân vật AI chưa sẵn sàng: cần Ollama chạy cục bộ. "
            "Kiểm tra ở /api/v1/speaking/health.",
        ) from exc

    ai_text = str(parsed.get("reply") or "").strip()
    if not ai_text:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Nhân vật AI trả lời rỗng. Thử gửi lại câu vừa rồi.",
        )
    raw_correction = parsed.get("correction")
    correction = str(raw_correction).strip() if raw_correction else None
    # Model nhỏ hay "sửa" bằng cách chép lại y nguyên câu — đó không phải sửa.
    if correction and correction.lower() == clean.lower():
        correction = None

    _add_turn(db, convo, "user", clean, correction=correction, confidence=confidence)
    _add_turn(db, convo, "ai", ai_text)
    db.commit()
    db.refresh(convo)
    return _detail(db, convo)


def end(db: Session, user: User, conversation_id: int) -> ConversationDetail:
    convo = _owned(db, user, conversation_id)
    if convo.status == "active":
        convo.status = "ended"
        convo.ended_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(convo)
    return _detail(db, convo)


def get(db: Session, user: User, conversation_id: int) -> ConversationDetail:
    return _detail(db, _owned(db, user, conversation_id))


def history(db: Session, user: User, limit: int = 20) -> list[ConversationRow]:
    rows = db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.started_at.desc())
        .limit(limit)
    ).scalars()
    out = []
    for convo in rows:
        scenario = _BY_KEY.get(convo.scenario)
        out.append(ConversationRow(
            id=convo.id, scenario=convo.scenario,
            scenario_name=scenario.name if scenario else convo.scenario,
            status=convo.status, started_at=convo.started_at,
            ended_at=convo.ended_at, turn_count=convo.turn_count,
        ))
    return out
