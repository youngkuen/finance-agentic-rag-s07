# -*- coding: utf-8 -*-
"""FastAPI 앱 — /health · /ask · /ask/stream · /(UI).

7회차. 지금까지 `make ask` 로 터미널에서 부르던 그래프를 HTTP 로 엽니다. 셋이 더 붙습니다.
  1. 응답 스키마(schemas.AskResponse). 답변 문자열만 주지 않습니다. 근거(sources) · 기준일 · 고지 ·
     정책 버전이 같이 갑니다. 금융 답변은 "무엇을 근거로, 언제 기준으로" 가 답만큼 중요합니다.
  2. 인증(auth) · 호출 제한(limiter) · 감사 로그(audit). 완성본입니다. 키는 해시로 비교하고,
     로그에는 질문 원문 대신 해시가 남습니다.
  3. 스트리밍(sse). 답변 노드의 토큰만 골라 흘립니다.

그래프는 프로세스당 하나를 만들어 재사용합니다. 만드는 데 모델 적재 25초가 들기 때문입니다.
그래서 서버를 띄운 뒤 첫 요청이 느립니다(콜드 스타트). 벤치(scripts/api_bench.py)는 첫 호출을 따로 셉니다.
"""
from __future__ import annotations

import time
import uuid
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from ..agent.graph import build_agent_graph
from ..agent.nodes import policy
from ..index import qdrant
from ..settings import get_settings
from . import audit, sse
from .auth import require_api_key
from .schemas import AskRequest, AskResponse, HealthResponse, Source

s = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[s.rate_limit])
app = FastAPI(title="금융문서 Agentic RAG", version="0.7.0")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit(request: Request, exc: RateLimitExceeded):
    # 429. 상한은 .env 의 RATE_LIMIT(기본 30/minute). 키가 아니라 접속 주소 기준입니다.
    return JSONResponse({"detail": "요청이 너무 잦습니다. 잠시 후 다시 시도해 주세요."}, status_code=429)


_graph = None


def graph():
    """그래프 하나를 만들어 두고 재사용한다. 요청마다 만들면 요청마다 25초가 든다."""
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
    return _graph


def run_graph(question: str) -> tuple[dict, dict]:
    """그래프를 한 번 돌려 (최종 상태, 모델별 토큰) 을 반환한다.

    토큰은 6회차 ROI 가 쓴 것과 같은 콜백(UsageMetadataCallbackHandler)으로 센다.
    감사 로그와 응답의 usage 에 들어간다. 그래서 요청 하나가 얼마인지 로그에서 바로 읽을 수 있다.
    """
    from langchain_core.callbacks import UsageMetadataCallbackHandler
    usage = UsageMetadataCallbackHandler()
    out = graph().invoke({"question": question}, {"callbacks": [usage]})
    return out, dict(usage.usage_metadata)


def sources_from(hits: list[dict]) -> list[Source]:
    """검색 결과(hits)를 응답의 근거 목록으로 바꾼다. 상위 8개, 발췌 300자.

    시행일 · 심의필 만료 · 열화 재현본 표시가 같이 간다. 고객은 "어느 조항"만이 아니라
    "언제 판"인지도 봐야 한다. 2013년 판과 2024년 판은 같은 제7조라도 다른 답이다.
    """
    return [Source(chunk_id=h["chunk_id"], doc_id=h.get("doc_id", ""),
                   doc_type=h.get("doc_type", ""), issuer=h.get("issuer", ""),
                   article=h.get("article", ""), article_title=h.get("article_title", ""),
                   page_start=h.get("page_start", 0),
                   effective_from=h.get("effective_from", ""),
                   review_expiry=h.get("review_expiry", ""),
                   expired=bool(h.get("expired")),
                   synthetic_degraded=bool(h.get("synthetic_degraded")),
                   excerpt=h.get("text", "")[:300],
                   score=float(h.get("rerank_score", h.get("score", 0.0))))
            for h in hits[:8]]


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """살아 있는가, 그리고 무엇으로 살아 있는가. 컬렉션 · 포인트 수 · 모델 · 정책 버전.

    포인트 수가 0 이면 인덱스가 없는 것이다. 런북의 "Qdrant 가 죽었다" 시나리오가 이 줄을 본다.
    """
    return HealthResponse(status="ok", collection=s.qdrant_collection,
                          points=qdrant.count(), llm=s.llm_model_main,
                          policy_version=policy()["policy_version"])


