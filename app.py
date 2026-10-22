import html
import json
import logging
import math
import sys
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from cocktail_filters import find_cocktails
from rag_service import build_graph, get_cited_sources

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="AFTER HOURS · 칵테일 라운지",
    page_icon="🍸",
    layout="wide",
    initial_sidebar_state="expanded",
)

STYLE = """
<style>
:root { --ink:#f4eee4; --muted:#a8b1bb; --gold:#d6b67a; --coral:#f0907d; --panel:#111d2a; }
.stApp { background:radial-gradient(ellipse at 86% 0%,#26324555,transparent 45%),#0a121d; color:var(--ink); }
.stApp, input, textarea, button { font-family: 'Pretendard','Noto Sans KR',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
[data-testid="stHeader"] { background:#0a121de8; }
[data-testid="stSidebar"] { background:#0c1723; border-right:1px solid #ffffff0d; }
[data-testid="stSidebar"] > div:first-child { padding-top:2rem; }
.block-container { max-width:1320px; padding:2.5rem 3rem 4rem; }
h1,h2,h3,h4 { color:var(--ink); }
[data-testid="stCaptionContainer"] { color:var(--muted); }
[data-testid="stMarkdownContainer"] a { color:var(--gold)!important; text-decoration-color:#d6b67a80; }
hr { border-color:#ffffff10!important; margin:1.8rem 0!important; }
[data-testid="stVerticalBlock"] { gap:1rem; }
[data-testid="stVerticalBlockBorderWrapper"] > div { border-color:#ffffff12!important; border-radius:18px!important; background:#111d2a80; }
.stButton > button,.stLinkButton > a,.stFormSubmitButton > button {
 border:1px solid #d6b67a55!important; border-radius:10px!important; background:#d6b67a0c; color:var(--ink)!important;
 min-height:42px; transition:background .18s,border-color .18s,transform .18s; }
.stButton > button:hover,.stLinkButton > a:hover,.stFormSubmitButton > button:hover {
 background:#d6b67a24!important; border-color:var(--gold)!important; transform:translateY(-1px); }
button[kind="primary"], [data-testid="stFormSubmitButton"] button { background:var(--gold)!important; color:#101822!important; border:0!important; font-weight:700; }
button[kind="primary"] *,[data-testid="stFormSubmitButton"] button * { color:#101822!important; }
[data-baseweb="input"],[data-baseweb="select"] > div,[data-baseweb="textarea"] { background:#0c1724!important; color:var(--ink)!important; border-color:#ffffff25!important; border-radius:10px!important; }
input,textarea { color:var(--ink)!important; caret-color:var(--gold); }
input::placeholder,textarea::placeholder { color:#8995a5!important; }
[data-baseweb="popover"],[data-baseweb="menu"], [role="listbox"] { background:#172333!important; color:var(--ink)!important; }
[data-baseweb="tag"] { background:#d6b67a26!important; color:var(--ink)!important; }
[data-testid="stForm"] { border:1px solid #ffffff15; background:#111d2a; border-radius:18px; padding:1.3rem; }
[data-testid="stExpander"] { border-color:#ffffff18!important; background:#0e1926; border-radius:12px!important; }
[data-testid="stExpander"] summary { color:var(--ink)!important; }
[data-testid="stChatMessage"] { background:#122131; border:1px solid #ffffff0d; border-radius:16px; padding:1.2rem; }
[data-testid="stChatMessage"] p,[data-testid="stChatMessage"] li { line-height:1.9; }
[data-testid="stChatInput"] { border:1px solid #d6b67a66!important; border-radius:14px!important; background:#132132!important; }
[data-testid="stBottom"], [data-testid="stBottomBlockContainer"] { background:transparent!important; }
[data-testid="stAlert"] { border-radius:12px; }
[data-testid="stRadio"] [role="radiogroup"] { gap:.5rem; flex-wrap:wrap; }
[data-testid="stRadio"] [role="radiogroup"] > label { background:#121f2e; border:1px solid #ffffff16; border-radius:10px; padding:.55rem 1.1rem; margin:0; }
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) { border-color:#d6b67a; background:#d6b67a1c; }
.brand { font-family:Georgia,serif; font-size:26px; letter-spacing:2px; color:var(--gold); }
.brand-sub { font-size:10px; letter-spacing:3px; color:var(--muted); margin-top:6px; }
.side-note { font-size:12px; line-height:1.9; color:var(--muted); }
.eyebrow { font-size:11px; letter-spacing:3px; color:var(--gold); font-weight:700; margin:0 0 12px; }
.hero { position:relative; overflow:hidden; padding:38px 42px; border:1px solid #d6b67a30; border-radius:24px; background:linear-gradient(120deg,#152438,#152332 55%,#253039); margin-bottom:22px; }
.hero:after { content:'✧'; position:absolute; right:40px; top:-60px; font-family:Georgia,serif; font-size:280px; color:#d6b67a10; pointer-events:none; }
.hero h1 { position:relative; z-index:1; font-family:Georgia,'Noto Sans KR',serif; font-size:clamp(35px,4.4vw,62px); font-weight:400; line-height:1.13; letter-spacing:-2px; margin:0 0 15px; padding:0; }
.hero h1 em { font-style:italic; color:var(--gold); }
.hero p { color:#bbc3cb; line-height:1.8; font-size:14px; margin:0; position:relative; z-index:1; }
.hero-foot { margin-top:25px; display:flex; gap:8px; flex-wrap:wrap; }
.pill { display:inline-block; font-size:11px; letter-spacing:.3px; border:1px solid #ffffff20; color:#d9dfdf; padding:6px 11px; border-radius:30px; }
.pill.gold { border-color:#d6b67a55; color:var(--gold); }
.section-head { margin:20px 0 8px; }
.section-head h2 { font-size:25px; font-weight:650; letter-spacing:-.8px; margin:0; padding:0; }
.section-head .eyebrow { font-size:10px; margin-bottom:8px; }
.photo-wrap { position:relative; background:linear-gradient(130deg,#263645,#19242e); border-radius:20px; overflow:hidden; min-height:270px; }
.feature-photo { width:100%; height:365px; object-fit:cover; display:block; }
.photo-wrap:after { content:''; position:absolute; inset:60% 0 0; background:linear-gradient(transparent,#08121bbf); pointer-events:none; }
.photo-tag { position:absolute; bottom:20px; left:20px; z-index:1; letter-spacing:3px; font-size:10px; color:#f4eee4; }
.drink-title { font-family:Georgia,serif; font-size:clamp(30px,4vw,49px); line-height:1.12; margin:10px 0 20px; letter-spacing:-1px; overflow-wrap:anywhere; }
.detail-label { color:var(--muted); font-size:11px; letter-spacing:1.5px; margin-top:18px; }
.detail-value { font-size:15px; margin-top:6px; color:var(--ink); }
.chips { display:flex; flex-wrap:wrap; gap:7px; margin:10px 0 15px; }
.chip { padding:6px 10px; border-radius:7px; background:#ffffff07; border:1px solid #ffffff12; color:#d0d8df; font-size:12px; }
.chip.missing { background:#f0907d12; border-color:#f0907d45; color:#f3ad9e; }
.result-img { width:100%; height:180px; object-fit:cover; border-radius:12px; display:block; margin-bottom:15px; }
.card-title { font-family:Georgia,serif; font-size:23px; margin:4px 0 8px; color:var(--ink); }
.card-meta { font-size:11px; color:var(--gold); letter-spacing:1px; }
.card-copy { font-size:12px; line-height:1.8; color:#adb8c5; min-height:44px; margin-bottom:12px; }
.chat-welcome { text-align:center; padding:25px 15px 30px; border:1px dashed #d6b67a35; border-radius:18px; margin:12px 0; }
.chat-welcome span { color:var(--gold); font-size:35px; }
.chat-welcome h3 { font-size:19px; font-weight:500; margin:4px 0 10px; padding:0; }
.chat-welcome p { color:var(--muted); font-size:13px; line-height:1.9; }
.ingredient-row { display:flex; justify-content:space-between; gap:18px; padding:10px 0; border-bottom:1px solid #ffffff0c; font-size:13px; }
.ingredient-row span:last-child { color:var(--gold); text-align:right; }
.footer { border-top:1px solid #ffffff10; padding-top:20px; margin-top:34px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px; color:#8793a3; font-size:10px; letter-spacing:1px; }

/* 배경과 글자색을 쌍으로 지정해 기본 밝은 테마와의 충돌을 방지한다. */
.stApp { color-scheme:dark; }
[data-testid="stMarkdownContainer"] { color:#e7edf3; }
[data-testid="stMarkdownContainer"] :is(p,li,td,th,blockquote) { color:inherit; }
[data-testid="stMarkdownContainer"] :is(strong,b) { color:#f5eee2; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color:#acb9c8!important; }
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p { color:#e7edf3!important; }
[data-testid="stMarkdownContainer"] blockquote { border-left:3px solid #d6b67a; background:#172536; padding:.7rem 1rem; }
[data-testid="stMarkdownContainer"] code { color:#f2cf91; background:#1b2b3d; border:1px solid #ffffff12; }
[data-testid="stMarkdownContainer"] pre { background:#101d2d!important; border:1px solid #ffffff18; }
[data-testid="stMarkdownContainer"] pre code { color:#e7edf3; border:0; }
[data-testid="stMarkdownContainer"] table { background:#101d2b; border-color:#334155; }
[data-testid="stMarkdownContainer"] th { background:#1b2b3d; }
[data-testid="stMarkdownContainer"] :is(th,td) { border-color:#334155!important; }
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
 background-color:#132235!important; color:#edf2f7!important; border:1px solid #43546a!important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] span,
[data-testid="stSelectbox"] [data-baseweb="select"] input,
[data-testid="stMultiSelect"] [data-baseweb="select"] input {
 color:#edf2f7!important; -webkit-text-fill-color:#edf2f7!important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] svg,
[data-testid="stMultiSelect"] [data-baseweb="select"] svg { color:#c5ced9!important; fill:currentColor; }
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stTextArea"] [data-baseweb="textarea"] {
 background-color:#132235!important; color:#edf2f7!important; border:1px solid #43546a!important;
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stChatInput"] textarea {
 background-color:transparent!important; color:#edf2f7!important; -webkit-text-fill-color:#edf2f7!important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div:focus-within,
[data-testid="stTextInput"] [data-baseweb="input"]:focus-within,
[data-testid="stTextArea"] [data-baseweb="textarea"]:focus-within {
 border-color:#d6b67a!important; box-shadow:0 0 0 2px #d6b67a22!important;
}
input::placeholder, textarea::placeholder { color:#a9b7c8!important; -webkit-text-fill-color:#a9b7c8!important; opacity:1; }
/* 드롭다운은 본문 밖의 포털에 표시되므로 별도로 스타일을 적용한다. */
[data-baseweb="popover"] [role="listbox"],
[data-baseweb="popover"] [data-baseweb="menu"],
[data-baseweb="popover"] ul { background:#172638!important; color:#edf2f7!important; border-color:#43546a!important; }
[data-baseweb="popover"] [role="option"],
[data-baseweb="popover"] [role="option"] *,
[data-baseweb="popover"] li,
[data-baseweb="popover"] li *,
[data-baseweb="popover"] [data-testid="stMarkdownContainer"] {
 color:#edf2f7!important; -webkit-text-fill-color:#edf2f7!important;
}
[data-baseweb="popover"] [role="option"], [data-baseweb="popover"] li { background:#172638!important; }
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="popover"] [role="option"][aria-selected="true"],
[data-baseweb="popover"] li:hover { background:#2b4057!important; }
[data-baseweb="tag"], [data-baseweb="tag"] * { color:#f3deb6!important; -webkit-text-fill-color:#f3deb6!important; }
[data-testid="stExpander"] details,
[data-testid="stExpander"] details > div { background:#101d2b!important; }
[data-testid="stExpander"] summary {
 background:#18283a!important; color:#e7edf3!important; border-radius:10px; min-height:44px;
}
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span { color:#e7edf3!important; }
[data-testid="stExpander"] summary:hover { background:#21354a!important; }
[data-testid="stExpander"] summary svg { color:#d6b67a!important; }
[data-testid="stBottom"], [data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] { background:#0a121d!important; }
[data-testid="stChatInput"], [data-testid="stChatInput"] > div {
 background:#132235!important; color:#edf2f7!important; border-radius:14px;
}
[data-testid="stChatInput"] { border:1px solid #8e7853!important; }
[data-testid="stChatInput"]:focus-within { border-color:#d6b67a!important; box-shadow:0 0 0 2px #d6b67a22; }
[data-testid="stChatInputSubmitButton"] { color:#efcf94!important; background:#26394e!important; border-radius:9px; }
[data-testid="stChatInputSubmitButton"] svg { fill:currentColor; }
[data-testid="stChatInputSubmitButton"]:disabled { color:#8595aa!important; background:#1d2d40!important; opacity:.8; }
[data-testid="stChatMessageContent"] { color:#e7edf3; }
[data-testid="stChatMessageContent"] a { color:#efcf94!important; }
[data-testid="stAlert"] { background:#172638!important; color:#e7edf3!important; border:1px solid #43546a; }
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] { color:#e7edf3!important; }
[data-testid="stRadio"] label p { color:#d4dfeb!important; }
[data-testid="stRadio"] label:has(input:checked) p { color:#f3deb6!important; }
.stButton > button:focus-visible,.stLinkButton > a:focus-visible { outline:2px solid #d6b67a; outline-offset:3px; }

@media(max-width:760px) { .block-container { padding:1.3rem 1rem 2rem; } .hero { padding:28px 24px; } .hero:after { right:-40px; } .feature-photo { height:290px; } .drink-title { font-size:35px; } }
@media(prefers-reduced-motion:reduce) { * { transition:none!important; } }
</style>
"""


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def image_markup(cocktail: dict, feature: bool = False) -> str:
    url = cocktail.get("image_url", "")
    if urlparse(url).scheme not in ("https", "http"):
        return '<div class="chat-welcome">🍸</div>'
    css_class = "feature-photo" if feature else "result-img"
    return f'<img class="{css_class}" src="{esc(url)}" alt="{esc(cocktail["name"])}" loading="lazy" referrerpolicy="no-referrer">'


