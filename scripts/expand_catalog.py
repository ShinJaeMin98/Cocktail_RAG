"""전체 정제 데이터를 서비스 검색 대상으로 준비한다. API 호출은 하지 않는다."""
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def load_json(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_search_text(item):
    ingredients = ", ".join(
        f"{ingredient['name']} ({ingredient.get('measure') or '분량 미기재'})"
        for ingredient in item["ingredients"]
    )
    return "\n".join([
        f"칵테일 이름: {item['name']}",
        f"분류: {item['category']}",
        f"알코올 여부: {item['alcoholic']}",
        f"잔 종류: {item['glass']}",
        f"재료와 분량: {ingredients}",
        f"제조법: {item['instructions']}",
    ])


def main():
    original_path = ROOT_DIR / "data/processed/cocktails.json"
    service_dir = ROOT_DIR / "data/service"
    reviewed_path = service_dir / "cocktails.json"
    documents_path = service_dir / "documents.json"
    output_path = service_dir / "cocktails_all.json"

    cocktails = load_json(original_path)
    reviewed = load_json(reviewed_path)
    documents = load_json(documents_path)
    if not isinstance(cocktails, list) or not cocktails:
        raise ValueError("전체 칵테일 데이터가 비어 있어.")
    reviewed_by_id = {str(item["id"]): item for item in reviewed}
    document_ids = {str(item["cocktail_id"]) for item in documents if item.get("text", "").strip()}
    rows = []
    seen = set()
    for item in cocktails:
        cocktail_id = str(item["id"])
        if cocktail_id in seen:
            raise ValueError(f"중복 칵테일 ID: {cocktail_id}")
        seen.add(cocktail_id)
        for key in ("name", "category", "alcoholic", "glass", "instructions", "source", "source_url"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f"필수 항목 누락: {cocktail_id} / {key}")
        if not item.get("ingredients"):
            raise ValueError(f"재료 누락: {cocktail_id}")
        row = {**item, "id": cocktail_id}
        previous = reviewed_by_id.get(cocktail_id)
        # 같은 원천 자료의 기존 검색용 텍스트는 보존해 재임베딩을 줄인다.
        compare_keys = ("name", "category", "alcoholic", "glass", "ingredients", "instructions")
        if previous and all(previous.get(key) == item.get(key) for key in compare_keys) and previous.get("search_text"):
            row["search_text"] = previous["search_text"]
        else:
            row["search_text"] = build_search_text(row)
        row["has_reviewed_document"] = cocktail_id in document_ids
        rows.append(row)
    if set(reviewed_by_id) - seen:
        raise ValueError("검토한 칵테일 일부가 전체 데이터에 없어.")
    service_dir.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    temporary.replace(output_path)
    linked_count = sum(row["has_reviewed_document"] for row in rows)
    print(f"전체 검색 대상: {len(rows)}개")
    print(f"검토한 설명 문서 연결 있음: {linked_count}개")
    print(f"기본 레시피부터 제공: {len(rows) - linked_count}개")
    print(f"저장 위치: {output_path}")
    print("기존 cocktails.json, documents.json과 벡터 DB는 변경하지 않았어.")


if __name__ == "__main__":
    main()
