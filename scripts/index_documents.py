import json
import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

from build_vector_store import make_hash
from chunk_service_documents import select_text, split_text


ROOT_DIR = Path(__file__).resolve().parent.parent
BATCH_SIZE = 32


def index_documents(
    documents: list[dict],
    collection,
    embeddings,
    model_name: str,
    config: dict,
) -> dict:
    """전달받은 문서만 추가·갱신한다."""
    chunk_size = config["chunk_size"]
    chunk_overlap = config["chunk_overlap"]

    if type(chunk_size) is not int or chunk_size <= 0:
        raise ValueError("chunk_size는 양의 정수여야 해.")

    if (
        type(chunk_overlap) is not int
        or not 0 <= chunk_overlap < chunk_size
    ):
        raise ValueError("chunk_overlap 설정이 올바르지 않아.")

    stored_model = (collection.metadata or {}).get(
        "embedding_model"
    )

    if stored_model != model_name:
        raise ValueError("저장된 임베딩 모델과 현재 모델이 달라.")

    records = {}
    page_prefixes = {}

    # API 호출 전에 모든 문서를 청킹하고 검증
    for document in documents:
        cocktail_id = str(document["cocktail_id"])
        language = document["language"]
        page_id = document["page_id"]
        section_hint = document.get("section_hint") or ""

        selected_text, text_scope = select_text(
            document["text"],
            section_hint,
        )

        pieces = split_text(
            selected_text,
            chunk_size,
            chunk_overlap,
        )

        if not pieces:
            raise ValueError(
                f"저장할 본문이 없어: {document['title']}"
            )

        prefix = f"{cocktail_id}:{language}:{page_id}:"
        page_prefixes[prefix] = cocktail_id

        for index, piece in enumerate(pieces):
            chunk_id = f"{prefix}{index}"

            metadata = {
                "cocktail_id": cocktail_id,
                "related_cocktail": document["related_cocktail"],
                "page_id": page_id,
                "title": document["title"],
                "url": document["url"],
                "source": document["source"],
                "source_type": "external_document",
                "language": language,
                "chunk_index": index,
                "section_hint": section_hint,
                "text_scope": text_scope,
            }

            content_hash = make_hash(
                piece,
                metadata,
                model_name,
            )

            record = {
                "id": chunk_id,
                "text": piece,
                "metadata": {
                    **metadata,
                    "content_hash": content_hash,
                    "embedding_model": model_name,
                },
            }

            if (
                chunk_id in records
                and records[chunk_id] != record
            ):
                raise ValueError(
                    f"같은 ID에 다른 본문이 연결됐어: {chunk_id}"
                )

            records[chunk_id] = record

    if not records:
        return {
            "total": 0,
            "unchanged": 0,
            "indexed": 0,
            "deleted": 0,
        }

    # 이번 문서와 연결된 칵테일의 기존 저장 정보 확인
    existing_hashes = {}
    existing_ids = set()

    for cocktail_id in set(page_prefixes.values()):
        existing = collection.get(
            where={"cocktail_id": cocktail_id},
            include=["metadatas"],
        )

        for record_id, metadata in zip(
            existing["ids"],
            existing["metadatas"],
        ):
            existing_ids.add(record_id)
            existing_hashes[record_id] = (
                metadata or {}
            ).get("content_hash")

    pending = [
        record
        for record in records.values()
        if existing_hashes.get(record["id"])
        != record["metadata"]["content_hash"]
    ]

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

        print(
            f"문서 임베딩 저장: "
            f"{start + len(batch)}/{len(pending)}개"
        )

    # 갱신한 원문에서 청크 수가 줄어든 경우에만 이전 청크 제거
    # 이번에 전달하지 않은 다른 문서는 유지한다.
    prefixes = tuple(page_prefixes)

    stale_ids = [
        record_id
        for record_id in existing_ids
        if (
            record_id.startswith(prefixes)
            and record_id not in records
        )
    ]

    if stale_ids:
        collection.delete(ids=stale_ids)

    # 이번에 저장해야 하는 ID가 실제로 존재하는지 확인
    saved_ids = set()

    record_ids = list(records)

    for start in range(0, len(record_ids), BATCH_SIZE):
        saved = collection.get(
            ids=record_ids[start:start + BATCH_SIZE],
            include=["metadatas"],
        )
        saved_ids.update(saved["ids"])

    if saved_ids != set(records):
        raise ValueError("일부 문서 청크가 저장되지 않았어.")

    return {
        "total": len(records),
        "unchanged": len(records) - len(pending),
        "indexed": len(pending),
        "deleted": len(stale_ids),
    }


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")

    with (ROOT_DIR / "config.json").open(
        encoding="utf-8"
    ) as f:
        config = json.load(f)

    with (
        ROOT_DIR / "data/service/collected_documents_test.json"
    ).open(encoding="utf-8") as f:
        collected = json.load(f)

    model_name = os.environ["GMS_EMBEDDING_MODEL"]

    embeddings = OpenAIEmbeddings(
        model=model_name,
        api_key=os.environ["GMS_KEY"],
        base_url=os.environ["GMS_BASE_URL"],
        check_embedding_ctx_length=False,
        chunk_size=BATCH_SIZE,
        request_timeout=60,
        max_retries=2,
    )

    client = chromadb.PersistentClient(
        path=str(ROOT_DIR / "data/chroma")
    )

    collection = client.get_collection(
        name="cocktail_documents",
        embedding_function=None,
    )

    result = index_documents(
        documents=collected["documents"],
        collection=collection,
        embeddings=embeddings,
        model_name=model_name,
        config=config,
    )

    print(f"\n처리한 청크: {result['total']}개")
    print(f"변경 없음: {result['unchanged']}개")
    print(f"임베딩 저장: {result['indexed']}개")
    print(f"이전 청크 정리: {result['deleted']}개")
    print(f"컬렉션 전체: {collection.count()}개")


if __name__ == "__main__":
    main()