def section_title(kicker: str, title: str) -> None:
    st.markdown(f'<div class="section-head"><div class="eyebrow">{esc(kicker)}</div><h2>{esc(title)}</h2></div>', unsafe_allow_html=True)


def chips(values, missing: bool = False) -> None:
    css_class = "chip missing" if missing else "chip"
    st.markdown('<div class="chips">' + ''.join(f'<span class="{css_class}">{esc(value)}</span>' for value in values) + '</div>', unsafe_allow_html=True)


@st.cache_data
def load_cocktails() -> list[dict]:
    with (ROOT_DIR / "data/service/cocktails_all.json").open(encoding="utf-8") as f:
        return json.load(f)


@st.cache_resource
def load_graph():
    return build_graph()


def select_cocktail(cocktail_id: str) -> None:
    st.session_state.selected_cocktail_id = cocktail_id
    st.session_state.active_view = "칵테일 라운지"


def change_cocktail() -> None:
    st.session_state.selected_cocktail_id = st.session_state._cocktail_picker


def change_view(view: str) -> None:
    # 버튼은 이전 선택값을 다음 요청에 다시 보내지 않는다.
    st.session_state.active_view = view


def render_sources(sources: list[dict]) -> None:
    if not sources:
        st.caption("이번 답변에 인용된 근거는 없어.")
        return
    with st.expander(f"인용한 출처 · {len(sources)}개"):
        for source in sources:
            numbers = "".join(f"[{number}]" for number in source["numbers"])
            label = "레시피" if source["source_type"] == "cocktail_metadata" else "설명 문서"
            st.markdown(f"**{numbers} {source['title']}** · {label}")
            st.link_button("원문에서 확인 ↗", source["url"])


