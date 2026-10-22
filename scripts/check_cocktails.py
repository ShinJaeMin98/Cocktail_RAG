import json
from pathlib import Path

# scripts 폴더의 한 단계 위 = 프로젝트 최상위
ROOT_DIR = Path(__file__).resolve().parent.parent

with open(ROOT_DIR/"data/raw/cocktails_raw.json", "r", encoding="utf-8") as f:
    drinks = json.load(f)["drinks"]

# 빈 문자열이나 공백도 누락으로 판단
def is_empty(value):
    return value is None or str(value).strip() == ""

missing_name = []
missing_ingredients = []
missing_instructions = []

for drink in drinks:
    name = drink.get("strDrink") or drink.get("idDrink")

    if is_empty(drink.get("strDrink")):
        missing_name.append(name)

    if all(
        is_empty(drink.get(f"strIngredient{i}"))
        for i in range(1, 16)
    ):
        missing_ingredients.append(name)

    if is_empty(drink.get("strInstructions")):
        missing_instructions.append(name)

ids = [drink.get("idDrink") for drink in drinks]

print(f"전체 항목: {len(drinks)}개")
print(f"ID 누락: {sum(is_empty(x) for x in ids)}개")
print(f"ID 중복: {len(ids) - len(set(ids))}개")
print(f"이름 누락: {len(missing_name)}개")
print(f"재료 전체 누락: {len(missing_ingredients)}개")
print(f"제조법 누락: {len(missing_instructions)}개")

print("\n제조법 누락 항목:", missing_instructions)
print("재료 전체 누락 항목:", missing_ingredients)