@app.post("/ask", response_model=AskResponse)
@limiter.limit(s.rate_limit)
def ask(request: Request, body: AskRequest,
        key_id: str = Depends(require_api_key)) -> AskResponse:
    """실습 1. 질문 하나를 그래프에 넣고 AskResponse 를 만든다.

    순서는 셋이다.
      (1) run_graph 로 그래프를 돌리고 걸린 시간을 잰다(ms).
      (2) 최종 상태(dict)를 AskResponse 로 옮긴다. answer · notices · basis_date(body.as_of 가 없으면 오늘) ·
          sources(sources_from) · abstained · abstain_reason · escalation_reason ·
          policy_version(policy()["policy_version"]) · request_id(uuid4 hex 앞 12자) · latency_ms · retry_count · usage.
      (3) audit.write 로 감사 로그 한 줄을 남긴다. 질문 원문은 audit 가 해시로 바꾼다. 여기서 바꾸지 않는다.
    테스트는 tests/test_api.py 의 실습 1 다섯. 빠뜨리기 쉬운 것은 basis_date 와 감사 로그다.
    답변 문자열만 반환하면 테스트가 아니라 고객이 거절한다.
    """
    # (1) 그래프를 돌리고 시간을 잰다
    t0 = time.perf_counter()
    out, usage = run_graph(body.question)
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    # (2) 최종 상태 → 응답. 기준일은 요청이 주면 그것, 없으면 오늘. 거절이면 근거는 비어 있다.
    resp = AskResponse(
        answer=out.get("answer", ""),
        notices=list(out.get("notices", [])),
        basis_date=body.as_of or date.today().isoformat(),
        sources=sources_from(out.get("hits", [])),
        abstained=bool(out.get("abstained")),
        abstain_reason=out.get("abstain_reason", "") or "",
        escalation_reason=out.get("escalation_reason", "") or "",
        policy_version=policy()["policy_version"],
        request_id=uuid.uuid4().hex[:12],
        latency_ms=latency_ms,
        retry_count=int(out.get("retry_count", 0)),
        usage=usage,
    )

    # (3) 감사 로그 한 줄. 질문은 원문 그대로 넘긴다. 해시로 바꾸는 것은 audit 의 일이다.
    audit.write(request_id=resp.request_id, api_key_id=key_id, question=body.question,
                response=resp.model_dump(), model=s.llm_model_main,
                policy_version=resp.policy_version, latency_ms=latency_ms, usage=usage)
    return resp


@app.post("/ask/stream")
@limiter.limit(s.rate_limit)
async def ask_stream(request: Request, body: AskRequest,
                     key_id: str = Depends(require_api_key)):
    """같은 질문을 SSE 로. 이벤트는 sse.stream_graph 가 만든다(실습 2)."""
    rid = uuid.uuid4().hex[:12]
    return EventSourceResponse(_as_events(sse.stream_graph(graph(), {"question": body.question},
                                                           request_id=rid)))


async def _as_events(events):
    """스트림 도중의 예외를 error 이벤트로 바꾼다. 실습 2 를 채우기 전(NotImplementedError)에도
    연결이 그냥 끊기지 않고 한 줄이 남는다. 연결만 끊기면 클라이언트는 원인을 모른다."""
    try:
        async for ev in events:
            yield ev
    except Exception as e:
        yield sse.event("error", {"message": f"{type(e).__name__}: {e}"})


UI = Path(__file__).resolve().parent.parent.parent.parent / "ui" / "index.html"


@app.get("/")
def ui():
    """UI 한 쪽. compose 에서는 nginx(8080)가 같은 파일을 내고 /ask 를 이 서버로 넘긴다."""
    return FileResponse(UI) if UI.exists() else {"detail": "ui/index.html 이 없습니다."}