def recipe(cocktail: dict) -> None:
    rows = ''.join('<div class="ingredient-row"><span>' + esc(i["name"]) + '</span><span>' + esc(i.get("measure") or "분량 미기재") + '</span></div>' for i in cocktail["ingredients"])
    st.markdown(rows, unsafe_allow_html=True)
    st.markdown("\n**제조법**")
    st.write(cocktail["instructions"])
    st.link_button("TheCocktailDB 원문 ↗", cocktail["source_url"])


def render_cocktail_info(cocktail: dict) -> None:
    left, right = st.columns([1, 1.25], gap="large")
    with left:
        st.markdown('<div class="photo-wrap">' + image_markup(cocktail, True) + '<span class="photo-tag">THE SELECTED POUR</span></div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="eyebrow">YOUR SELECTION</div><div class="drink-title">' + esc(cocktail["name"]) + '</div>', unsafe_allow_html=True)
        alcohol = {"Alcoholic":"알코올", "Non alcoholic":"무알코올", "Optional alcohol":"알코올 선택"}.get(cocktail["alcoholic"], cocktail["alcoholic"])
        coverage = "설명 문서 검토 완료" if cocktail.get("has_reviewed_document") else "기본 레시피 · 추가 자료 검색"
        chips([alcohol, cocktail["category"], coverage])
        st.markdown('<div class="detail-label">SERVE IN</div><div class="detail-value">' + esc(cocktail["glass"]) + '</div><div class="detail-label">INGREDIENTS · ' + str(len(cocktail["ingredients"])) + '</div>', unsafe_allow_html=True)
        chips([i["name"] for i in cocktail["ingredients"]])
        with st.expander("재료의 분량과 제조법"):
            recipe(cocktail)


