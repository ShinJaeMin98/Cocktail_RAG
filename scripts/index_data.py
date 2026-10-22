import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

DB_DIR = ROOT_DIR / "data/chroma"
BATCH_SIZE = 32


def load_json(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def index_records(store, records):
    # 저장된 텍스트와 메타데이터 확인
    existing = store.get(include=["documents", "metadatas"])

    saved = {
        record_id: (text, metadata)
        for record_id, text, metadata in zip(
            existing["ids"],
            existing["documents"],
            existing["metadatas"],
        )
    }

    pending = [
        record
        for record in records
        if saved.get(record["id"]) != (
            record["text"],
            record["metadata"],
        )
    ]

    print(f"입력: {len(records)}개")
    print(f"변경 없음: {len(records) - len(pending)}개")
    print(f"추가 또는 갱신: {len(pending)}개")

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start:start + BATCH_SIZE]

        store.add_texts(
            texts=[record["text"] for record in batch],
            metadatas=[record["metadata"] for record in batch],
            ids=[record["id"] for record in batch],
        )

        print(f"  처리: {min(start + BATCH_SIZE, len(pending))}/{len(pending)}")

    print(f"현재 저장 건수: {len(store.get()['ids'])}개")


def main():
    for key in ["GMS_KEY", "GMS_BASE_URL", "GMS_EMBEDDING_MODEL"]:
        if not os.getenv(key, "").strip():
            raise ValueError(f".env의 {key} 값을 확인해줘.")

    cocktails = load_json(
        ROOT_DIR / "data/processed/cocktails_search.json"
    )
    wiki_chunks = load_json(
        ROOT_DIR / "data/processed/wiki_chunks.json"
    )

    meta_records = [
        {
            "id": cocktail["id"],
            "text": cocktail["search_text"],
            "metadata": {
                "cocktail_id": cocktail["id"],
                "name": cocktail["name"],
                "category": cocktail["category"],
                "alcoholic": cocktail["alcoholic"],
                "glass": cocktail["glass"],
                "source": cocktail["source"],
                "url": cocktail["source_url"],
                "source_type": "item_metadata",
            },
        }
        for cocktail in cocktails
    ]

    # 입력 데이터 검사
    for records in [meta_records, wiki_chunks]:
        ids = [record["id"] for record in records]

        if len(ids) != len(set(ids)):
            raise ValueError("입력 데이터에 중복 ID가 있어.")

        if any(not record["text"].strip() for record in records):
            raise ValueError("비어 있는 검색용 텍스트가 있어.")

    embeddings = OpenAIEmbeddings(
        model=os.environ["GMS_EMBEDDING_MODEL"],
        api_key=os.environ["GMS_KEY"],
        base_url=os.environ["GMS_BASE_URL"],
        check_embedding_ctx_length=False,
        request_timeout=60,
        max_retries=0,
    )

    DB_DIR.mkdir(parents=True, exist_ok=True)

    # 다른 임베딩 모델로 기존 DB를 실수로 재사용하지 않도록 기록
    settings_path = DB_DIR / "embedding_settings.json"
    settings = {
        "model": os.environ["GMS_EMBEDDING_MODEL"],
        "base_url": os.environ["GMS_BASE_URL"],
    }

    if settings_path.exists():
        if load_json(settings_path) != settings:
            raise ValueError(
                "기존 DB의 임베딩 설정과 달라. "
                "같은 모델을 사용하거나 별도 DB 경로를 사용해줘."
            )
    else:
        with settings_path.open("w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    meta_store = Chroma(
        collection_name="cocktail_meta",
        embedding_function=embeddings,
        persist_directory=str(DB_DIR),
    )

    docs_store = Chroma(
        collection_name="cocktail_docs",
        embedding_function=embeddings,
        persist_directory=str(DB_DIR),
    )

    print("\n[칵테일 메타데이터]")
    index_records(meta_store, meta_records)

    print("\n[위키 문서 청크]")
    index_records(docs_store, wiki_chunks)

    print(f"\nDB 저장 위치: {DB_DIR}")


if __name__ == "__main__":
    main()