import hashlib
import html
import json
import os
import re
import threading
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

CACHE_DIR = ROOT_DIR / "data/cache/wikipedia"

# 검색 결과와 본문을 하루 동안 재사용
CACHE_TTL_SECONDS = 24 * 60 * 60

# 실제 HTTP 요청 사이의 최소 간격
REQUEST_INTERVAL_SECONDS = 7

CONTACT = os.getenv("WIKI_CONTACT", "").strip()

USER_AGENT = (
    f"CocktailLab/0.1 ({CONTACT}) python-requests"
    if CONTACT
    else "CocktailLab/0.1 python-requests"
)

# 같은 프로세스에서 발생하는 요청 간격 조절
_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST_TIME = 0.0


def check_user_agent() -> None:
    if not CONTACT:
        print(
            "[안내] .env에 WIKI_CONTACT를 "
            "설정하는 것을 권장해."
        )

    try:
        USER_AGENT.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError(
            "WIKI_CONTACT에는 영문 이메일 또는 URL을 넣어줘."
        )


def get_cache_path(language: str, params: dict) -> Path:
    payload = json.dumps(
        {
            "version": 1,
            "language": language,
            "params": params,
        },
        ensure_ascii=False,
        sort_keys=True,
    )

    key = hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()

    return CACHE_DIR / language / f"{key}.json"


def read_cache(path: Path):
    if not path.exists():
        return None

    try:
        with path.open(encoding="utf-8") as f:
            cached = json.load(f)

        saved_at = cached["saved_at"]

        if not isinstance(saved_at, (int, float)):
            return None

        age = time.time() - saved_at

        if not 0 <= age < CACHE_TTL_SECONDS:
            return None

        if not isinstance(cached["data"], dict):
            return None

        return cached["data"]

    except (OSError, ValueError, KeyError, TypeError):
        # 손상된 캐시는 실제 요청으로 다시 확보
        return None


def write_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    # 작성 중인 파일을 다른 요청에서 읽지 않도록 임시 저장 후 교체
    temporary = path.with_name(
        f"{path.name}.{threading.get_ident()}.tmp"
    )

    try:
        with temporary.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "saved_at": time.time(),
                    "data": data,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        temporary.replace(path)

    finally:
        if temporary.exists():
            temporary.unlink()


def send_request(
    api_url: str,
    params: dict,
) -> requests.Response:
    global _LAST_REQUEST_TIME

    with _REQUEST_LOCK:
        elapsed = time.monotonic() - _LAST_REQUEST_TIME
        remaining = REQUEST_INTERVAL_SECONDS - elapsed

        if remaining > 0:
            time.sleep(remaining)

        _LAST_REQUEST_TIME = time.monotonic()

        return requests.get(
            api_url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )


def request_wikipedia(
    params: dict,
    max_retries: int = 4,
    language: str = "ko",
) -> dict:
    if language not in ("ko", "en"):
        raise ValueError("지원 언어는 ko 또는 en이야.")

    if type(max_retries) is not int or max_retries < 1:
        raise ValueError("max_retries는 양의 정수여야 해.")

    check_user_agent()

    path = get_cache_path(language, params)
    cached = read_cache(path)

    label = (
        params.get("srsearch")
        or params.get("titles")
        or "API 요청"
    )

    if cached is not None:
        print(f"[캐시 사용/{language}] {label}")
        return cached

    api_url = f"https://{language}.wikipedia.org/w/api.php"

    for attempt in range(1, max_retries + 1):
        print(f"[API 요청/{language}] {label}")

        try:
            response = send_request(api_url, params)

        except (requests.Timeout, requests.ConnectionError):
            if attempt == max_retries:
                raise

            continue

        # 요청 제한 및 일시적인 서버 오류만 재시도
        if response.status_code in (429, 500, 502, 503, 504):
            if attempt == max_retries:
                response.raise_for_status()

            try:
                delay = float(
                    response.headers.get("Retry-After")
                    or min(2 ** attempt, 30)
                )
            except ValueError:
                delay = 7.0

            # 긴 대기를 요구하면 즉시 실패시키고 나중에 재실행
            if delay > 60:
                raise RuntimeError(
                    "위키백과에서 긴 대기를 요청했어. "
                    "잠시 후 다시 실행해줘."
                )

            time.sleep(max(delay, 1.0))
            continue

        response.raise_for_status()
        data = response.json()

        if not isinstance(data, dict):
            raise ValueError(
                "위키백과 응답이 JSON 객체가 아니야."
            )

        if "error" in data:
            raise RuntimeError(
                f"위키백과 API 오류: {data['error']}"
            )

        write_cache(path, data)
        return data

    raise RuntimeError("위키백과 요청에 실패했어.")


def search(
    query: str,
    limit: int = 3,
    language: str = "ko",
) -> list[dict]:
    """검색 결과도 캐시에 저장한다."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("검색어가 비어 있어.")

    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("검색 개수는 1~50이어야 해.")

    data = request_wikipedia(
        {
            "action": "query",
            "list": "search",
            "srsearch": query.strip(),
            "srlimit": limit,
            "format": "json",
            "formatversion": 2,
        },
        language=language,
    )

    results = []

    for item in data.get("query", {}).get("search", []):
        snippet = re.sub(
            r"<[^>]+>",
            "",
            item.get("snippet", ""),
        )

        results.append({
            "page_id": item["pageid"],
            "title": item["title"],
            "snippet": html.unescape(snippet),
            "language": language,
        })

    return results


def fetch_page(
    title: str,
    language: str = "ko",
) -> dict | None:
    """문서 본문과 원문 URL을 가져오고 캐시에 저장한다."""
    if not isinstance(title, str) or not title.strip():
        raise ValueError("문서 제목이 비어 있어.")

    data = request_wikipedia(
        {
            "action": "query",
            "prop": "extracts|info",
            "titles": title.strip(),
            "explaintext": 1,
            "inprop": "url",
            "redirects": 1,
            "format": "json",
            "formatversion": 2,
        },
        language=language,
    )

    pages = data.get("query", {}).get("pages", [])

    if not pages:
        return None

    page = pages[0]

    if "missing" in page or "invalid" in page:
        return None

    return {
        "page_id": page["pageid"],
        "title": page["title"],
        "url": page["fullurl"],
        "text": page.get("extract", ""),
        "language": language,
        "source": (
            "한국어 위키백과"
            if language == "ko"
            else "영어 위키백과"
        ),
    }


def main() -> None:
    print("첫 번째 검색:")
    first = search("모히토", limit=3)

    print("\n같은 검색 재실행:")
    second = search("모히토", limit=3)

    if first != second:
        raise ValueError("검색 결과와 캐시 결과가 달라.")

    for item in second:
        print(f"- {item['title']}")

    print("\n첫 번째 본문 조회:")
    first_page = fetch_page("모히토")

    print("\n같은 본문 재조회:")
    second_page = fetch_page("모히토")

    if first_page is None:
        raise ValueError("모히토 문서를 찾지 못했어.")

    if first_page != second_page:
        raise ValueError("본문과 캐시 결과가 달라.")

    print(f"\n제목: {second_page['title']}")
    print(f"본문 길이: {len(second_page['text'])}자")
    print(f"원문: {second_page['url']}")
    print("\n검색·본문 캐시 확인 완료")


if __name__ == "__main__":
    main()