# 7회차 실습 — FastAPI · SSE · Docker Compose

수업은 지난 시간과 같이 "강사가 짧게 보여 주고 → 여러분이 직접 채우고 → 테스트로 확인"입니다. 오늘은 지금까지 `make ask` 로 터미널에서 부르던 그래프를 **HTTP 서비스**로 엽니다. 채우는 자리가 둘(**실습 1** 응답 조립, **실습 2** 스트리밍의 노드 필터)이고, 인증·호출 제한·감사 로그는 완성본을 읽습니다. 결과물은 `results/api_bench.json`(응답 시간 예산)과 `docs/security_questionnaire.md`(과제)입니다. 아래는 수업 순서대로 적은 것입니다.

**이 문서에서 쓰는 명령**

| 명령 | 하는 일 |
|---|---|
| `make test` | 자동 채점. 2~6회차 검사 116개와 오늘 검사 12개를 한 번에 돌려서 맞으면 초록, 틀리면 빨강 |
| `make api` | API 서버를 띄운다. http://localhost:8000. 바로 뜨고, 모델 적재는 첫 요청에서 한다(콜드 스타트). **두 번째 터미널**에서 띄우고 그대로 둔다 |
| `make api-ask Q="질문"` | `/ask` 에 질문 하나를 보내고 근거 · 고지 · 답변 · 토큰을 찍는다. 실습 1 을 채우기 전에는 500 |
| `make api-stream Q="질문"` | `/ask/stream` 의 이벤트를 오는 대로 찍는다. 실습 2 를 채우기 전에는 error 이벤트 |
| `make api-bench` | 답할 수 있는 10문항을 `/ask` 로 보내 평균 · p95 · 문항당 비용을 잰다. 약 3분이라 휴식에 돌린다 |
| `make compose-up` | Qdrant · API · UI 셋을 컨테이너로 띄운다. http://localhost:8080. 이미지는 수업 전에 빌드해 두었다(install.md 6번) |
| `make check-s07` | 오늘 결과물이 조건 5개를 만족하는지 검사한다. 과제 확인도 이 명령으로 |

Windows 는 [install.md](../install.md) 의 PowerShell 명령을 씁니다. `make api` 는 `.venv\Scripts\python -m uvicorn finrag.api.main:app --port 8000 --app-dir src`, `make api-ask Q="..."` 는 `.venv\Scripts\python scripts\api_ask.py "..."` 입니다.

## 오늘 끝내고 갈 것

1. `/ask` 가 **근거 인용 응답**을 돌려줍니다. 답변 문자열이 아니라 근거(조항 · 시행일 · 만료 여부) · 기준일 · 고지 · 정책 버전이 같이 가는 JSON 입니다.
2. `/ask/stream` 이 **답변 노드의 글자만** 흘립니다. 첫 글자까지 걸리는 시간이 사용자가 느끼는 시간입니다.
3. 요청 하나가 얼마나 걸리고 얼마인지 **응답 시간 예산**으로 적습니다. 6회차에 잰 p95 와 비용이 오늘의 기준입니다.
4. 셋(Qdrant · API · UI)을 `docker compose up` 한 줄로 띄우고, 보안 질의서 답변서의 첫 장을 씁니다.

## 시작 전 확인

```bash
make test
```

지금은 실패가 정상입니다. 마지막 줄이 `10 failed, 118 passed` 이고 `error` 가 없으면 됩니다. `results/agentic.json` 이 있어야 합니다(6회차 폴더에서 복사). 그 줄과 `docker --version` 의 결과(없으면 "없음"), 둘을 채팅에 적어 주세요.

## 1부 · API 뼈대 읽기

`src/finrag/api/` 에 파일 다섯이 있습니다. `main.py`(라우트 셋: `/health` · `/ask` · `/ask/stream`), `schemas.py`(요청 · 응답 모양), `sse.py`(스트림 이벤트), `auth.py`(키 확인), `audit.py`(감사 로그). 오늘 채우는 것은 `main.ask` 와 `sse.stream_graph` 둘이고 나머지는 읽기만 합니다.

먼저 볼 것은 셋입니다.

- `main.graph()` — 그래프를 프로세스당 하나만 만들어 재사용합니다. 만드는 데 모델 적재 25초가 듭니다. 그래서 서버를 띄운 뒤 **첫 요청이 느립니다**(콜드 스타트). 벤치가 첫 호출을 따로 세는 이유입니다.
- `schemas.AskResponse` — 필드 열둘. `answer` 말고 `sources`(근거 8개, 시행일 · 심의필 만료 · 열화 재현본 표시) · `basis_date`(기준일) · `notices`(고지) · `policy_version`(어느 정책으로 답했나) · `request_id`(감사 로그와 잇는 열쇠) · `usage`(모델별 토큰). 정보보호팀과 감사가 묻는 것이 전부 이 안에 있습니다.
- `main.sources_from()` — 검색 결과를 `sources` 로 바꾸는 완성본. 실습 1 에서 그대로 부릅니다.

