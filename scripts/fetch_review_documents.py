import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from audit_wiki_coverage import request_api

ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT_DIR / "data/processed/wiki_candidates_merged.json"
OUTPUT_DIR = ROOT_DIR / "data/wiki_review"

REQUEST_INTERVAL = 7


def main():
    with INPUT_PATH.open(encoding="utf-8") as f:
        items = json.load(f)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    titles = sorted({
        candidate["title"]
        for item in items
        for candidate in item["candidates"]
    })

    # 기존 파일에서 정상적으로 수집된 제목 확인
    saved_titles = set()

    for path in OUTPUT_DIR.glob("*.json"):
        with path.open(encoding="utf-8") as f:
            document = json.load(f)

        text = document.get("text", "")

        if isinstance(text, str) and text.strip():
            title = document.get("requested_title")

            if title:
                saved_titles.add(title)

    pending = [
        title for title in titles
        if title not in saved_titles
    ]

    failed = []

    print(f"전체 고유 문서 후보: {len(titles)}개")
    print(f"기존 수집 완료: {len(set(titles) & saved_titles)}개")
    print(f"이번 수집 대상: {len(pending)}개")

    for index, requested_title in enumerate(pending, start=1):
        if index > 1:
            time.sleep(REQUEST_INTERVAL)

        print(f"\n[{index}/{len(pending)}] {requested_title}")

        try:
            # 전체 본문을 문서 하나씩 요청
            data = request_api({
                "action": "query",
                "titles": requested_title,
                "redirects": 1,
                "prop": "extracts|info",
                "explaintext": 1,
                "exlimit": 1,
                "inprop": "url",
                "format": "json",
                "formatversion": 2,
            })

            pages = data.get("query", {}).get("pages", [])

            if not pages:
                raise ValueError("문서 응답 없음")

            page = pages[0]

            if "missing" in page or "invalid" in page:
                raise ValueError("존재하지 않거나 잘못된 문서 제목")

            text = page.get("extract", "").strip()

            if not text:
                raise ValueError("본문이 비어 있음")

            related = [
                {
                    "cocktail_id": item["cocktail_id"],
                    "cocktail_name": item["cocktail_name"],
                }
                for item in items
                if any(
                    candidate["title"] == requested_title
                    for candidate in item["candidates"]
                )
            ]

            document = {
                "page_id": page["pageid"],
                "requested_title": requested_title,
                "title": page["title"],
                "url": page["fullurl"],
                "text": text,
                "source": "영어 위키백과",
                "language": "en",
                "related_cocktails": related,
                "review_status": "pending",
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }

            # 제목 기준으로 일정한 파일명 생성
            title_hash = hashlib.sha256(
                requested_title.encode("utf-8")
            ).hexdigest()[:16]

            path = OUTPUT_DIR / f"en_doc_{title_hash}.json"

            with path.open("w", encoding="utf-8") as f:
                json.dump(document, f, ensure_ascii=False, indent=2)

            saved_titles.add(requested_title)

            print(f"  저장 성공: {len(text):,}자")

        except Exception as e:
            failed.append({
                "title": requested_title,
                "error": str(e),
            })

            print(f"  실패: {e}")

    completed_count = len(set(titles) & saved_titles)

    print("\n--- 수집 결과 ---")
    print(f"전체 고유 문서 후보: {len(titles)}개")
    print(f"본문 확보: {completed_count}개")
    print(f"미확보: {len(titles) - completed_count}개")

    if failed:
        print("\n이번 실행 실패 문서:")
        for item in failed:
            print(f"- {item['title']}: {item['error']}")

    print(f"\n저장 위치: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()