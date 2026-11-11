from fastapi import FastAPI

app = FastAPI(title="나의 첫 API")          # 이 app 이 API 서버의 본체 (이름은 꼭 app)


@app.get("/")                                 # 누군가 GET / 으로 요청하면 바로 아래 함수가 답함
def home():
    return {"message": "안녕하세요! 나의 첫 API 입니다."} 
from fastapi import FastAPI

app = FastAPI(title="나의 첫 API")


@app.get("/")
def home():
    return {"message": "안녕하세요! 나의 첫 API 입니다."}


@app.get("/hello/{name}")                     # 주소의 {name} 자리에 온 글이 name 으로 들어옴 (경로 매개변수)
def hello(name: str):
    return {"message": f"{name} 님, 반가워요!"}


@app.get("/add")                              # 주소 뒤 ?a=3&b=5 로 받음 (쿼리 매개변수)
def add(a: int, b: int):                      # int 라고 적으면 FastAPI 가 숫자인지 검사함 → 아니면 422
    return {"a": a, "b": b, "sum": a + b}
  from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="나의 첫 API")


class Question(BaseModel):                    # 요청 본문(JSON)의 모양 — 칸 이름 · 자료형 · 조건
    word: str = Field(min_length=1, max_length=30, description="궁금한 용어")
    style: str = Field(default="초등학생도 알아듣게 쉽게", description="설명 말투")


@app.get("/")
def home():
    return {"message": "안녕하세요! 나의 첫 API 입니다."}


@app.post("/echo")                            # POST /echo — 본문을 받아 그대로 돌려줌 (모양 검사 연습)
def echo(question: Question):                 # 본문이 Question 모양이 아니면 FastAPI 가 422 로 돌려보냄
    return {"received": question.model_dump(), "length": len(question.word)}
  import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

MODEL_NAME = "gemini-3.5-flash-lite"
app = FastAPI(title="AI 용어 설명 API", description="용어를 보내면 Gemini 가 쉬운 말로 설명해 줍니다.")


class Question(BaseModel):
    word: str = Field(min_length=1, max_length=30, description="궁금한 용어")
    style: str = Field(default="초등학생도 알아듣게 쉽게", description="설명 말투")


class Answer(BaseModel):                      # 응답(JSON)의 모양 — /docs 에도 그대로 나옴
    word: str
    answer: str
    tokens: int | None = None


def get_client():
    """키는 서버의 환경 변수 GEMINI_API_KEY 에서 읽음 — 코드 · 저장소에 적지 않음"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="서버에 GEMINI_API_KEY 가 없습니다 — 환경 변수를 확인하세요")
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=60_000, retry_options=types.HttpRetryOptions(http_status_codes=[500, 503])),
    )


def ask_gemini(client, system_instruction, contents):
    """Gemini 에 묻고, 실패하면 알맞은 상태 번호와 한글 안내로 바꿔 돌려보냄"""
    try:
        return client.interactions.create(model=MODEL_NAME, store=False, system_instruction=system_instruction, input=contents)
    except Exception as error:
        code = getattr(error, "status_code", None)
        if code == 429:
            raise HTTPException(status_code=429, detail="Gemini 무료 한도를 넘었습니다 — 1분 뒤 다시 요청하세요")
        raise HTTPException(status_code=502, detail=f"Gemini 요청 실패 (상태 번호 {code})")


@app.get("/")
def home():
    return {"message": "AI 용어 설명 API 입니다. /docs 에서 사용법을 보세요."}


@app.post("/explain", response_model=Answer)
def explain(question: Question):
    client = get_client()
    reply = ask_gemini(client, f"너는 AI 용어 설명 도우미야. {question.style} 3문장 이내로 설명한다.", question.word)
    return Answer(word=question.word, answer=reply.output_text, tokens=reply.usage.total_tokens)
  import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

MODEL_NAME = "gemini-3.5-flash-lite"
MAX_TURNS = 6                                 # 최근 몇 턴을 기억할지
SYSTEM_PROMPT = "너는 '폴리봇'이야. 인공지능소프트웨어과 1학년의 파이썬 · AI 공부 도우미야. 존댓말로 3문장 이내로 답한다. 개인정보를 묻지 않는다."
app = FastAPI(title="AI 용어 설명 API", description="용어를 보내면 Gemini 가 쉬운 말로 설명해 줍니다.")


class Question(BaseModel):
    word: str = Field(min_length=1, max_length=30, description="궁금한 용어")
    style: str = Field(default="초등학생도 알아듣게 쉽게", description="설명 말투")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500, description="이번에 보낼 말")
    history: list[dict] = Field(default_factory=list, description="지난 대화 기록 (이전 응답의 history 를 그대로 보냄)")


class ChatReply(BaseModel):
    answer: str
    history: list[dict]                       # 다음 요청 때 그대로 다시 보낼 기록


class Answer(BaseModel):                      # 응답(JSON)의 모양 — /docs 에도 그대로 나옴
    word: str
    answer: str
    tokens: int | None = None


def get_client():
    """키는 서버의 환경 변수 GEMINI_API_KEY 에서 읽음 — 코드 · 저장소에 적지 않음"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="서버에 GEMINI_API_KEY 가 없습니다 — 환경 변수를 확인하세요")
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=60_000, retry_options=types.HttpRetryOptions(http_status_codes=[500, 503])),
    )