def result_card(cocktail: dict, prefix: str) -> None:
    st.markdown(image_markup(cocktail) + '<div class="card-meta">' + esc(cocktail["glass"]) + '</div><div class="card-title">' + esc(cocktail["name"]) + '</div><div class="card-copy">' + esc(' · '.join(i["name"] for i in cocktail["ingredients"])) + '</div>', unsafe_allow_html=True)
    st.button("이 칵테일과 대화하기 ↗", key=f"{prefix}_{cocktail['id']}", on_click=select_cocktail, args=(str(cocktail["id"]),), use_container_width=True)


def render_search(cocktails: list[dict]) -> None:
    section_title("FIND YOUR POUR", "취향의 조건을 말해줘.")
    st.caption("포함할 재료, 피하고 싶은 재료, 알코올 여부로 한 잔을 찾아봐.")
    with st.form("cocktail_search_form"):
        request = st.text_input("원하는 조건", placeholder="진이 들어가고 크림은 없는 칵테일 찾아줘.", label_visibility="collapsed")
        submitted = st.form_submit_button("나에게 맞는 칵테일 찾기 →", use_container_width=True)
    if submitted:
        if not request.strip():
            st.warning("원하는 조건을 먼저 입력해줘.")
        else:
            st.session_state.pop("filter_result", None)
            try:
                with st.spinner("조건에 맞는 한 잔을 찾고 있어..."):
                    st.session_state.filter_result = find_cocktails(request.strip(), cocktails)
                st.session_state.search_page = 1
            except Exception as error:
                logger.error("조건 검색 실패: %s", type(error).__name__)
                st.error("조건을 분석하지 못했어. 잠시 뒤 다시 검색해줘.")
    result = st.session_state.get("filter_result")
    if result is None:
        st.markdown('<div class="chat-welcome"><span>⌕</span><h3>새로운 한 잔을 발견하는 방법</h3><p>“보드카가 들어간 칵테일”<br>“럼은 들어가고 우유는 없는 칵테일”</p></div>', unsafe_allow_html=True)
        return
    filters = result["filters"]
    if filters["needs_clarification"]:
        st.info(filters["message"])
        return
    conditions = []
    if filters["include_all"]:
        conditions.append("모두 포함 · " + ", ".join(filters["include_all"]))
    if filters["exclude_any"]:
        conditions.append("제외 · " + ", ".join(filters["exclude_any"]))
    if filters["alcoholic"]:
        conditions.append(filters["alcoholic"])
    chips(conditions)
    matches = result["matches"]
    st.markdown(f"**{len(matches)}잔**을 찾았어.")
    if not matches:
        st.info("현재 데이터에 맞는 항목이 없어. 조건을 조금 바꿔봐.")
        return
    pages = math.ceil(len(matches) / 9)
    page = min(int(st.session_state.get("search_page", 1)), pages)
    st.session_state.search_page = page
    if pages > 1:
        page = st.selectbox("결과 페이지", list(range(1, pages + 1)), key="search_page", format_func=lambda value: f"{value} / {pages}")
    shown = matches[(page-1)*9:page*9]
    for start in range(0, len(shown), 3):
        columns = st.columns(3, gap="medium")
        for column, cocktail in zip(columns, shown[start:start+3]):
            with column:
                with st.container(border=True):
                    result_card(cocktail, "search_open")


