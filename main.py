# 📋 main.py · [과제 백엔드] 나만의 멀티모달 API — 사진을 받아 정해 둔 칸(JSON)으로 정리 (Vercel 에 올릴 main.py · POST 한 번에 요청 1번)
# · ★ (직접 작성) 표시가 붙은 곳만 내 주제로 바꾸면 됨 — 화면(app.py)은 고칠 곳 없음
# · 키는 환경 변수 GEMINI_API_KEY · 접근 코드는 APP_ACCESS_CODE (코드 · 저장소에 적지 않음)
import base64
import binascii
import json
import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

MODEL_NAME = "gemini-3.5-flash-lite"

# ★ (직접 작성) ① 서비스 이름 · 아이콘 · 한 줄 소개 — 화면이 GET / 로 받아 제목으로 씀

# ★ ① 서비스 이름 · 아이콘 · 한 줄 소개
APP_TITLE = "냉장고 재료 요리 추천 도우미"
APP_ICON = "🍳"
APP_DESCRIPTION = "냉장고 사진을 분석해 보이는 재료와 만들 수 있는 요리, 조리 시간을 추천합니다"

# ★ ② 사진을 보고 할 일
PROMPT = """너는 냉장고 재료를 분석하고 요리를 추천하는 요리 도우미야.

사진 속 냉장고를 자세히 살펴보고 실제로 확인할 수 있는 식재료를 찾아줘.
사진에서 확인할 수 있는 재료만 정리하고, 식별하기 어려운 재료는
'확인 불가'라고 적어 줘.

확인한 재료를 활용할 수 있는 요리를 추천해 줘.
추가로 필요한 재료가 있다면 구분해서 알려 줘.
조리 시간은 대략적으로 안내하고, 조리 순서는 초보자도 이해할 수 있도록
간단하고 순서대로 작성해 줘.

냉장고 사진이 아니거나 식재료를 확인할 수 없는 사진이라면
각 결과 칸에 '냉장고 또는 식재료를 확인할 수 없습니다'라고 적어 줘.
사진에 없는 재료를 실제로 있는 것처럼 지어내지 마.
"""

# ★ ③ 결과로 받을 칸 이름 : 설명 (3~5개)
FIELDS = {
    "재료": "사진에서 확인한 냉장고 속 식재료",
    "추천 요리": "확인한 재료로 만들 수 있는 요리와 추가 필요 재료",
    "걸리는 시간": "추천 요리의 예상 조리 시간",
    "조리 순서": "요리를 만드는 간단한 단계별 조리 방법",
}


SCHEMA = {"type": "object", "properties": {name: {"type": "string", "description": text} for name, text in FIELDS.items()},
          "required": list(FIELDS)}
app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION)


class PhotoRequest(BaseModel):
    image_b64: str = Field(min_length=1, max_length=4_000_000, description="사진(JPEG)을 base64 로 바꾼 글자")


class Result(BaseModel):
    result: dict[str, str]
    tokens: int | None = None


def check_access(access_code):
    expected = os.environ.get("APP_ACCESS_CODE")
    if expected and access_code != expected:
        raise HTTPException(status_code=401, detail="접근 코드가 틀렸습니다 — 헤더 X-Access-Code 를 확인하세요")


def get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="서버에 GEMINI_API_KEY 가 없습니다 — 환경 변수를 확인하세요")
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=120_000, retry_options=types.HttpRetryOptions(http_status_codes=[500, 503])),
    )


@app.get("/")
def home():
    """화면이 제목 · 아이콘 · 소개 · 칸 이름을 가져가는 주소 (요청 없음)"""
    return {"name": APP_TITLE, "icon": APP_ICON, "description": APP_DESCRIPTION, "fields": list(FIELDS)}


@app.post("/analyze", response_model=Result)
def analyze(request: PhotoRequest, x_access_code: str | None = Header(default=None)):
    check_access(x_access_code)
    try:
        base64.b64decode(request.image_b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="base64 글자가 아닙니다")
    client = get_client()
    try:
        reply = client.interactions.create(
            model=MODEL_NAME, store=False,
            input=[{"type": "text", "text": PROMPT}, {"type": "image", "data": request.image_b64, "mime_type": "image/jpeg"}],
            response_format={"type": "text", "mime_type": "application/json", "schema": SCHEMA},
        )
    except Exception as error:
        code = getattr(error, "status_code", None)
        raise HTTPException(status_code=429 if code == 429 else 502, detail=f"Gemini 요청 실패 (상태 번호 {code})")
    try:
        result = json.loads(reply.output_text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="답이 JSON 모양이 아닙니다 — 다시 보내 보세요")
    return Result(result={name: str(result.get(name, "")) for name in FIELDS}, tokens=reply.usage.total_tokens)
