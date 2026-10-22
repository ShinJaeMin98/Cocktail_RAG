import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

INPUT_PATH = ROOT_DIR / "data/processed/cocktails.json"
OUTPUT_PATH = ROOT_DIR / "data/processed/wiki_coverage.json"

API_URL = "https://en.wikipedia.org/w/api.php"
BATCH_SIZE = 20

contact = os.getenv("WIKI_CONTACT", "").strip()
user_agent = (
    f"CocktailLab/0.1 ({contact}) python-requests"
    if contact
    else "CocktailLab/0.1 python-requests"
)


def request_api(params):
    for attempt in range(4):
        response = requests.get(
            API_URL,
            params=params,
            headers={"User-Agent": user_agent},
            timeout=30,
        )

        if response.status_code == 429:
            if attempt == 3:
                response.raise_for_status()

            try:
                wait = float(response.headers.get("Retry-After", 10))
            except ValueError:
                wait = 10

            print(f"요청 제한: {wait}초 후 재시도")
            time.sleep(max(wait, 1))
            continue

        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise RuntimeError(str(data["error"]))

        return data

    raise RuntimeError("위키백과 요청 실패")


def main():
    with INPUT_PATH.open(encoding="utf-8") as f:
        cocktails = json.load(f)

    # 중간에 중단되더라도 완료한 항목은 다음 실행에서 재사용
    if OUTPUT_PATH.exists():
        with OUTPUT_PATH.open(encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = {}

    pending = [
        item for item in cocktails
        if item["id"] not in records
    ]

    print(f"전체 항목: {len(cocktails)}개")
    print(f"기존 조사 기록: {len(cocktails) - len(pending)}개")
    print(f"이번 조사 대상: {len(pending)}개")

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start:start + BATCH_SIZE]

        data = request_api({
            "action": "query",
            "titles": "|".join(item["name"] for item in batch),
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

        # 입력 이름 → 정규화된 제목 → 넘겨주기 도착 제목
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
            title = cocktail["name"]
            visited = set()

            while title in title_map and title not in visited:
                visited.add(title)
                title = title_map[title]

            page = pages.get(title)

            record = {
                "cocktail_id": cocktail["id"],
                "cocktail_name": cocktail["name"],
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "status": "not_found",
                "english_title": "",
                "english_url": "",
                "korean_title": "",
                "intro": "",
            }

            if page and "missing" not in page and "invalid" not in page:
                intro = page.get("extract", "").strip()
                is_disambiguation = (
                    "disambiguation" in page.get("pageprops", {})
                )

                korean_title = next(
                    (
                        link["title"]
                        for link in page.get("langlinks", [])
                        if link["lang"] == "ko"
                    ),
                    "",
                )

                # キーワード一致は候補の絞り込み。確定判定ではない。
                looks_like_drink = any(
                    word in intro.lower()
                    for word in ["cocktail", "drink", "beverage"]
                )

                if is_disambiguation:
                    status = "disambiguation"
                elif looks_like_drink:
                    status = "drink_candidate"
                else:
                    status = "needs_review"

                record.update({
                    "status": status,
                    "english_title": page["title"],
                    "english_url": page.get("fullurl", ""),
                    "korean_title": korean_title,
                    "intro": intro,
                })

            records[cocktail["id"]] = record

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

        with OUTPUT_PATH.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        print(
            f"今回の処理: "
            f"{min(start + BATCH_SIZE, len(pending))}/{len(pending)}"
        )

        if start + BATCH_SIZE < len(pending):
            time.sleep(7)

    current = [records[item["id"]] for item in cocktails]

    print("\n--- 調査結果 ---")
    print(f"조사 항목: {len(current)}개")

    labels = {
        "drink_candidate": "음료 관련 문서 후보",
        "needs_review": "내용 확인 필요",
        "disambiguation": "동음이의 문서",
        "not_found": "정확한 제목으로 찾지 못함",
    }

    for status, label in labels.items():
        count = sum(item["status"] == status for item in current)
        print(f"{label}: {count}개")

    korean_count = sum(
        item["status"] == "drink_candidate" and item["korean_title"]
        != ""
        for item in current
    )

    print(f"음료 후보 중 한국어 문서 연결 있음: {korean_count}개")
    print(f"\n저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()