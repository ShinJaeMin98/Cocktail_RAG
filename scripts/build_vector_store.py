import hashlib
import json
import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data/service"
DB_DIR = ROOT_DIR / "data/chroma"

BATCH_SIZE = 32


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def make_hash(text: str, metadata: dict, model_name: str) -> str:
    payload = {
        "text": text,
        "metadata": metadata,
        "embedding_model": model_name,
    }

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def prepare_records(cocktails: list, chunks: list):
    metadata_records = []
    document_records = []

    cocktail_ids = {str(item["id"]) for item in cocktails}

    for item in cocktails:
        metadata_records.append({
            "id": f"cocktail:{item['id']}",
            "text": item["search_text"],
            "metadata": {
                "cocktail_id": str(item["id"]),
                "title": item["name"],
                "category": item["category"],
                "alcoholic": item["alcoholic"],
                "glass": item["glass"],
                "source": item["source"],
                "url": item["source_url"],
                "source_type": "cocktail_metadata",
            },
        })

    for chunk in chunks:
        metadata = dict(chunk["metadata"])
        metadata["cocktail_id"] = str(metadata["cocktail_id"])

        if metadata["cocktail_id"] not in cocktail_ids:
            raise ValueError(
                f"서비스에 없는 칵테일의 청크야: {chunk['id']}"
            )

        document_records.append({
            "id": chunk["id"],
            "text": chunk["text"],
            "metadata": metadata,
        })

    # API 요청 전에 입력 데이터 검증
    for records in (metadata_records, document_records):
        ids = [record["id"] for record in records]

        if len(ids) != len(set(ids)):
            raise ValueError("중복된 저장 ID가 있어.")

        for record in records:
            if (
                not isinstance(record["text"], str)
                or not record["text"].strip()
            ):
                raise ValueError(
                    f"검색용 텍스트가 비어 있어: {record['id']}"
                )

    # 전체 목록에는 외부 문서가 아직 없는 칵테일도 포함될 수 있다.
    return metadata_records, document_records


def sync_collection(
    collection,
    records: list,
    embeddings,
    model_name: str,
) -> None:
    existing = collection.get(include=["metadatas"])

    existing_hashes = {
        record_id: (metadata or {}).get("content_hash")
        for record_id, metadata in zip(
            existing["ids"],
            existing["metadatas"],
        )
    }

    pending = []

    for record in records:
        content_hash = make_hash(
            record["text"],
            record["metadata"],
            model_name,
        )

        if existing_hashes.get(record["id"]) == content_hash:
            continue

        pending.append({
            **record,
            "metadata": {
                **record["metadata"],
                "content_hash": content_hash,
                "embedding_model": model_name,
            },
        })

    print(f"\n컬렉션: {collection.name}")
    print(f"입력 항목: {len(records)}개")
    print(f"변경 없음: {len(records) - len(pending)}개")
    print(f"임베딩 대상: {len(pending)}개")

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start:start + BATCH_SIZE]

        vectors = embeddings.embed_documents(
            [record["text"] for record in batch]
        )

        collection.upsert(
            ids=[record["id"] for record in batch],
            documents=[record["text"] for record in batch],
            metadatas=[record["metadata"] for record in batch],
            embeddings=vectors,
        )

        completed = start + len(batch)
        print(f"저장 진행: {completed}/{len(pending)}개")

    # 초기 파일에 없는 실시간 추가 문서를 삭제하지 않는다.
    saved = collection.get(include=["metadatas"])
    expected_ids = {record["id"] for record in records}
    if not expected_ids.issubset(set(saved["ids"])):
        raise ValueError("일부 항목이 저장되지 않았어.")
    count = collection.count()
    print("기존 추가 데이터: 보존")

    print(f"최종 저장: {count}개")


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")

    model_name = os.environ["GMS_EMBEDDING_MODEL"]

    catalog_path = DATA_DIR / "cocktails_all.json"
    if not catalog_path.exists():
        raise FileNotFoundError("먼저 scripts/expand_catalog.py를 실행해줘.")
    cocktails = load_json(catalog_path)
    chunks_path = DATA_DIR / "wiki_chunks.json"
    chunks = load_json(chunks_path) if chunks_path.exists() else []

    metadata_records, document_records = prepare_records(
        cocktails,
        chunks,
    )

    embeddings = OpenAIEmbeddings(
        model=model_name,
        api_key=os.environ["GMS_KEY"],
        base_url=os.environ["GMS_BASE_URL"],
        check_embedding_ctx_length=False,
        chunk_size=BATCH_SIZE,
        request_timeout=60,
        max_retries=2,
    )

    client = chromadb.PersistentClient(path=str(DB_DIR))

    collections = []

    for name, records in (
        ("cocktail_metadata", metadata_records),
        ("cocktail_documents", document_records),
    ):
        collection = client.get_or_create_collection(
            name=name,
            embedding_function=None,
            metadata={"embedding_model": model_name},
        )

        stored_model = (collection.metadata or {}).get(
            "embedding_model"
        )

        if stored_model != model_name:
            raise ValueError(
                f"{name}의 임베딩 모델 설정이 달라. "
                f"기존: {stored_model}, 현재: {model_name}"
            )

        collections.append((collection, records))

    print(f"임베딩 모델: {model_name}")
    print(f"저장 위치: {DB_DIR}")

    for collection, records in collections:
        sync_collection(
            collection,
            records,
            embeddings,
            model_name,
        )

    print("\n벡터 저장 완료")


if __name__ == "__main__":
    main()