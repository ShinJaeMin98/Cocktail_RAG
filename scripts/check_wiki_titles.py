import json
import time
from pathlib import Path

from audit_wiki_coverage import request_api

ROOT_DIR = Path(__file__).resolve().parent.parent

INPUT_PATH = ROOT_DIR / "data/processed/cocktails.json"
OUTPUT_PATH = ROOT_DIR / "data/processed/wiki_title_candidates.json"

BATCH_SIZE = 20


def main():
    with INPUT_PATH.open(encoding="utf-8") as f:
        cocktails = json.load(f)

    # 기존 10개 조사 결과도 재사용
    if OUTPUT_PATH.exists():
        with OUTPUT_PATH.open(encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = []

    completed_names = {
        record["cocktail_name"] for record in records
    }

    pending = [
        item for item in cocktails
        if item["name"] not in completed_names
    ]

    print(f"전체 칵테일: {len(cocktails)}개")
    print(f"기존 후보 연결 항목: {len(completed_names)}개")
    print(f"이번 조사 대상: {len(pending)}개")

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start:start + BATCH_SIZE]

        # 원래 표기와 소문자 표기를 함께 확인
        titles_by_id = {}

        for cocktail in batch:
            name = cocktail["name"]

            titles_by_id[cocktail["id"]] = list(dict.fromkeys([
                f"{name} (cocktail)",
                f"{name[:1].upper() + name[1:].lower()} (cocktail)",
            ]))

        titles = list(dict.fromkeys(
            title
            for names in titles_by_id.values()
            for title in names
        ))

        data = request_api({
            "action": "query",
            "titles": "|".join(titles),
            "redirects": 1,
            "prop": "extracts|info|pageprops|langlinks",
            "explaintext": 1,
            "exintro": 1,
            "inprop": "url",
            "ppprop": "disambiguation",
            "lllang": "ko",
            "lllimit": "max",
            "format": "json",
            "formatversion": 2,
        })

        query = data.get("query", {})

        # 정규화·넘겨주기된 제목 추적
        title_map = {}

        for item in query.get("normalized", []):
            title_map[item["from"]] = item["to"]

        for item in query.get("redirects", []):
            title_map[item["from"]] = item["to"]

        pages = {
            page["title"]: page
            for page in query.get("pages", [])
        }

        for cocktail in batch:
            found = {}

            for title in titles_by_id[cocktail["id"]]:
                visited = set()

                while title in title_map and title not in visited:
                    visited.add(title)
                    title = title_map[title]

                page = pages.get(title)

                if not page:
                    continue

                if "missing" in page or "invalid" in page:
                    continue

                if "disambiguation" in page.get("pageprops", {}):
                    continue

                intro = page.get("extract", "").strip()

                if not intro:
                    continue

                korean_title = next(
                    (
                        link["title"]
                        for link in page.get("langlinks", [])
                        if link["lang"] == "ko"
                    ),
                    "",
                )

                found[page["pageid"]] = {
                    "cocktail_id": cocktail["id"],
                    "cocktail_name": cocktail["name"],
                    "page_id": page["pageid"],
                    "title": page["title"],
                    "url": page["fullurl"],
                    "korean_title": korean_title,
                    "intro": intro,
                }

            records.extend(found.values())

            if found:
                print(
                    f"후보 발견: {cocktail['name']} → "
                    + ", ".join(item["title"] for item in found.values())
                )

        # 배치마다 저장해 중간 결과 보존
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

        with OUTPUT_PATH.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        print(
            f"이번 조사 진행: "
            f"{min(start + BATCH_SIZE, len(pending))}/{len(pending)}"
        )

        if start + BATCH_SIZE < len(pending):
            time.sleep(7)

    matched_names = {
        record["cocktail_name"] for record in records
    }

    korean_names = {
        record["cocktail_name"]
        for record in records
        if record["korean_title"]
    }

    print("\n--- 조사 결과 ---")
    print(f"전체 칵테일: {len(cocktails)}개")
    print(f"문서 후보 연결 항목: {len(matched_names)}개")
    print(f"그중 한국어 문서 연결 있음: {len(korean_names)}개")
    print(f"저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()