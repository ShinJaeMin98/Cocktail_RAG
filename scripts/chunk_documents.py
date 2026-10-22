import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = ROOT_DIR / "data/wiki"
OUTPUT_PATH = ROOT_DIR / "data/processed/wiki_chunks.json"

# 청킹 설정 — 단위는 문자 수
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def split_text(text):
    text = text.strip()

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end])

        if end == len(text):
            break

        start = end - CHUNK_OVERLAP

    return chunks


def main():
    if not 0 <= CHUNK_OVERLAP < CHUNK_SIZE:
        raise ValueError("중복 길이는 0 이상, 청크 크기 미만이어야 해.")

    files = sorted(INPUT_DIR.glob("*.json"))

    if not files:
        raise ValueError("data/wiki에 문서 JSON이 없어.")

    all_chunks = []
    seen_ids = set()

    for path in files:
        with path.open(encoding="utf-8") as f:
            document = json.load(f)

        pieces = split_text(document["text"])

        if not pieces:
            raise ValueError(f"본문이 비어 있어: {path.name}")

        for index, text in enumerate(pieces):
            # 칵테일 ID를 포함해 다른 항목의 청크와 충돌 방지
            chunk_id = (
                f"{document['cocktail_id']}:"
                f"ko:{document['page_id']}:{index}"
            )

            if chunk_id in seen_ids:
                raise ValueError(f"중복 청크 ID: {chunk_id}")

            seen_ids.add(chunk_id)

            all_chunks.append({
                "id": chunk_id,
                "text": text,
                "metadata": {
                    "cocktail_id": document["cocktail_id"],
                    "related_cocktail": document["related_cocktail"],
                    "page_id": document["page_id"],
                    "title": document["title"],
                    "url": document["url"],
                    "source": document["source"],
                    "source_type": "external_document",
                    "language": "ko",
                    "chunk_index": index,
                },
            })

        print(
            f"{document['title']}: "
            f"{len(document['text'])}자 → {len(pieces)}개 청크"
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"\n처리 문서: {len(files)}개")
    print(f"전체 청크: {len(all_chunks)}개")
    print(f"저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()