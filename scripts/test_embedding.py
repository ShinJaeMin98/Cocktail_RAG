import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

required_keys = [
    "GMS_KEY",
    "GMS_BASE_URL",
    "GMS_EMBEDDING_MODEL",
]

for key in required_keys:
    if not os.getenv(key, "").strip():
        raise SystemExit(f".env의 {key} 값을 확인해줘.")

embeddings = OpenAIEmbeddings(
    model=os.environ["GMS_EMBEDDING_MODEL"],
    api_key=os.environ["GMS_KEY"],
    base_url=os.environ["GMS_BASE_URL"],
    check_embedding_ctx_length=False,
    request_timeout=60,
    max_retries=0,
)

text = "모히토는 럼, 민트, 라임 등을 사용하는 칵테일이다."

print("사용 모델:", os.environ["GMS_EMBEDDING_MODEL"])
print("임베딩 요청 중...")

vector = embeddings.embed_query(text)

print("임베딩 성공")
print("벡터 차원:", len(vector))
print("앞의 숫자 5개:", vector[:5])