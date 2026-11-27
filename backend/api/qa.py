"""
行旅识景 TripScape / api/qa

问答 API（文章式管线 + 会话上下文 + 低置信度返回"不知道"）。

POST /api/qa/chat
    请求：{"question": "...", "session_id": "客户端生成，可选"}
    响应：{"answer": "...", "confidence": 0.42, "known": true,
           "landmark": {...} | null, "landmarks": [...], "source": "article"}
"""

from apps.core.auth import OptionalAuth, login_required
from apps.core.net import client_ip
from apps.core.ratelimit import heavy_limiter
from apps.landmarks.models import QAContext
from ninja import Router, Schema
from ninja.errors import HttpError

router = Router()

# 单 IP 每分钟提问次数（RAG 是重接口，匿名可调，必须限流）
QA_PER_MINUTE = 30
QUESTION_MAX = 500
SESSION_ID_MAX = 48


class ChatIn(Schema):
    question: str
    session_id: str = ""


@router.get("/history", summary="历史会话记录")
@login_required
def history(request, limit: int = 50):
    """当前用户的历史问答（会话上下文按用户前缀存储）。

    limit 负数归一为 20（TS-11：负切片触发 500）。
    """
    limit = min(max(limit, 1), 200)
    rows = QAContext.objects.filter(
        session_id__startswith=f"u{request.auth.id}-"
    ).order_by("-created_at")[:limit]
    return {
        "success": True,
        "data": [
            {
                "id": c.id,
                "question": c.question,
                "answer": c.answer,
                "landmark_name": c.landmark_name,
                "created_at": c.created_at.isoformat(),
            }
            for c in rows
        ],
    }


@router.post("/chat", summary="智能问答（RAG + 会话上下文）", auth=OptionalAuth())
def chat(request, payload: ChatIn):
    """智能问答（RAG 检索 + 上下文；低置信度回答不知道）。"""
    ip = client_ip(request)
    if not heavy_limiter.allow(f"qa:{ip}", limit=QA_PER_MINUTE, window_seconds=60):
        raise HttpError(429, "提问过于频繁，请稍后再试")

    question = (payload.question or "").strip()
    if not question:
        raise HttpError(400, "问题不能为空")
    if len(question) > QUESTION_MAX:
        raise HttpError(400, f"问题最多 {QUESTION_MAX} 字")

    # 会话 ID 加用户前缀（登录时），便于历史页按用户过滤；
    # 匿名会话统一加 anon- 前缀，防止伪造 "u<id>-xxx" 往他人历史里塞记录。
    session_id = (payload.session_id or "")[:SESSION_ID_MAX]
    user = getattr(request, "auth", None)
    if session_id:
        if user and getattr(user, "is_authenticated", False):
            session_id = f"u{user.id}-{session_id}"
        else:
            session_id = f"anon-{session_id}"

    # 取会话历史（最近 10 轮，用带用户前缀的 session_id 查）
    history = []
    if session_id:
        ctx_rows = QAContext.objects.filter(session_id=session_id).order_by(
            "-created_at"
        )[:10]
        history = [
            {
                "question": c.question,
                "answer": c.answer,
                "landmark_name": c.landmark_name,
            }
            for c in reversed(list(ctx_rows))
        ]

    # 问答管线：文章式（分块检索 + 意图抽取）优先，索引不可用自动回退旧逻辑
    from services.article_qa import answer_question as article_answer

    result = article_answer(question, history=history)

    # 写会话历史
    if session_id:
        try:
            QAContext.objects.create(
                session_id=session_id,
                question=question,
                answer=result.get("answer", ""),
                landmark_name=(result.get("landmark") or {}).get("name", ""),
            )
        except Exception:
            pass

    return {
        "answer": result["answer"],
        "confidence": result["confidence"],
        "known": result["known"],
        "landmark": result.get("landmark"),
        "landmarks": result.get("landmarks")
        or ([result["landmark"]] if result.get("landmark") else []),
        "source": result["source"],
    }