## 2부 · 실습 1 `main.ask`

`src/finrag/api/main.py` 의 `ask` 를 채웁니다. 독스트링에 순서 셋이 있습니다. 그래프를 돌리고(`run_graph`), 최종 상태를 `AskResponse` 로 옮기고, `audit.write` 로 한 줄 남깁니다. 요구사항은 `tests/test_api.py` 의 실습 1 다섯입니다. 빠뜨리기 쉬운 것은 `basis_date`(요청의 `as_of` 가 없으면 오늘)와 감사 로그입니다.

```bash
make test        # test_api 의 실습 1 다섯이 초록이면 통과. 5 failed, 123 passed
```

채운 뒤 **두 번째 터미널**에서 서버를 띄웁니다.

```bash
make api                      # 바로 "Application startup complete". 모델은 첫 요청에서 적재한다
```

첫 터미널로 돌아와 질문 하나를 보냅니다.

```bash
make api-ask Q="하나은행 여신거래기본약관 제7조 기한의 이익 상실 사유는 현행 기준으로 무엇인가요?"
```

**출력 읽기.** 첫 줄의 `request_id` 가 감사 로그의 열쇠, `정책` 이 정책 버전, `서버 ms` 가 그래프가 쓴 시간입니다. 둘째 줄 `토큰` 이 이 요청의 값입니다. `근거 (N)` 의 각 줄에 시행일과 "심의필 만료" 표시가 붙습니다. 맨 아래 `왕복` 이 사용자가 기다린 시간입니다. 첫 요청은 30~40초(모델 적재), 두 번째부터 15초 안쪽입니다. 같은 질문을 한 번 더 보내 보세요.

## 3부 · 실습 2 `sse.stream_graph`

`/ask` 는 끝날 때까지 빈 화면입니다. 15초를 아무 반응 없이 기다리게 할 수는 없습니다. 그래서 `/ask/stream` 이 **이벤트**를 흘립니다. `node_start`(어느 노드가 시작됐나) · `citation`(근거가 정해졌다) · `token`(답변 글자) · `done` · `error`.

LangGraph 의 `astream` 은 두 가지를 섞어 줍니다. `updates`(노드가 바꾼 키들)와 `messages`(모델이 만드는 글자). 그런데 `messages` 에는 재작성 노드와 판정 노드가 만드는 글자도 섞여 있습니다. 그걸 그대로 흘리면 화면에 검색어와 JSON 이 찍힙니다. **답변 노드(`answer` · `abstain`)의 글자만** 골라내는 것이 실습 2 입니다.

`src/finrag/api/sse.py` 의 `stream_graph` 를 채웁니다. 독스트링에 모드 둘과 이벤트 다섯이 있습니다. 요구사항은 `tests/test_api.py` 의 실습 2 다섯입니다. 전부 가짜 그래프라 LLM 없이 돕니다.

```bash
make test        # 128 passed
```

서버를 다시 띄웁니다(두 번째 터미널에서 Ctrl+C 뒤 `make api`. 코드를 바꾸면 다시 띄워야 합니다). 다시 띄운 첫 요청은 모델 적재가 들어가 느립니다. 같은 명령을 두 번 쳐서 두 번째 숫자를 봅니다.

```bash
make api-stream Q="KB 멀티플러스연금보험 약관 제7조 청약의 철회는 언제까지 가능한가요?"
```

**출력 읽기.** 왼쪽 숫자가 경과 시간입니다. `node_start` 가 노드 순서대로 찍히고, `citation` 에 근거 수, 그리고 `token 첫 글자` 줄의 시간이 **사용자가 처음 무언가를 보는 시점**입니다. 그 뒤로 글자가 흐르고 `done` 으로 끝납니다. 마지막 줄 "첫 글자까지 N ms" 를 `/ask` 의 왕복과 비교해 보세요.

브라우저에서도 봅니다. http://localhost:8000/?key=change-me 에 같은 질문을 넣으면 위에 노드 배지가 하나씩 켜지고 답변이 흐르고 오른쪽에 근거가 붙습니다. `ui/index.html` 124줄이 그 화면입니다. 이벤트를 받아 그리는 것뿐입니다.

## 휴식 · 응답 시간 측정

