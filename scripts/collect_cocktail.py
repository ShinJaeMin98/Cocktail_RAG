import json
import string
import time
import requests
from pathlib import Path

# scripts 폴더의 한 단계 위 = 프로젝트 최상위
ROOT_DIR = Path(__file__).resolve().parent.parent

# ID를 기준으로 저장하면 중복을 제거할 수 있어
cocktails = {}
failed_letters = []

for letter in string.ascii_lowercase:
    url = (
        "https://www.thecocktaildb.com/api/json/v1/1/"
        f"search.php?f={letter}"
    )

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        drinks = response.json().get("drinks") or []

        for drink in drinks:
            cocktails[drink["idDrink"]] = drink

        print(f"{letter.upper()}: {len(drinks)}개 / 누적 {len(cocktails)}개")

    except (requests.RequestException, ValueError) as e:
        failed_letters.append(letter)
        print(f"{letter.upper()} 수집 실패: {e}")

    # 요청 사이에 간격 두기
    time.sleep(1)

# 기존 파일과 같은 {"drinks": [...]} 구조로 저장
result = {"drinks": list(cocktails.values())}

with open(ROOT_DIR/"data/raw/cocktails_raw.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\n최종 수집: {len(cocktails)}개")
print("저장 완료: cocktails_raw.json")
print(f"실패한 글자: {failed_letters}")

if len(cocktails) < 100:
    print("100개 미만이므로 추가 수집이 필요해.")