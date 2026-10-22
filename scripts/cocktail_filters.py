import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


ROOT_DIR = Path(__file__).resolve().parent.parent


def find_cocktails(
    question: str,
    cocktails: list[dict],
) -> dict:
    load_dotenv(ROOT_DIR / ".env")

    # 실제 데이터에 존재하는 재료명만 모델에 제공
    ingredient_names = sorted({
        ingredient["name"]
        for cocktail in cocktails
        for ingredient in cocktail["ingredients"]
    })

    alcoholic_values = sorted({
        cocktail["alcoholic"]
        for cocktail in cocktails
    })

    model = ChatOpenAI(
        model=os.environ["GMS_MODEL"],
        api_key=os.environ["GMS_KEY"],
        base_url=os.environ["GMS_BASE_URL"],
        timeout=120,
        max_retries=2,
    )

    response = model.invoke([
        {
            "role": "system",
            "content": """
너는 칵테일 검색 조건을 추출하는 담당자다.
사용자의 요청을 아래 JSON 형식으로 변환한다.

{
  "include_all": [],
  "exclude_any": [],
  "alcoholic": null,
  "needs_clarification": false,
  "message": ""
}

규칙:
- 설명이나 마크다운 없이 JSON 객체만 출력한다.
- include_all은 반드시 모두 포함해야 하는 재료 목록이다.
- exclude_any는 하나라도 포함하면 제외할 재료 목록이다.
- 재료명은 ingredient_names에 있는 정확한 문자열만 사용한다.
- alcoholic은 alcoholic_values에 있는 정확한 문자열 또는 null이다.
- 사용자가 말하지 않은 조건은 추가하지 않는다.
- '진'은 Gin, '보드카'는 Vodka처럼 실제 재료명에 대응시킨다.
- '크림 제외'처럼 여러 재료에 해당하는 표현은
  관련 재료명을 exclude_any에 모두 넣는다.
- 무알코올 요청은 Non alcoholic 값이 있을 때 사용한다.
- 선택 가능한 조건은 재료 포함, 재료 제외, 알코올 여부뿐이다.
- 맛, 도수, 가격, 알레르기 안전성 등 데이터로 검증할 수 없는
  조건이 있으면 needs_clarification을 true로 한다.
- 요청한 재료를 목록에서 찾지 못해도 조건을 무시하지 말고
  needs_clarification을 true로 한다.
- '진 또는 보드카'처럼 OR 조건은 현재 지원하지 않는다.
  이 경우 needs_clarification을 true로 한다.
- 조건이 전혀 없거나 의미가 모호해도
  needs_clarification을 true로 한다.
- needs_clarification이 true이면 message에
  무엇을 확인해야 하는지 한국어로 짧게 적는다.
- 정상적으로 조건을 추출했으면 message는 빈 문자열이다.
- 칵테일 이름이나 추천 결과는 생성하지 않는다.
""".strip(),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "request": question,
                    "ingredient_names": ingredient_names,
                    "alcoholic_values": alcoholic_values,
                },
                ensure_ascii=False,
            ),
        },
    ])

    if not isinstance(response.content, str):
        raise ValueError("모델 응답이 문자열이 아니야.")

    filters = json.loads(response.content)

    # 모델이 반환한 조건의 형식과 실제 값 검증
    if not isinstance(filters, dict):
        raise ValueError("검색 조건은 JSON 객체여야 해.")

    for key in ("include_all", "exclude_any"):
        values = filters[key]

        if (
            not isinstance(values, list)
            or not all(isinstance(value, str) for value in values)
        ):
            raise ValueError(f"{key}는 문자열 목록이어야 해.")

        unknown = set(values) - set(ingredient_names)

        if unknown:
            raise ValueError(
                f"데이터에 없는 재료명이 반환됐어: {sorted(unknown)}"
            )

        filters[key] = list(dict.fromkeys(values))

    alcoholic = filters["alcoholic"]

    if alcoholic is not None and alcoholic not in alcoholic_values:
        raise ValueError("알코올 여부 값이 올바르지 않아.")

    if type(filters["needs_clarification"]) is not bool:
        raise ValueError(
            "needs_clarification은 true 또는 false여야 해."
        )

    if not isinstance(filters["message"], str):
        raise ValueError("message는 문자열이어야 해.")

    conflict = (
        set(filters["include_all"])
        & set(filters["exclude_any"])
    )

    if conflict:
        filters["needs_clarification"] = True
        filters["message"] = (
            "같은 재료가 포함 조건과 제외 조건에 함께 있어. "
            "조건을 다시 알려줘."
        )

    if (
        not filters["include_all"]
        and not filters["exclude_any"]
        and alcoholic is None
    ):
        filters["needs_clarification"] = True

        if not filters["message"]:
            filters["message"] = (
                "포함하거나 제외할 재료, "
                "또는 알코올 여부를 알려줘."
            )

    if filters["needs_clarification"]:
        if not filters["message"].strip():
            filters["message"] = "검색 조건을 조금 더 구체적으로 알려줘."

        return {
            "filters": filters,
            "matches": [],
            "usage": response.usage_metadata or {},
        }

    include_all = set(filters["include_all"])
    exclude_any = set(filters["exclude_any"])

    matches = []

    # 추천 결과는 모델이 아닌 코드가 실제 데이터로 결정
    for cocktail in cocktails:
        ingredients = {
            ingredient["name"]
            for ingredient in cocktail["ingredients"]
        }

        if not include_all.issubset(ingredients):
            continue

        if exclude_any & ingredients:
            continue

        if (
            alcoholic is not None
            and cocktail["alcoholic"] != alcoholic
        ):
            continue

        matches.append(cocktail)

    matches.sort(key=lambda item: item["name"].casefold())

    return {
        "filters": filters,
        "matches": matches,
        "usage": response.usage_metadata or {},
    }


def main() -> None:
    with (ROOT_DIR / "data/service/cocktails.json").open(
        encoding="utf-8"
    ) as f:
        cocktails = json.load(f)

    question = "진이 들어가고 크림은 없는 칵테일 찾아줘."

    print(f"요청: {question}")
    print("\n검색 조건 분석 중...")

    result = find_cocktails(question, cocktails)
    filters = result["filters"]

    print("\n추출한 검색 조건:")
    print(json.dumps(filters, ensure_ascii=False, indent=2))

    if filters["needs_clarification"]:
        print(f"\n확인 필요: {filters['message']}")
    else:
        print(f"\n조건에 맞는 칵테일: {len(result['matches'])}개")

        for cocktail in result["matches"]:
            ingredients = ", ".join(
                ingredient["name"]
                for ingredient in cocktail["ingredients"]
            )

            print(f"\n- {cocktail['name']} [{cocktail['id']}]")
            print(f"  재료: {ingredients}")
            print(f"  알코올 여부: {cocktail['alcoholic']}")

        if not result["matches"]:
            print("현재 서비스 데이터에서 조건에 맞는 항목이 없어.")

    print("\n조건 추출 토큰 사용량:")
    print(result["usage"])


if __name__ == "__main__":
    main()