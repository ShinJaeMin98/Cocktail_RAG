import json
import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent

INPUT_PATH = ROOT_DIR / "data/service/documents.json"
CONFIG_PATH = ROOT_DIR / "config.json"

OUTPUT_PATH = ROOT_DIR / "data/service/wiki_chunks.json"
CHECK_PATH = ROOT_DIR / "data/service/section_checks.json"


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def select_text(
    text: str,
    section_hint: str,
) -> tuple[str, str]:
    """추출한 본문과 추출 방식을 반환한다."""
    if not section_hint:
        return text.strip(), "full_document"

    target = normalize(section_hint)

    # 1. 정확히 일치하는 소제목 아래의 본문 추출
    heading_pattern = re.compile(
        r"^(={2,6})[ \t]*(.*?)[ \t]*\1[ \t]*$",
        re.MULTILINE,
    )
    headings = list(heading_pattern.finditer(text))

    for index, heading in enumerate(headings):
        title = heading.group(2).strip()

        if normalize(title) != target:
            continue

        end = (
            headings[index + 1].start()
            if index + 1 < len(headings)
            else len(text)
        )

        body = text[heading.end():end].strip()

        if not body:
            raise ValueError(
                f"소제목 아래에 본문이 없어: {section_hint}"
            )

        return f"{title}\n{body}", "matched_section"

    # 2. 이름 다음 줄에 설명이 있는 목록 형태 처리
    lines = [line.strip() for line in text.splitlines()]

    for index, line in enumerate(lines):
        if normalize(line) != target:
            continue

        for next_line in lines[index + 1:]:
            if not next_line:
                continue

            if next_line.startswith("=="):
                break

            return f"{line}\n{next_line}", "named_entry"

    # 3. 별도 소제목 없이 설명 문장으로 등장하는 항목 처리
    line_prefixes = {
        "dirty martini": "A dirty martini contains",
        "dry martini": "In modern terminology, a dry martini",
        "godmother": "The godmother cocktail uses",
        "miami vice": "Lava Flow or Miami Vice",
    }

    prefix = line_prefixes.get(target)

    if prefix:
        for line in lines:
            if not normalize(line).startswith(normalize(prefix)):
                continue

            # Godmother 뒤에 이어지는 Godchild 설명 제외
            if target == "godmother":
                line = re.split(
                    r"\s+The godchild\b",
                    line,
                    maxsplit=1,
                    flags=re.IGNORECASE,
                )[0]

            return line, "matched_line"

    raise ValueError(
        f"관련 설명을 추출하지 못했어: {section_hint}"
    )


def split_text(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """설정한 글자 수와 중첩 길이로 본문을 나눈다."""
    text = text.strip()

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end == len(text):
            break

        start = end - chunk_overlap

    return chunks


def main() -> None:
    config = load_json(CONFIG_PATH)

    chunk_size = config["chunk_size"]
    chunk_overlap = config["chunk_overlap"]

    if type(chunk_size) is not int or chunk_size <= 0:
        raise ValueError("chunk_size는 양의 정수여야 해.")

    if (
        type(chunk_overlap) is not int
        or not 0 <= chunk_overlap < chunk_size
    ):
        raise ValueError(
            "chunk_overlap은 0 이상, chunk_size 미만인 정수여야 해."
        )

    documents = load_json(INPUT_PATH)

    if not isinstance(documents, list):
        raise ValueError("documents.json은 목록 형태여야 해.")

    all_chunks = []
    section_checks = []
    chunk_ids = set()

    for document in documents:
        cocktail_id = str(document["cocktail_id"])
        cocktail_name = document["related_cocktail"]
        page_id = document["page_id"]
        language = document.get("language", "en")

        section_hint = document.get("section_hint") or ""
        text = document["text"]

        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                f"문서 본문이 비어 있어: {cocktail_name}"
            )

        try:
            selected_text, text_scope = select_text(
                text,
                section_hint,
            )
        except ValueError as e:
            raise ValueError(
                f"{cocktail_name} / {document['title']}: {e}"
            ) from e

        if section_hint:
            section_checks.append({
                "cocktail_name": cocktail_name,
                "document_title": document["title"],
                "section_hint": section_hint,
                "text_scope": text_scope,
                "original_length": len(text),
                "selected_length": len(selected_text),
                "selected_text": selected_text,
            })

        pieces = split_text(
            selected_text,
            chunk_size,
            chunk_overlap,
        )

        for index, piece in enumerate(pieces):
            chunk_id = (
                f"{cocktail_id}:{language}:{page_id}:{index}"
            )

            if chunk_id in chunk_ids:
                raise ValueError(
                    f"중복 청크 ID가 발생했어: {chunk_id}"
                )

            chunk_ids.add(chunk_id)

            all_chunks.append({
                "id": chunk_id,
                "text": piece,
                "metadata": {
                    "cocktail_id": cocktail_id,
                    "related_cocktail": cocktail_name,
                    "page_id": page_id,
                    "title": document["title"],
                    "url": document["url"],
                    "source": document.get(
                        "source",
                        "위키백과",
                    ),
                    "source_type": "external_document",
                    "language": language,
                    "chunk_index": index,
                    "section_hint": section_hint,
                    "text_scope": text_scope,
                },
            })

        print(
            f"{cocktail_name}: "
            f"{len(text):,}자 → "
            f"사용 {len(selected_text):,}자 → "
            f"{len(pieces)}개 청크"
        )

    # 모든 문서를 정상 처리한 뒤 결과 저장
    save_json(OUTPUT_PATH, all_chunks)
    save_json(CHECK_PATH, section_checks)

    unique_documents = {
        (
            document.get("language", "en"),
            document["page_id"],
        )
        for document in documents
    }

    print(f"\n항목별 문서 연결: {len(documents)}개")
    print(f"고유 원문 문서: {len(unique_documents)}개")
    print(f"부분 추출 검토 대상: {len(section_checks)}개")
    print(f"전체 청크: {len(all_chunks)}개")
    print(f"\n청크 저장 위치: {OUTPUT_PATH}")
    print(f"검토 파일 위치: {CHECK_PATH}")


if __name__ == "__main__":
    main()