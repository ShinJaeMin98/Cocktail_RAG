import json
from pathlib import Path

# scripts 폴더의 한 단계 위 = 프로젝트 최상위
ROOT_DIR = Path(__file__).resolve().parent.parent

with open(ROOT_DIR/"data/processed/cocktails.json", "r", encoding="utf-8") as f:
    cocktails = json.load(f)

for cocktail in cocktails:
    ingredient_text = ", ".join(
        f"{item['name']} ({item['measure'] or '분량 미기재'})"
        for item in cocktail["ingredients"]
    )

    cocktail["search_text"] = "\n".join([
        f"칵테일 이름: {cocktail['name']}",
        f"분류: {cocktail['category']}",
        f"알코올 여부: {cocktail['alcoholic']}",
        f"잔 종류: {cocktail['glass']}",
        f"재료와 분량: {ingredient_text}",
        f"제조법: {cocktail['instructions']}"
    ])

with open(ROOT_DIR/"data/processed/cocktails_search.json", "w", encoding="utf-8") as f:
    json.dump(cocktails, f, ensure_ascii=False, indent=2)

print(f"검색용 텍스트 생성: {len(cocktails)}개")
print("\n첫 번째 검색용 텍스트:")
print(cocktails[0]["search_text"])