def render_pantry(cocktails: list[dict]) -> None:
    section_title("YOUR HOME BAR", "지금 가진 재료로, 한 잔.")
    st.caption("재료 이름을 기준으로 비교해. 보유량과 대체 가능 여부는 별도로 확인해줘.")
    labels = {}
    for cocktail in cocktails:
        for ingredient in cocktail["ingredients"]:
            name = ingredient["name"].strip()
            labels.setdefault(name.casefold(), name)
    with st.container(border=True):
        owned = st.multiselect("우리 집 바에 있는 재료", sorted(labels), format_func=lambda key: labels[key], key="pantry_ingredients", placeholder="Gin, Campari, Sweet Vermouth...")
        max_missing = st.selectbox("부족해도 괜찮은 재료 수", [0, 1, 2], format_func=lambda count: "재료를 모두 가진 칵테일만" if count == 0 else f"{count}개까지 부족해도 괜찮아", key="pantry_max_missing")
    if not owned:
        st.markdown('<div class="chat-welcome"><span>◇</span><h3>집에 있는 재료부터 골라봐.</h3><p>만들 수 있는 칵테일과<br>완성까지 필요한 재료를 함께 알려줄게.</p></div>', unsafe_allow_html=True)
        return
    owned_set = set(owned)
    results = []
    for cocktail in cocktails:
        required = {i["name"].strip().casefold() for i in cocktail["ingredients"]}
        available = required & owned_set
        missing = required - owned_set
        if available and len(missing) <= max_missing:
            results.append((cocktail, available, missing))
    results.sort(key=lambda item: (len(item[2]), -len(item[1]), item[0]["name"].casefold()))
    st.markdown(f"**{len(results)}잔**의 가능성이 있어.")
    if not results:
        st.info("조건에 맞는 항목이 없어. 재료를 추가하거나 부족한 재료 수를 바꿔봐.")
        return
    # 보유 재료를 변경하면 첫 페이지부터 표시
    signature = (tuple(sorted(owned)), max_missing)
    if st.session_state.get("pantry_signature") != signature:
        st.session_state.pantry_signature = signature
        st.session_state.pantry_page = 1
    pages = math.ceil(len(results)/6)
    page = 1
    if pages > 1:
        page = st.selectbox("결과 페이지", list(range(1,pages+1)), key="pantry_page", format_func=lambda value: f"{value} / {pages}")
    shown = results[(page-1)*6:page*6]
    for start in range(0, len(shown), 2):
        columns = st.columns(2, gap="medium")
        for column, (cocktail, available, missing) in zip(columns, shown[start:start+2]):
            with column:
                with st.container(border=True):
                    st.markdown(image_markup(cocktail) + '<div class="card-title">' + esc(cocktail["name"]) + '</div>', unsafe_allow_html=True)
                    st.caption("가지고 있어")
                    chips([labels[key] for key in sorted(available)])
                    if missing:
                        st.caption(f"완성까지 {len(missing)}개")
                        chips([labels[key] for key in sorted(missing)], missing=True)
                    else:
                        st.success("기재된 재료를 모두 가지고 있어.")
                    with st.expander("레시피와 판단 근거"):
                        recipe(cocktail)
                    st.button("이 칵테일과 대화하기 ↗", key=f"pantry_open_{cocktail['id']}", on_click=select_cocktail, args=(str(cocktail["id"]),), use_container_width=True)

