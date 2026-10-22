import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pathlib import Path

# scripts 폴더의 한 단계 위 = 프로젝트 최상위
ROOT_DIR = Path(__file__).resolve().parent.parent

# 이 파일과 같은 폴더의 .env 읽기
load_dotenv(ROOT_DIR / ".env")

key = os.getenv("GMS_KEY", "").strip()
base_url = os.getenv("GMS_BASE_URL", "").strip()
model_name = os.getenv("GMS_MODEL", "").strip()

if not key or not base_url or not model_name:
    raise SystemExit(
        ".env의 GMS_KEY, GMS_BASE_URL, GMS_MODEL을 확인해줘."
    )

if model_name == "GMS에서_확인한_정확한_모델_ID":
    raise SystemExit(
        "GMS_MODEL을 실제 API 모델 ID로 바꿔줘."
    )

model = ChatOpenAI(
    model=model_name,
    api_key=key,
    base_url=base_url,
    timeout=60,
    max_retries=0,  # 연결 테스트에서는 자동 재시도하지 않음
)

print(f"사용 모델: {model_name}")
print("GMS 연결 확인 중...")

response = model.invoke([
    {
        "role": "user",
        "content": "'연결 성공'이라는 문구만 출력해줘."
    }
])

print("응답:", response.content)
print("토큰 사용량:", response.usage_metadata)