import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data/processed"
REVIEW_DIR = ROOT_DIR / "data/wiki_review"
OUTPUT_DIR = ROOT_DIR / "data/service"

# 현재 연결된 문서가 해당 레시피를 설명하지 않는 항목
EXCLUDED = {
    "17186": "Clover Club이 아닌 바텐더 인물 문서에 연결됨",
    "14608": "럼·진저에일 레시피가 일반 탄산음료 문서에 연결됨",
    "16250": "칵테일이 아닌 주류 밀수 행위 문서에 연결됨",
    "14087": "동명 칵테일이지만 주요 재료가 다른 문서에 연결됨",
}

# 첫 서비스 목록에서는 제외하고 추가 검토할 항목
ON_HOLD = {
    "17195": "Bellini: 복숭아 재료와 와인 종류 차이 확인 필요",
    "17203": "Kir: 보유 레시피가 Kir royal 설명에 가까움",
    "17212": "Espresso Martini: 재료 목록에 에스프레소 누락",
    "17208": "Rose: 문서와 보유 레시피의 주요 재료 차이",
    "11124": "Boomerang: 문서에 보유 레시피와 같은 변형이 있는지 확인 필요",
    "12820": "Irish Cream: 스카치 기반 보유 레시피와 문서 설명 차이",
    "12798": "Coffee Liqueur: 목록의 짧은 정의만으로 설명이 충분한지 확인 필요",
    "12518": "Whisky Mac: 보유 데이터의 Wine이 진저 와인인지 불명확",
    "17191": "Planter's Punch: 문서와 보유 레시피의 재료 차이",
    "13202": "Flaming Dr. Pepper: 문서와 보유 레시피의 구성 차이",
}

# 후보가 두 개 있는 경우 사용할 문서를 명시
PREFERRED_TITLES = {
    "15330": "Orange Crush (cocktail)",
    "17249": "Pegu Club (cocktail)",
}

# 기본형·목록 문서에 해당 항목 설명이 있는 경우
SECTION_HINTS = {
    "17181": "dirty martini",
    "11005": "dry martini",
    "14167": "vodka martini",
    "11387": "Frozen daiquiri",
    "11424": "godmother",
    "13936": "Miami Vice",
    "11410": "Gin fizz",
    "11417": "Gin sour",
    "178367": "Ramos gin fizz",
    "12776": "Melya",
    "17214": "Russian spring punch",
}


def load_json(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(filename, data):
    with (OUTPUT_DIR / filename).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    cocktails = load_json(DATA_DIR / "cocktails.json")
    merged = load_json(DATA_DIR / "wiki_candidates_merged.json")

    cocktails_by_id = {
        item["id"]: item
        for item in cocktails
    }

    # 요청한 제목을 기준으로 수집 문서 연결
    documents_by_title = {}

    for path in sorted(REVIEW_DIR.glob("*.json")):
        document = load_json(path)

        if document.get("text", "").strip():
            documents_by_title[document["requested_title"]] = document

    selected_cocktails = []
    selected_documents = []
    review_log = []

    for item in merged:
        cocktail_id = item["cocktail_id"]
        name = item["cocktail_name"]

        if cocktail_id in EXCLUDED:
            review_log.append({
                "cocktail_id": cocktail_id,
                "name": name,
                "status": "excluded",
                "reason": EXCLUDED[cocktail_id],
            })
            continue

        if cocktail_id in ON_HOLD:
            review_log.append({
                "cocktail_id": cocktail_id,
                "name": name,
                "status": "on_hold",
                "reason": ON_HOLD[cocktail_id],
            })
            continue

        candidates = item["candidates"]

        if cocktail_id in PREFERRED_TITLES:
            preferred = PREFERRED_TITLES[cocktail_id]
            candidates = [
                candidate
                for candidate in candidates
                if candidate["title"] == preferred
            ]

        # 잘못된 후보를 임의로 선택하지 않도록 확인
        if len(candidates) != 1:
            raise ValueError(
                f"{name}: 문서 후보가 {len(candidates)}개야. "
                "사용할 문서를 명시해야 해."
            )

        candidate = candidates[0]
        title = candidate["title"]

        if title not in documents_by_title:
            raise ValueError(f"{name}: 수집한 본문이 없어 — {title}")

        original_document = documents_by_title[title]

        section_hint = SECTION_HINTS.get(cocktail_id, "")

        if (
            section_hint
            and section_hint.casefold()
            not in original_document["text"].casefold()
        ):
            raise ValueError(
                f"{name}: 예상한 설명 구간을 찾지 못했어 — {section_hint}"
            )

        cocktail = dict(cocktails_by_id[cocktail_id])

        # 기존 426개 파일을 덮어쓰지 않고 검색 텍스트 재구성
        ingredient_text = ", ".join(
            f"{ingredient['name']} "
            f"({ingredient['measure'] or '분량 미기재'})"
            for ingredient in cocktail["ingredients"]
        )

        cocktail["search_text"] = "\n".join([
            f"칵테일 이름: {cocktail['name']}",
            f"분류: {cocktail['category']}",
            f"알코올 여부: {cocktail['alcoholic']}",
            f"잔 종류: {cocktail['glass']}",
            f"재료와 분량: {ingredient_text}",
            f"제조법: {cocktail['instructions']}",
        ])

        selected_cocktails.append(cocktail)

        # 같은 위키 문서도 칵테일별 연결 정보는 따로 구성
        selected_documents.append({
            "page_id": original_document["page_id"],
            "title": original_document["title"],
            "url": original_document["url"],
            "text": original_document["text"],
            "source": original_document["source"],
            "language": original_document["language"],
            "cocktail_id": cocktail_id,
            "related_cocktail": name,
            "section_hint": section_hint,
            "collected_at": original_document["collected_at"],
            "selection_method": "사전 문서 연결 검토",
        })

        review_log.append({
            "cocktail_id": cocktail_id,
            "name": name,
            "status": "selected",
            "document_title": title,
            "section_hint": section_hint,
        })

    # 모든 검사를 통과한 뒤 결과 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    save_json("cocktails.json", selected_cocktails)
    save_json("documents.json", selected_documents)
    save_json("review_log.json", review_log)

    unique_documents = {
        (document["language"], document["page_id"])
        for document in selected_documents
    }

    print(f"검토 대상 칵테일: {len(merged)}개")
    print(f"서비스 선정: {len(selected_cocktails)}개")
    print(
        "제외:",
        sum(item["status"] == "excluded" for item in review_log),
        "개",
    )
    print(
        "보류:",
        sum(item["status"] == "on_hold" for item in review_log),
        "개",
    )
    print(f"항목별 문서 연결: {len(selected_documents)}개")
    print(f"고유 문서: {len(unique_documents)}개")
    print(f"저장 위치: {OUTPUT_DIR}")

    if len(selected_cocktails) < 100:
        print("100개 미만이므로 추가 문서 확보가 필요해.")


if __name__ == "__main__":
    main()