쉬기 전에 걸어 둡니다. 서버가 떠 있어야 합니다.

```bash
make api-bench       # 10문항, 약 3분 → results/api_bench.json
```

## 4부 · 인증 · 호출 제한 · 감사 로그 (완성본)

세 줄로 끝납니다. 틀린 키는 401, 1분에 30번 넘으면 429, 요청마다 `logs/audit.jsonl` 에 한 줄.

```bash
API_KEY=wrong make api-ask Q="아무 질문"        # HTTP 401
tail -1 logs/audit.jsonl                        # 방금 요청의 한 줄
```

**감사 로그 읽기.** `question_sha256` 은 있는데 `question` 은 없습니다. 원문을 남기지 않습니다. 질문에 주민번호가 섞여 들어와도 로그에는 안 남습니다. `api_key_id` 는 키의 해시 앞 12자, `cited_chunk_ids` 가 그때 인용한 조항, `policy_version` 과 `model` 이 그때의 설정, `usage` 가 그때의 토큰입니다. "그때 왜 그렇게 답했나"를 이 한 줄로 다시 만들 수 있습니다. 이것이 보안 질의서 답변서 Q2 의 답입니다.

## 5부 · 응답 시간 예산

`make api-bench` 의 마지막 두 줄을 봅니다. 평균 · p95 · 문항당 비용, 그리고 6회차 `agentic.json` 의 p95 와 비교입니다. 6회차는 그래프만 잰 시간이고 오늘은 HTTP 왕복까지입니다. 예산은 셋으로 적습니다. 첫 글자까지(스트림), 완료 p95, 문항당 비용. 이 셋이 8회차 readout 의 운영 절에 들어갑니다.

## 6부 · Docker Compose

세 컨테이너입니다. `qdrant`(벡터 DB, 서버 모드) · `api`(방금 만든 서버) · `ui`(nginx, 8080). 임베디드 Qdrant(파일)는 프로세스 하나만 열 수 있어서, 컨테이너가 둘 이상이면 서버 모드가 필요합니다. 그래서 인덱스를 서버에 한 번 넣습니다.

```bash
docker compose up -d qdrant      # 벡터 DB 먼저
make index-server                # 스냅샷을 서버 모드 Qdrant 에. 10초
make compose-up                  # 셋 전부. api 는 모델 적재 때문에 1분 뒤 healthy
docker compose ps                # 셋 다 Up 이면
curl -s localhost:8000/health    # points 가 3,700 안팎
```

브라우저에서 http://localhost:8080/?key=change-me. nginx 가 정적 파일을 내고 `/ask` 는 api 컨테이너로 넘깁니다(`ui/nginx.conf`, 스트리밍이라 버퍼링을 끈 것이 핵심). 끝나면 `make compose-down`. 로컬 `make api` 가 떠 있으면 8000번 포트가 겹치니 그쪽을 먼저 끕니다.

Docker 가 안 되는 분은 강사 화면을 봅니다. 수업의 나머지는 전부 `make api` 로 됩니다.

## 7부 · 보안 질의서 답변서

`docs/templates/security_questionnaire.md` 를 `docs/security_questionnaire.md` 로 복사하고 1절(데이터 흐름)과 2절의 Q2(로그)를 수업에서 채웁니다. 외부로 나가는 것은 마스킹된 질문과 검색된 조항 발췌뿐이고, 나가지 않는 것은 원문 · 키 · 문서 전체입니다. 숫자(미답변 정확도 · 오거절률 · 적대적 통과 수)는 6회차 결과 파일에서 옮깁니다. 나머지는 과제입니다.

## 마지막 · check-s07

서버 터미널에서 Ctrl+C 로 `make api` 를 **먼저 끕니다.** 임베디드 Qdrant 는 프로세스 하나만 열 수 있어서, 서버가 떠 있으면 첫 항목이 `already accessed` 로 빨갛게 나옵니다. compose 가 떠 있으면 `make compose-down`.

```bash
make check-s07       # 80초. 4/5 면 오늘은 끝. 보안 답변서가 과제
```

| 항목 | 통과 기준 |
|---|---|
| /ask 응답 | 실제 그래프로 돌려 근거 · 기준일 · 정책 버전이 있다 |
| /ask/stream 이벤트 | node_start 와 done 이 있고 token 또는 citation 이 있다 |
| 응답 시간 측정 | `results/api_bench.json` 에 10문항 이상과 p95 |
| 감사 로그 | `logs/audit.jsonl` 이 열 줄 이상이고 질문 원문이 없다 |
| 보안 답변서 | `docs/security_questionnaire.md` 가 있고 빈칸(`____`)이 없다 (과제) |