def render_chat(selected_id: str, cocktail: dict) -> None:
    section_title("ASK THE BARTENDER", "한 잔에 담긴 이야기를 물어봐.")
    st.caption("재료부터 유래까지, 확인한 자료를 바탕으로 답해줄게.")

    history = st.session_state.chat_histories.setdefault(
        selected_id,
        [],
    )

    if not history:
        st.markdown('<div class="chat-welcome"><span>✧</span><h3>어떤 이야기가 궁금해?</h3><p>“어디에서 유래했어?” · “재료와 분량을 알려줘.”<br>이름을 생략해도 지금 선택한 칵테일로 이야기할게.</p></div>', unsafe_allow_html=True)

    for message in history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message["role"] == "assistant":
                if message.get("warning"):
                    st.warning(message["warning"])

                render_sources(message.get("sources", []))

    question = st.chat_input(
        f"{cocktail['name']}에 대해 질문해줘",
        key="lounge_question",
    )

    if not question or not question.strip():
        return

    question = question.strip()

    with st.chat_message("user"):
        st.markdown(question)

    previous_history = [
        {
            "role": message["role"],
            "content": message["content"],
        }
        for message in history[-6:]
    ]

    with st.chat_message("assistant"):
        try:
            with st.status(
                "자료를 확인하고 있어...",
                expanded=True,
            ) as status:
                st.write(
                    "질문에 필요한 자료를 확인하고 있어."
                )

                graph = load_graph()
                result = {}

                for update in graph.stream(
                    {
                        "cocktail_id": selected_id,
                        "question": question,
                        "history": previous_history,
                    },
                    stream_mode="updates",
                ):
                    if "collect" in update:
                        collected = update["collect"]
                        result.update(collected)
                        info = collected["collection_info"]

                        if info["success"]:
                            st.write(
                                f"관련 자료 {info['document_count']}개를 확인했어."
                            )
                        else:
                            st.write(info["warning"])

                        st.write(
                            "선택한 칵테일의 자료에서 근거를 검색하고 있어."
                        )

                    if "retrieve" in update:
                        retrieved = update["retrieve"]
                        result.update(retrieved)

                        st.write(
                            f"근거 {len(retrieved['evidence'])}개를 "
                            "확보했어. 답변을 생성하고 있어."
                        )

                    if "generate" in update:
                        result.update(update["generate"])

                if "answer" not in result:
                    raise ValueError("답변 생성 결과가 없어.")

                sources = get_cited_sources(
                    result["answer"],
                    result["evidence"],
                )

                warning = result.get(
                    "collection_info", {}
                ).get("warning", "")

                status.update(
                    label=(
                        "기존 자료로 답변 생성 완료"
                        if warning
                        else "답변 생성 완료"
                    ),
                    state="complete",
                    expanded=False,
                )

        except Exception as error:
            logger.error(
                "답변 생성 실패: %s",
                type(error).__name__,
            )
            st.error(
                "답변을 생성하지 못했어. "
                "연결 상태를 확인한 뒤 다시 질문해줘."
            )
            return

        st.markdown(result["answer"])

        if warning:
            st.warning(warning)

        render_sources(sources)

        history.extend([
            {
                "role": "user",
                "content": question,
            },
            {
                "role": "assistant",
                "content": result["answer"],
                "sources": sources,
                "warning": warning,
            },
        ])
        # 저장한 기록을 기준으로 화면을 다시 구성한다.
        st.rerun()