def trim_history(history, max_turns):
    """최근 max_turns 턴만 남긴 새 리스트를 돌려준다 (11주차와 같음)"""
    user_positions = [index for index, step in enumerate(history) if step.get("type") == "user_input"]
    if len(user_positions) <= max_turns:
        return history
    return history[user_positions[-max_turns]:]


def ask_gemini(client, system_instruction, contents):
    """Gemini 에 묻고, 실패하면 알맞은 상태 번호와 한글 안내로 바꿔 돌려보냄"""
    try:
        return client.interactions.create(model=MODEL_NAME, store=False, system_instruction=system_instruction, input=contents)
    except Exception as error:
        code = getattr(error, "status_code", None)
        if code == 429:
            raise HTTPException(status_code=429, detail="Gemini 무료 한도를 넘었습니다 — 1분 뒤 다시 요청하세요")
        raise HTTPException(status_code=502, detail=f"Gemini 요청 실패 (상태 번호 {code})")


@app.get("/")
def home():
    return {"message": "AI 용어 설명 API 입니다. /docs 에서 사용법을 보세요."}


@app.post("/explain", response_model=Answer)
def explain(question: Question):
    client = get_client()
    reply = ask_gemini(client, f"너는 AI 용어 설명 도우미야. {question.style} 3문장 이내로 설명한다.", question.word)
    return Answer(word=question.word, answer=reply.output_text, tokens=reply.usage.total_tokens)


@app.post("/chat", response_model=ChatReply)
def chat(request: ChatRequest):
    """서버는 대화를 기억하지 않음 — 부르는 쪽이 history 를 들고 와서 다시 보냄 (11주차 stateless 방식)"""
    client = get_client()
    send_list = trim_history(request.history + [{"type": "user_input", "content": [{"type": "text", "text": request.message}]}], MAX_TURNS)
    reply = ask_gemini(client, SYSTEM_PROMPT, send_list)
    return ChatReply(answer=reply.output_text, history=send_list + [step.model_dump(mode="json") for step in reply.steps])

    # 챗봇 설정
MAX_TURNS = 8

SYSTEM_PROMPT = """
너는 친절하고 이해하기 쉽게 설명하는 AI 챗봇이다.
사용자의 질문에 정확하고 자연스러운 한국어로 답변한다.
필요하면 예시를 들어 설명한다.
"""

# 챗봇 요청 데이터
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[dict] = Field(default_factory=list)

# 챗봇 응답 데이터
class ChatReply(BaseModel):
    answer: str
    history: list[dict]

# 대화 기록 정리
def trim_history(items, max_turns):
    user_indexes = [
        i for i, item in enumerate(items)
        if item.get("type") == "user_input"
    ]

    if len(user_indexes) <= max_turns:
        return items

    return items[user_indexes[-max_turns]:]

# POST 챗봇 API
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
