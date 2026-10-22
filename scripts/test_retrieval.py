import json
import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def main() -> None:
    with (ROOT_DIR / "config.json").open(
        encoding="utf-8"
    ) as f:
        config = json.load(f)

    cocktail_id = "11000"
    question = "모히토는 어디에서 유래했고, 민트는 어떻게 사용해?"
    top_k = config["top_k"]

    if type(top_k) is not int or top_k <= 0:
        raise ValueError("top_k는 양의 정수여야 해.")

    embeddings = OpenAIEmbeddings(
        model=os.environ["GMS_EMBEDDING_MODEL"],
        api_key=os.environ["GMS_KEY"],
        base_url=os.environ["GMS_BASE_URL"],
        check_embedding_ctx_length=False,
        request_timeout=60,
        max_retries=2,
    )

    client = chromadb.PersistentClient(
        path=str(ROOT_DIR / "data/chroma")
    )

    metadata_collection = client.get_collection(
        name="cocktail_metadata",
        embedding_function=None,
    )
    document_collection = client.get_collection(
        name="cocktail_documents",
        embedding_function=None,
    )

    # 선택한 칵테일의 기본 정보는 유사도와 관계없이 확보
    metadata_result = metadata_collection.get(
        ids=[f"cocktail:{cocktail_id}"],
        include=["documents", "metadatas"],
    )

    if not metadata_result["ids"]:
        raise ValueError("선택한 칵테일의 기본 정보가 없어.")

    print("선택한 칵테일 기본 정보:")
    print(metadata_result["documents"][0])

    # 선택한 칵테일에 연결된 문서가 있는지 먼저 확인
    linked = document_collection.get(
        where={"cocktail_id": cocktail_id},
        include=["metadatas"],
    )

    if not linked["ids"]:
        raise ValueError("선택한 칵테일의 문서 청크가 없어.")

    print(f"\n질문: {question}")
    print(f"연결된 청크: {len(linked['ids'])}개")

    query_vector = embeddings.embed_query(question)

    # 다른 칵테일의 청크가 섞이지 않도록 필터 적용
    result = document_collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, len(linked["ids"])),
        where={"cocktail_id": cocktail_id},
        include=["documents", "metadatas", "distances"],
    )

    print("\n문서 검색 결과:")

    for number, (chunk_id, text, metadata, distance) in enumerate(
        zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        ),
        start=1,
    ):
        if metadata["cocktail_id"] != cocktail_id:
            raise ValueError("다른 칵테일의 청크가 검색됐어.")

        print(f"\n[{number}] {metadata['title']}")
        print(f"청크 ID: {chunk_id}")
        print(f"거리: {distance:.4f}")
        print(f"원문: {metadata['url']}")
        print(f"본문:\n{text}")

    print("\n검색 확인 완료")


if __name__ == "__main__":
    main()