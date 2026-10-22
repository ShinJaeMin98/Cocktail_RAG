import json
from pathlib import Path

# scripts 폴더의 한 단계 위 = 프로젝트 최상위
ROOT_DIR = Path(__file__).resolve().parent.parent

# None은 빈 문자열로 바꾸고, 앞뒤 공백 제거
def clean(value):
    return str(value).strip() if value is not None else ""


with open(ROOT_DIR/"data/raw/cocktails_raw.json", "r", encoding="utf-8") as f:
    drinks = json.load(f)["drinks"]

cocktails = []
missing_measure_count = 0

for drink in drinks:
    ingredients = []

    for i in range(1, 16):
        name = clean(drink.get(f"strIngredient{i}"))
        measure = clean(drink.get(f"strMeasure{i}"))

        # 재료가 있는 경우에만 저장
        if name:
            ingredients.append({
                "name": name,
                "measure": measure
            })

            if not measure:
                missing_measure_count += 1

    cocktails.append({
        "id": clean(drink.get("idDrink")),
        "name": clean(drink.get("strDrink")),
        "category": clean(drink.get("strCategory")),
        "alcoholic": clean(drink.get("strAlcoholic")),
        "glass": clean(drink.get("strGlass")),
        "ingredients": ingredients,
        "instructions": clean(drink.get("strInstructions")),
        "image_url": clean(drink.get("strDrinkThumb")),
        "source": "TheCocktailDB",
        "source_url": (
            "https://www.thecocktaildb.com/drink/"
            f"{drink['idDrink']}"
        )
    })

with open(ROOT_DIR/"data/processed/cocktails.json", "w", encoding="utf-8") as f:
    json.dump(cocktails, f, ensure_ascii=False, indent=2)

print(f"저장 완료: {len(cocktails)}개")
print(f"분량이 비어 있는 재료: {missing_measure_count}개")

print("\n첫 번째 칵테일:")
print(json.dumps(cocktails[0], ensure_ascii=False, indent=2))