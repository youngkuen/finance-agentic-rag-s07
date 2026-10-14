# 설치와 준비물 받기 (7회차)

6회차와 같은 컴퓨터에서, 6회차 폴더(`finance-agentic-rag-s06`) 옆에 새 레포지토리를 받습니다. 문서·청크·모델·결과 파일·`.env` 는 6회차 폴더에서 복사하고, **새 패키지 다섯**(fastapi · uvicorn · sse-starlette · slowapi · httpx)을 설치합니다. 여기까지 10분입니다. 그리고 **Docker 이미지를 미리 빌드**합니다. 5~15분 걸리니 수업 전날 밤에 걸어 두세요. 마지막 7번의 확인 줄 둘을 디스코드에 남겨 주세요.

Docker 가 안 되는 분도 수업은 됩니다. `make api` 로 같은 서버를 띄우고 같은 명령을 씁니다. Docker 는 셋(Qdrant · API · UI)을 한 줄로 띄우는 마지막 15분에만 씁니다.

## 1. 준비물 두 가지, git 과 uv

1~6회차에 했으면 건너뜁니다. 확인은 `git --version`, `uv --version`.

## 2. 레포지토리 받기

지난 회차처럼 포크를 먼저 합니다.

1. 브라우저에서 https://github.com/hyeonsikseo/finance-agentic-rag-s07 를 열고 오른쪽 위 **Fork** 를 누릅니다.
2. 그 레포지토리를 받습니다. `<계정>` 자리에 자기 GitHub 계정을 넣습니다.

```bash
git clone https://github.com/<계정>/finance-agentic-rag-s07.git
cd finance-agentic-rag-s07
git remote add upstream https://github.com/hyeonsikseo/finance-agentic-rag-s07.git
```

포크가 막히면 원본을 그대로 받고 과제는 zip 으로 냅니다.

## 3. 6회차 폴더에서 가져오기

문서, OCR 캐시, 청크, 임베딩 스냅샷, BM25 캐시, 모델, **결과 파일 전부**, 그리고 `.env`(키)를 복사합니다. 폴더가 다른 곳에 있으면 경로만 바꿉니다.

**Mac**

```bash
cp -R ../finance-agentic-rag-s06/data/raw data/
cp -R ../finance-agentic-rag-s06/data/ocr_cache data/
cp -R ../finance-agentic-rag-s06/data/chunks data/
cp ../finance-agentic-rag-s06/data/ingest_report.json data/
cp -R ../finance-agentic-rag-s06/data/embeddings data/
cp -R ../finance-agentic-rag-s06/data/bm25_cache data/
cp -R ../finance-agentic-rag-s06/models .
mkdir -p results && cp ../finance-agentic-rag-s06/results/*.json ../finance-agentic-rag-s06/results/*.csv results/
cp ../finance-agentic-rag-s06/.env .env
```

**Windows (PowerShell)**

```powershell
Copy-Item -Recurse ..\finance-agentic-rag-s06\data\raw data\
Copy-Item -Recurse ..\finance-agentic-rag-s06\data\ocr_cache data\
Copy-Item -Recurse ..\finance-agentic-rag-s06\data\chunks data\
Copy-Item ..\finance-agentic-rag-s06\data\ingest_report.json data\
Copy-Item -Recurse ..\finance-agentic-rag-s06\data\embeddings data\
Copy-Item -Recurse ..\finance-agentic-rag-s06\data\bm25_cache data\
Copy-Item -Recurse ..\finance-agentic-rag-s06\models .
New-Item -ItemType Directory -Force results | Out-Null
Copy-Item ..\finance-agentic-rag-s06\results\*.json, ..\finance-agentic-rag-s06\results\*.csv results\
Copy-Item ..\finance-agentic-rag-s06\.env .env
```

`models` 는 4GB 가 넘어서 1~2분 걸립니다. 디스크가 빠듯하면 복사 대신 옮겨도 됩니다(`mv`, `Move-Item`). 6회차 폴더는 이제 쓰지 않습니다.

