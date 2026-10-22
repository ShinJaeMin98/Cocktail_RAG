import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data/processed"


def load_json(filename):
    with (DATA_DIR / filename).open(encoding="utf-8") as f:
        return json.load(f)


def main():
    cocktails = load_json("cocktails.json")
    coverage = load_json("wiki_coverage.json")
    title_candidates = load_json("wiki_title_candidates.json")

    ids_by_name = {
        item["name"]: item["id"]
        for item in cocktails
    }

    merged = {}

    def add_candidate(cocktail_id, name, candidate):
        if cocktail_id not in merged:
            merged[cocktail_id] = {
                "cocktail_id": cocktail_id,
                "cocktail_name": name,
                "review_status": "pending",
                "candidates": [],
            }

        candidates = merged[cocktail_id]["candidates"]

        # 같은 항목에 같은 URL을 중복 등록하지 않음
        if not any(
            item["url"] == candidate["url"]
            for item in candidates
        ):
            candidates.append(candidate)

    # 최초 조사에서 얻은 음료 관련 문서 후보
    for item in coverage.values():
        if item["status"] != "drink_candidate":
            continue

        add_candidate(
            item["cocktail_id"],
            item["cocktail_name"],
            {
                "title": item["english_title"],
                "url": item["english_url"],
                "korean_title": item["korean_title"],
                "intro": item["intro"],
                "discovery_method": "exact_title",
            },
        )

    # 이름 뒤에 (cocktail)을 붙여 찾은 문서 후보
    for item in title_candidates:
        name = item["cocktail_name"]
        cocktail_id = item.get("cocktail_id") or ids_by_name[name]

        add_candidate(
            cocktail_id,
            name,
            {
                "title": item["title"],
                "url": item["url"],
                "korean_title": item["korean_title"],
                "intro": item["intro"],
                "discovery_method": "cocktail_suffix",
            },
        )

    result = sorted(
        merged.values(),
        key=lambda item: item["cocktail_name"].lower(),
    )

    output_path = DATA_DIR / "wiki_candidates_merged.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"후보가 있는 칵테일: {len(result)}개")
    print(
        "문서 후보 연결 수:",
        sum(len(item["candidates"]) for item in result),
    )
    print("검토 상태: 모두 검토 대기(pending)")
    print(f"저장 위치: {output_path}")


if __name__ == "__main__":
    main()