
import os

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


# 기본 설정
MODEL_NAME = "gemini-3.5-flash-lite"
MAX_TURNS = 8

SYSTEM_PROMPT = """
너는 폴리봇이라는 이름의 친절한 AI 챗봇이다.
인공지능소프트웨어과 학생의 파이썬과 AI 공부를 도와준다.
사용자의 질문에 정확하고 자연스러운 한국어로 답변한다.
쉽고 이해하기 쉽게 설명하며 필요하면 예시를 들어준다.
"""


# FastAPI 서버 생성
app = FastAPI(
    title="AI 용어 설명 API",
    description="폴리봇 AI 챗봇 API"
)


# 요청 데이터 형식
class Question(BaseModel):
    word: str = Field(min_length=1, max_length=30)
    style: str = Field(default="초등학생도 알아듣게 쉽게")


class Answer(BaseModel):
    word: str
    answer: str
    tokens: int | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[dict] = Field(default_factory=list)


class ChatReply(BaseModel):
    answer: str
    history: list[dict]


# 접근 코드 확인
def check_access(access_code):
    expected = os.environ.get("APP_ACCESS_CODE")

    if expected and access_code != expected:
        raise HTTPException(
            status_code=401,
            detail="접근 코드가 틀렸습니다. 헤더 X-Access-Code를 확인하세요."
        )


# Gemini 연결
def get_client():
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="서버에 GEMINI_API_KEY가 없습니다."
        )

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=60_000,
            retry_options=types.HttpRetryOptions(
                http_status_codes=[500, 503]
            )
        )
    )


# Gemini 질문 실행
def ask_gemini(client, system_instruction, contents):
    try:
        return client.interactions.create(
            model=MODEL_NAME,
            store=False,
            system_instruction=system_instruction,
            input=contents
        )

    except Exception as error:
        code = getattr(error, "status_code", None)

        if code == 429:
            raise HTTPException(
                status_code=429,
                detail="Gemini 무료 한도를 넘었습니다. 잠시 후 다시 요청하세요."
            )

        raise HTTPException(
            status_code=502,
            detail=f"Gemini 요청 실패 (상태 번호 {code})"
        )


# 대화 기록 정리
def trim_history(items, max_turns):
    user_indexes = [
        i for i, item in enumerate(items)
        if item.get("type") == "user_input"
    ]

    if len(user_indexes) <= max_turns:
        return items

    return items[user_indexes[-max_turns]:]


# 기본 페이지
@app.get("/")
def home():
    return {
        "message": "폴리봇 AI 용어 설명 API입니다. /docs에서 사용법을 확인하세요."
    }


# 인사 API
@app.get("/hello/{name}")
def hello(name: str):
    return {"message": f"{name} 님, 반가워요!"}


# 덧셈 API
@app.get("/add")
def add(a: int, b: int):
    return {
        "a": a,
        "b": b,
        "sum": a + b
    }


# 입력 데이터 확인 API
@app.post("/echo")
def echo(question: Question):
    return {
        "received": question.model_dump(),
        "length": len(question.word)
    }


# AI 용어 설명 API
@app.post("/explain", response_model=Answer)
def explain(
    question: Question,
    x_access_code: str | None = Header(default=None)
):
    check_access(x_access_code)

    client = get_client()

    reply = ask_gemini(
        client,
        f"너는 AI 용어 설명 도우미야. {question.style} 3문장 이내로 설명한다.",
        question.word
    )

    return Answer(
        word=question.word,
        answer=reply.output_text,
        tokens=reply.usage.total_tokens
    )


# AI 챗봇 API
@app.post("/chat", response_model=ChatReply)
def chat(
    request: ChatRequest,
    x_access_code: str | None = Header(default=None)
):
    check_access(x_access_code)

    new_step = {
        "type": "user_input",
        "content": [
            {"type": "text", "text": request.message}
        ]
    }

    send_list = trim_history(
        request.history + [new_step],
        MAX_TURNS
    )

    reply = ask_gemini(
        get_client(),
        SYSTEM_PROMPT,
        send_list
    )

    return ChatReply(
        answer=reply.output_text,
        history=send_list + [
            step.model_dump(mode="json")
            for step in reply.steps
        ]
    )