`.env` 에 7회차 줄 셋을 더합니다. 기본값 그대로면 됩니다. `.env.example` 의 맨 아래 "7회차" 부분을 복사해 붙이세요. `API_KEY=change-me` 가 오늘 쓰는 키입니다.

## 4. 파이썬과 패키지 설치

**Mac**

```bash
make setup
```

**Windows (PowerShell)**

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

새 패키지 다섯이 더해집니다. 1~2분입니다.

## 5. 인덱스 만들기

6회차 청크를 이 폴더의 Qdrant 에 넣습니다. 스냅샷을 재사용해서 10초입니다. `make api` 가 이 인덱스를 봅니다.

**Mac**

```bash
make index
```

**Windows (PowerShell)**

```powershell
$env:HF_HOME = ".\models"
.venv\Scripts\python scripts\build_index.py
```

## 6. Docker 이미지 빌드 (수업 전에. 5~15분)

Docker Desktop 이 없으면 0회차 설치 문서의 9번대로 설치하고 **메모리 상한을 6GB 이상**으로 올립니다(Mac: Settings → Resources → Memory. Windows: `.wslconfig` 의 `memory=8GB`). API 컨테이너가 임베딩 모델과 리랭커를 함께 올리기 때문에 작으면 조용히 죽습니다.

```bash
docker --version          # Docker version 25 이상이면 됩니다
make compose-build        # Windows: docker compose build
```

마지막 줄이 `Built` 또는 이미지 이름으로 끝나면 된 것입니다. 네트워크에 따라 5~15분입니다. 수업에서는 빌드하지 않고 띄우기만 합니다(`make compose-up`, 1분).

빌드가 안 되거나 Docker 를 설치할 수 없으면 그대로 두세요. 수업의 마지막 15분만 강사 화면으로 보면 됩니다.

## 7. 되는지 확인

**Mac**

```bash
make test
```

**Windows (PowerShell)**

```powershell
.venv\Scripts\python -m pytest -q
```

지금은 **실패가 정상**입니다. 채울 자리 둘이 비어 있어서 7회차 테스트 10개가 `NotImplementedError` 로 실패합니다. 마지막 줄이 `10 failed, 118 passed` 이고 `error` 가 없으면 설치는 된 것입니다. **이 마지막 줄과, 6번 빌드의 마지막 줄(또는 "Docker 없음"), 둘을 디스코드에 적어 주세요.**

## 막힐 때

| 증상 | 이유 | 이렇게 합니다 |
|---|---|---|
| `uv: command not found` | 설치 뒤 터미널을 새로 안 열었습니다 | 터미널을 닫고 새로 엽니다 |
| `make test` 가 `ModuleNotFoundError: fastapi` | `make setup` 을 안 했습니다 | 4번 |
| `make test` 가 `11 failed` 이상 | 6회차 결과 파일을 안 복사했습니다 | 3번. `results/agentic.json` 이 있어야 합니다 |
| `make compose-build` 가 `Cannot connect to the Docker daemon` | Docker Desktop 이 꺼져 있습니다 | Docker Desktop 을 켜고 고래 아이콘이 멈추면 다시 |
| 빌드 중 `No space left on device` | 디스크 | `docker system prune` 뒤 다시. 이미지는 약 3GB 입니다 |
| 빌드가 30분 넘게 걸린다 | 네트워크(torch 200MB, 패키지 1GB) | 그대로 두거나 끊고 수업은 `make api` 로 |
| `make api` 가 `Address already in use` | 8000번 포트를 다른 서버가 쓰고 있습니다 | 그 터미널에서 Ctrl+C, 또는 compose 를 내립니다(`make compose-down`) |
| `/health` 의 `points` 가 0 | 인덱스가 없습니다 | `make index`(임베디드) 또는 `make index-server`(compose) |
| `docker compose ps` 에서 api 가 `unhealthy` | 메모리 부족으로 죽었습니다 | `docker compose logs api` 끝에 `Killed` 가 있으면 Docker 메모리를 6GB 이상으로 |