def main() -> None:
    st.markdown(STYLE, unsafe_allow_html=True)
    try:
        cocktails = load_cocktails()
    except Exception:
        st.error("칵테일 데이터를 불러오지 못했어. data/service/cocktails_all.json을 확인해줘.")
        st.stop()
    if not cocktails:
        st.error("선택할 칵테일 데이터가 없어.")
        st.stop()
    by_id = {str(item["id"]): item for item in cocktails}
    cocktail_ids = sorted(by_id, key=lambda key: by_id[key]["name"].casefold())
    if "chat_histories" not in st.session_state:
        st.session_state.chat_histories = {}
    if st.session_state.get("selected_cocktail_id") not in by_id:
        st.session_state.selected_cocktail_id = "11000" if "11000" in by_id else cocktail_ids[0]
    if "active_view" not in st.session_state:
        st.session_state.active_view = "칵테일 라운지"
    # 화면/선택의 실제 상태는 위젯 키와 분리해 보관한다.
    # 위젯 재생성이나 화면 전환으로 실제 선택이 초기화되지 않도록 한다.
    st.session_state._cocktail_picker = st.session_state.selected_cocktail_id
    with st.sidebar:
        st.markdown('<div class="brand">AFTER HOURS<span style="color:#f0907d">.</span></div><div class="brand-sub">A COCKTAIL KNOWLEDGE LOUNGE</div>', unsafe_allow_html=True)
        st.divider()
        st.caption("오늘의 한 잔")
        st.selectbox("칵테일 선택", cocktail_ids, format_func=lambda key: by_id[key]["name"], key="_cocktail_picker", on_change=change_cocktail)
        selected_id = st.session_state.selected_cocktail_id
        cocktail = by_id[selected_id]
        st.markdown(image_markup(cocktail), unsafe_allow_html=True)
        st.markdown('<div class="card-title">' + esc(cocktail["name"]) + '</div>', unsafe_allow_html=True)
        st.caption(cocktail["glass"])
        st.divider()
        count = len(st.session_state.chat_histories.get(selected_id, [])) // 2
        st.caption(f"이 칵테일과 나눈 대화 · {count}회")
        if st.button("현재 대화 비우기", use_container_width=True):
            st.session_state.chat_histories[selected_id] = []
            st.rerun()
        st.markdown('<div class="side-note">칵테일마다 이야기는 따로 보관돼.<br>다른 한 잔을 고르고 돌아와도<br>이 세션의 대화를 이어갈 수 있어.</div>', unsafe_allow_html=True)
    st.markdown('<section class="hero"><div class="eyebrow">A LITTLE CURIOSITY. A BETTER COCKTAIL.</div><h1>한 잔의 취향,<br><em>그 이상의 이야기.</em></h1><p>취향에 맞는 칵테일을 발견하고,<br>재료와 레시피, 그 뒤에 담긴 이야기를 만나봐.</p><div class="hero-foot"><span class="pill gold">' + str(len(cocktails)) + ' COCKTAILS</span><span class="pill">레시피와 연결된 이야기</span><span class="pill">원문으로 확인하는 답변</span></div></section>', unsafe_allow_html=True)
    # 화면 전환은 버튼 이벤트로만 처리한다.
    # 채팅 제출 시 브라우저가 보낸 이전 라디오 값으로 돌아가는 것을 방지한다.
    views = ["칵테일 라운지", "조건으로 찾기", "내 재료로 만들기"]
    navigation = st.columns(3)
    for column, name in zip(navigation, views):
        with column:
            st.button(
                name,
                key=f"navigate_{name}",
                type="primary" if st.session_state.active_view == name else "secondary",
                on_click=change_view,
                args=(name,),
                use_container_width=True,
            )
    view = st.session_state.active_view
    if view == "칵테일 라운지":
        st.write("")
        render_cocktail_info(by_id[selected_id])
        st.divider()
        render_chat(selected_id, by_id[selected_id])
    elif view == "조건으로 찾기":
        render_search(cocktails)
    else:
        render_pantry(cocktails)
    st.markdown('<div class="footer"><span>AFTER HOURS · 한 잔의 호기심을 위한 공간</span><span>TheCocktailDB + Wikipedia</span></div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
