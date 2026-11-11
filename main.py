
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


MODEL_NAME = "gemini-3.5-flash-lite"
MAX_TURNS = 8

SYSTEM_PROMPT = """
너는 친절하고 이해하기 쉽게 설명하는 AI 챗봇이다.
사용자의 질문에 정확하고 자연스러운 한국어로 답변한다.
필요하면 예시를 들어 설명한다.
"""

app = FastAPI(
    title="AI 용어 설명 API",
    description="용어를 보내면 Gemini가 쉽게 설명해 줍니다."
)


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


def trim_history(items, max_turns):
    user_indexes = [
        i for i, item in enumerate(items)
        if item.get("type") == "user_input"
    ]

    if len(user_indexes) <= max_turns:
        return items

    return items[user_indexes[-max_turns]:]


@app.get("/")
def home():
    return {
        "message": "AI 용어 설명 API 입니다. /docs 에서 사용법을 확인하세요."
    }


@app.get("/hello/{name}")
def hello(name: str):
    return {"message": f"{name} 님, 반가워요!"}


@app.get("/add")
def add(a: int, b: int):
    return {"a": a, "b": b, "sum": a + b}


@app.post("/echo")
def echo(question: Question):
    return {
        "received": question.model_dump(),
        "length": len(question.word)
    }


@app.post("/explain", response_model=Answer)
def explain(question: Question):
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


@app.post("/chat", response_model=ChatReply)
def chat(request: ChatRequest):
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
