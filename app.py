from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="Olist 이커머스 성과 대시보드", page_icon="🛒", layout="wide")

# =====================================================================
# 0. 디자인(색, CSS)
# =====================================================================
BLUE, ORANGE, GREEN, RED, GRAY = "#0072B2", "#D55E00", "#009E73", "#C0392B", "#6B7280"
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.6rem; max-width: 1400px;}
    footer {visibility: hidden;}
    div[data-testid="stMetric"] {
        background: #F5F8FB; border: 1px solid #DCE6F0; border-radius: 12px; padding: 12px 16px;}
    div[data-testid="stMetricLabel"] p {color: #4B5563; font-size: 0.85rem;}
    div[data-testid="stMetricValue"] {font-size: 1.55rem;}
    .insight {background: #EEF6FF; border-left: 5px solid #0072B2; border-radius: 6px;
        padding: 12px 18px; margin: 8px 0 14px 0; color: #1F2937; line-height: 1.7;}
    .insight ul {margin: 4px 0 0 0; padding-left: 20px;}
    .note {color: #6B7280; font-size: 0.85rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

HERE = Path(__file__).parent   # app.py가 있는 폴더

PAY_KO = {"credit_card": "신용카드", "boleto": "보레토(은행 청구서)", "voucher": "바우처",
          "debit_card": "체크카드", "not_defined": "미정"}
STATE_XY = {  # 주(State) 대략적 중심 좌표(경도, 위도): 지도 이미지 없이 버블 위치만 표시합니다
    "AC": (-70.8, -9.0), "AL": (-36.8, -9.6), "AM": (-65.1, -3.5), "AP": (-51.8, 1.4), "BA": (-41.7, -13.0),
    "CE": (-39.5, -5.2), "DF": (-47.9, -15.8), "ES": (-40.3, -19.2), "GO": (-49.9, -16.0), "MA": (-45.4, -5.4),
    "MG": (-44.4, -18.1), "MS": (-54.5, -20.5), "MT": (-55.4, -12.6), "PA": (-52.5, -3.8), "PB": (-36.7, -7.3),
    "PE": (-37.9, -8.4), "PI": (-42.3, -6.6), "PR": (-51.6, -24.9), "RJ": (-42.7, -22.3), "RN": (-36.6, -5.8),
    "RO": (-63.3, -10.8), "RR": (-61.3, 2.0), "RS": (-53.5, -30.2), "SC": (-50.2, -27.5), "SE": (-37.5, -10.6),
    "SP": (-48.8, -22.2), "TO": (-48.3, -9.5),
}


@st.cache_data
def load_data():
    return pd.read_csv(HERE / "olist_orders.csv", parse_dates=["purchase_date"])


data = load_data()
months_all = pd.period_range("2016-09", "2018-09", freq="M").astype(str).tolist()
months_main = [m for m in months_all if "2017-01" <= m <= "2018-08"]   # 주문이 충분한 기간

# =====================================================================
# 1. 사이드바(필터)
# =====================================================================
st.sidebar.header("🔎 조회 조건")
period = st.sidebar.select_slider("기간(월)", options=months_main, value=(months_main[-6], months_main[-1]))
statuses = st.sidebar.multiselect("주문 상태", data["order_status"].value_counts().index.tolist(),
                                  default=["delivered"])
categories = st.sidebar.multiselect("상품 카테고리 (비우면 전체)",
                                    data.groupby("category")["price"].sum().sort_values(ascending=False).index.tolist())
states = st.sidebar.multiselect("지역·주(State) (비우면 전체)", sorted(data["customer_state"].dropna().unique()))
pay_types = st.sidebar.multiselect("결제 수단 (비우면 전체)", sorted(data["payment_type"].unique()),
                                   format_func=lambda k: PAY_KO.get(k, k))
metric_label = st.sidebar.selectbox("차트 표시 지표", ["매출", "주문 수"])
compare = st.sidebar.checkbox("직전 동일 기간과 비교", value=True)
st.sidebar.caption("기본값은 최근 6개월 · 배송 완료 주문입니다. 기간을 바꾸면 비교 기간도 같이 바뀝니다.")


def apply_filters(frame, m_from, m_to):
    mask = frame["order_status"].isin(statuses) & frame["month"].between(m_from, m_to)
    if categories:
        mask &= frame["category"].isin(categories)
    if states:
        mask &= frame["customer_state"].isin(states)
    if pay_types:
        mask &= frame["payment_type"].isin(pay_types)
    return frame.loc[mask].copy()


# 현재 기간과, 길이가 같은 직전 기간
view = apply_filters(data, period[0], period[1])
if view.empty:
    st.warning("표시할 데이터가 없습니다. 조건을 넓히거나 주문 상태를 하나 이상 선택하세요.")
    st.stop()

prev_view, prev_range = None, None
i0, i1 = months_all.index(period[0]), months_all.index(period[1])
n_months = i1 - i0 + 1
if compare and i0 - n_months >= 0:
    prev_range = (months_all[i0 - n_months], months_all[i0 - 1])
    prev_view = apply_filters(data, *prev_range)
    if prev_view["order_id"].nunique() == 0:
        prev_view = None

# =====================================================================
# 2. 지표 계산
# =====================================================================
metric = {"매출": "sales", "주문 수": "orders"}[metric_label]
unit = "R$" if metric == "sales" else "건"


def style(fig, height=380):
    """모든 차트에 같은 모양(흰 배경, 여백, 글자)을 입힙니다."""
    fig.update_layout(template="plotly_white", height=height, title_font_size=16,
                      margin=dict(l=10, r=60, t=50, b=10), hoverlabel=dict(font_size=13))
    return fig


def summarize(frame, by):
    """by 기준으로 매출(price 합계)과 주문 수(order_id 고유 개수)를 계산합니다."""
    return (frame.groupby(by, as_index=False)
            .agg(sales=("price", "sum"), orders=("order_id", "nunique")))


def orders_of(frame):
    """상품 행 → 주문 행(주문 한 건 = 한 행). 리뷰·배송·결제는 주문 단위로 셉니다."""
    return frame.drop_duplicates("order_id")


def kpis(frame):
    o = orders_of(frame)
    delivered = o.dropna(subset=["delay_days"])
    counts = o["customer_uid"].value_counts()
    return {
        "sales": frame["price"].sum(),
        "orders": len(o),
        "aov": frame["price"].sum() / len(o),
        "review": o["review_score"].mean(),
        "ontime": (delivered["delay_days"] <= 0).mean() * 100 if len(delivered) else np.nan,
        "repeat": (counts >= 2).mean() * 100,
    }


cur = kpis(view)
prv = kpis(prev_view) if prev_view is not None else None


def pct_delta(key):
    if prv is None or not prv[key]:
        return None
    return f"{(cur[key] / prv[key] - 1) * 100:+.1f}%"


def pp_delta(key, digits=1, unit_txt="%p"):
    if prv is None or pd.isna(prv[key]) or pd.isna(cur[key]):
        return None
    return f"{cur[key] - prv[key]:+.{digits}f}{unit_txt}"


# =====================================================================
# 3. 제목과 KPI 카드
# =====================================================================
st.title("🛒 Olist 이커머스 성과 대시보드")
period_txt = f"{period[0]} ~ {period[1]}"
prev_txt = f" · 비교 기간 {prev_range[0]} ~ {prev_range[1]}" if prev_view is not None else ""
st.caption(f"분석 기간 {period_txt}{prev_txt} · 카드 아래 증감은 직전 동일 기간 대비 · 출처: Olist Brazilian E-Commerce Public Dataset (Kaggle) · 금액 단위: 브라질 헤알(R$)")

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("매출", f"R$ {cur['sales'] / 1e6:,.2f}M", pct_delta("sales"))
k2.metric("주문 수", f"{cur['orders']:,} 건", pct_delta("orders"))
k3.metric("객단가(주문당 매출)", f"R$ {cur['aov']:,.0f}", pct_delta("aov"))
k4.metric("평균 리뷰 점수", f"{cur['review']:.2f} / 5", pp_delta("review", 2, "점"))
k5.metric("정시 배송률", "-" if pd.isna(cur["ontime"]) else f"{cur['ontime']:.1f}%", pp_delta("ontime"))
k6.metric("재구매 고객 비율", f"{cur['repeat']:.1f}%", pp_delta("repeat"))

# ---------- 핵심 요약(선택 조건에 맞춰 자동으로 바뀝니다) ----------
by_cat = summarize(view, "category").sort_values("sales", ascending=False)
top_cat = by_cat.iloc[0]
top3_share = by_cat["sales"].head(3).sum() / by_cat["sales"].sum() * 100
ov = orders_of(view)
late = ov.dropna(subset=["delay_days", "review_score"])
late_flag = late["delay_days"] > 0
review_gap = (late.loc[~late_flag, "review_score"].mean() - late.loc[late_flag, "review_score"].mean()
              if late_flag.any() and (~late_flag).any() else np.nan)
bullets = []
growth = pct_delta("sales")
bullets.append(f"기간 매출은 <b>R$ {cur['sales']:,.0f}</b>"
               + (f"이며 직전 동일 기간 대비 <b>{growth}</b>입니다." if growth else "입니다."))
bullets.append(f"매출 1위 카테고리는 <b>{top_cat['category']}</b>(전체의 {top_cat['sales'] / by_cat['sales'].sum() * 100:.0f}%)이고 "
               f"상위 3개 카테고리가 <b>{top3_share:.0f}%</b>를 차지합니다.")
if not pd.isna(cur["ontime"]):
    txt = f"정시 배송률은 <b>{cur['ontime']:.1f}%</b>입니다."
    if not pd.isna(review_gap):
        txt += f" 지연된 주문의 평균 리뷰는 정시 주문보다 <b>{review_gap:.2f}점</b> 낮습니다(상관관계이며 원인을 단정할 수는 없습니다)."
    bullets.append(txt)
st.markdown('<div class="insight"><b>핵심 요약</b><ul>' + "".join(f"<li>{b}</li>" for b in bullets) + "</ul></div>",
            unsafe_allow_html=True)

# =====================================================================
# 4. 탭
# =====================================================================
tab_over, tab_prod, tab_geo, tab_cust, tab_ship, tab_data = st.tabs(
    ["📈 개요", "🛍️ 상품", "🗺️ 지역", "💳 고객·결제", "🚚 배송·리뷰", "📋 데이터·정의"])

# ---------- 개요 ----------
with tab_over:
    monthly = summarize(view, "month").sort_values("month")
    monthly["ma3"] = monthly[metric].rolling(3, min_periods=1).mean()
    left, right = st.columns([3, 2])

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=monthly["month"], y=monthly["sales"], name="매출(R$)", marker_color=BLUE, opacity=0.85)
    fig.add_scatter(x=monthly["month"], y=monthly["orders"], name="주문 수(건)", mode="lines+markers",
                    line=dict(color=ORANGE, width=3), secondary_y=True)
    fig.update_yaxes(title_text="매출(R$)", secondary_y=False, rangemode="tozero")
    fig.update_yaxes(title_text="주문 수(건)", secondary_y=True, rangemode="tozero", showgrid=False)
    fig.update_layout(title="월별 매출과 주문 수", legend=dict(orientation="h", y=-0.15))
    left.plotly_chart(style(fig, 400), width="stretch")

    top15 = by_cat.head(15)
    tree = px.treemap(top15, path=["category"], values="sales", color="sales",
                      color_continuous_scale="Blues", title="카테고리 매출 비중(상위 15개)")
    tree.update_traces(textinfo="label+percent root")
    tree.update_coloraxes(showscale=False)
    right.plotly_chart(style(tree, 400), width="stretch")

    c1, c2 = st.columns(2)
    wd = ov.assign(weekday=ov["purchase_date"].dt.dayofweek).groupby("weekday", as_index=False).agg(orders=("order_id", "nunique"))
    wd["요일"] = wd["weekday"].map(dict(enumerate(["월", "화", "수", "목", "금", "토", "일"])))
    wd_fig = px.bar(wd, x="요일", y="orders", text_auto=",.0f", title="요일별 주문 수",
                    labels={"orders": "주문 수(건)"}, color_discrete_sequence=[BLUE])
    wd_fig.update_traces(textposition="outside", cliponaxis=False)
    c1.plotly_chart(style(wd_fig, 330), width="stretch")

    st_base = data[data["month"].between(period[0], period[1])]
    if categories:
        st_base = st_base[st_base["category"].isin(categories)]
    st_sum = orders_of(st_base).groupby("order_status", as_index=False).agg(orders=("order_id", "nunique"))
    st_fig = px.bar(st_sum.sort_values("orders"), x="orders", y="order_status", orientation="h", text_auto=",.0f",
                    title="주문 상태 분포(기간 내 전체 주문)", labels={"orders": "주문 수(건)", "order_status": "상태"},
                    color_discrete_sequence=[GRAY])
    st_fig.update_traces(textposition="outside", cliponaxis=False)
    c2.plotly_chart(style(st_fig, 330), width="stretch")

# ---------- 상품 ----------
with tab_prod:
    prod = (view.groupby("category")
            .agg(sales=("price", "sum"), orders=("order_id", "nunique"), freight=("freight_value", "sum"))
            .sort_values("sales", ascending=False))
    ord_cat = ov.groupby("category").agg(review=("review_score", "mean"),
                                         late=("delay_days", lambda s: (s.dropna() > 0).mean() * 100))
    prod = prod.join(ord_cat)
    prod["share"] = prod["sales"] / prod["sales"].sum() * 100
    prod["cum"] = prod["share"].cumsum()
    prod["aov"] = prod["sales"] / prod["orders"]
    prod["freight_ratio"] = prod["freight"] / prod["sales"] * 100

    top = prod.head(15).reset_index()
    pareto = make_subplots(specs=[[{"secondary_y": True}]])
    pareto.add_bar(x=top["category"], y=top["sales"], name="매출(R$)", marker_color=BLUE)
    pareto.add_scatter(x=top["category"], y=top["cum"], name="누적 비중(%)", mode="lines+markers",
                       line=dict(color=ORANGE, width=3), secondary_y=True)
    pareto.update_yaxes(title_text="매출(R$)", secondary_y=False)
    pareto.update_yaxes(title_text="누적 비중(%)", range=[0, 100], tickvals=[0, 20, 40, 60, 80, 100], secondary_y=True, showgrid=False)
    pareto.update_layout(title="상위 15개 카테고리 매출과 누적 비중(파레토)", legend=dict(orientation="h", y=-0.35))
    st.plotly_chart(style(pareto, 430), width="stretch")

    heat = (summarize(view, ["month", "category"]).pivot(index="category", columns="month", values=metric).fillna(0)
            .loc[prod.head(10).index])
    heat_fig = px.imshow(heat, aspect="auto", color_continuous_scale="Blues",
                         labels={"x": "월", "y": "카테고리", "color": f"{metric_label}({unit})"},
                         title=f"월 × 카테고리 {metric_label} 히트맵(상위 10개)")
    st.plotly_chart(style(heat_fig, 420), width="stretch")

    st.markdown("**카테고리 성과표** (정렬하려면 열 이름을 누르세요)")
    show = prod.reset_index().rename(columns={
        "category": "카테고리", "sales": "매출(R$)", "orders": "주문 수", "share": "매출 비중(%)", "aov": "객단가(R$)",
        "review": "평균 리뷰", "late": "지연율(%)", "freight_ratio": "운임 비중(%)"})
    st.dataframe(
        show[["카테고리", "매출(R$)", "매출 비중(%)", "주문 수", "객단가(R$)", "평균 리뷰", "지연율(%)", "운임 비중(%)"]],
        hide_index=True, width="stretch", height=380,
        column_config={
            "매출(R$)": st.column_config.NumberColumn(format="%,.0f"),
            "매출 비중(%)": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=float(show["매출 비중(%)"].max())),
            "객단가(R$)": st.column_config.NumberColumn(format="%.0f"),
            "평균 리뷰": st.column_config.NumberColumn(format="%.2f"),
            "지연율(%)": st.column_config.NumberColumn(format="%.1f"),
            "운임 비중(%)": st.column_config.NumberColumn(format="%.1f"),
        })

# ---------- 지역 ----------
with tab_geo:
    geo = summarize(view, "customer_state")
    geo_o = ov.groupby("customer_state").agg(days=("delivery_days", "mean"), late=("delay_days", lambda s: (s.dropna() > 0).mean() * 100))
    geo = geo.set_index("customer_state").join(geo_o).reset_index()
    geo["lon"] = geo["customer_state"].map(lambda s: STATE_XY.get(s, (np.nan, np.nan))[0])
    geo["lat"] = geo["customer_state"].map(lambda s: STATE_XY.get(s, (np.nan, np.nan))[1])
    geo = geo.dropna(subset=["lon"])
    share_sp = geo.loc[geo["customer_state"] == "SP", "sales"].sum() / geo["sales"].sum() * 100 if "SP" in geo["customer_state"].values else 0
    top_state = geo.sort_values("sales", ascending=False).iloc[0]
    st.markdown(f'<div class="insight">매출이 가장 큰 주는 <b>{top_state["customer_state"]}</b>(전체의 '
                f'<b>{top_state["sales"] / geo["sales"].sum() * 100:.0f}%</b>)입니다. '
                f'버블 크기는 {metric_label}, 색은 평균 배송일(짙을수록 오래 걸림)입니다.</div>', unsafe_allow_html=True)
    left, right = st.columns([3, 2])
    bubble = px.scatter(geo, x="lon", y="lat", size=metric, color="days", text="customer_state",
                        size_max=55, color_continuous_scale="OrRd",
                        hover_data={"lon": False, "lat": False, "sales": ":,.0f", "orders": ":,", "days": ":.1f"},
                        labels={"days": "평균 배송일", "sales": "매출(R$)", "orders": "주문 수"},
                        title="브라질 주(State)별 버블 지도")
    bubble.update_traces(textposition="middle center", textfont_size=11)
    bubble.update_xaxes(visible=False)
    bubble.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    left.plotly_chart(style(bubble, 520), width="stretch")

    topn = geo.sort_values(metric, ascending=False).head(10).sort_values(metric)
    bar = px.bar(topn, x=metric, y="customer_state", orientation="h", text_auto=".3s",
                 labels={"customer_state": "주(State)", metric: f"{metric_label}({unit})"},
                 title=f"주별 {metric_label} 상위 10개", color_discrete_sequence=[BLUE])
    bar.update_traces(textposition="outside", cliponaxis=False)
    right.plotly_chart(style(bar, 520), width="stretch")

# ---------- 고객·결제 ----------
with tab_cust:
    c1, c2 = st.columns(2)
    pay = view.assign(결제수단=view["payment_type"].map(PAY_KO).fillna(view["payment_type"]))
    pay_sum = summarize(pay, "결제수단")
    donut = px.pie(pay_sum, names="결제수단", values="sales", hole=0.55, title="결제 수단별 매출 비중",
                   color_discrete_sequence=[BLUE, ORANGE, GREEN, GRAY, RED])
    donut.update_traces(textinfo="label+percent")
    c1.plotly_chart(style(donut, 360), width="stretch")

    inst = ov.assign(할부=ov["installments"].clip(upper=10).fillna(1).astype(int)).groupby("할부", as_index=False) \
             .agg(orders=("order_id", "nunique"))
    inst["할부"] = inst["할부"].astype(str).replace({"10": "10회+"})
    inst_fig = px.bar(inst, x="할부", y="orders", text_auto=",.0f", title="할부 개월 수별 주문 수",
                      labels={"orders": "주문 수(건)", "할부": "할부 개월 수"}, color_discrete_sequence=[BLUE])
    inst_fig.update_traces(textposition="outside", cliponaxis=False)
    c2.plotly_chart(style(inst_fig, 360), width="stretch")

    c3, c4 = st.columns(2)
    aov = pay.groupby("결제수단").apply(lambda g: g["price"].sum() / g["order_id"].nunique(), include_groups=False) \
             .reset_index(name="aov").sort_values("aov")
    aov_fig = px.bar(aov, x="aov", y="결제수단", orientation="h", text_auto=",.0f", title="결제 수단별 객단가(R$)",
                     labels={"aov": "객단가(R$)"}, color_discrete_sequence=[ORANGE])
    aov_fig.update_traces(textposition="outside", cliponaxis=False)
    c3.plotly_chart(style(aov_fig, 330), width="stretch")

    cnt = ov["customer_uid"].value_counts()
    split = pd.DataFrame({"구분": ["1회 구매 고객", "2회 이상 구매 고객"],
                          "고객 수": [int((cnt == 1).sum()), int((cnt >= 2).sum())]})
    split_fig = px.pie(split, names="구분", values="고객 수", hole=0.55, title="선택 기간 내 구매 횟수별 고객",
                       color_discrete_sequence=[BLUE, ORANGE])
    split_fig.update_traces(textinfo="label+percent")
    c4.plotly_chart(style(split_fig, 330), width="stretch")
    st.caption("재구매는 같은 customer_unique_id가 선택 기간 안에서 2건 이상 주문한 경우입니다. 이 데이터는 한 번만 구매한 고객이 대부분입니다.")

# ---------- 배송·리뷰 ----------
with tab_ship:
    deliv = ov.dropna(subset=["delay_days"]).copy()
    c1, c2 = st.columns(2)
    month_ot = deliv.groupby("month").agg(ontime=("delay_days", lambda s: (s <= 0).mean() * 100)).reset_index()
    ot_fig = px.line(month_ot, x="month", y="ontime", markers=True, title="월별 정시 배송률(%)",
                     labels={"month": "월", "ontime": "정시 배송률(%)"}, color_discrete_sequence=[GREEN])
    ot_fig.add_hline(y=90, line_dash="dash", line_color=GRAY, annotation_text="목표 90%(예시)", annotation_position="top left")
    ot_fig.update_yaxes(range=[max(0, month_ot["ontime"].min() - 10), 100])
    c1.plotly_chart(style(ot_fig, 360), width="stretch")

    hist = px.histogram(deliv.assign(delay=deliv["delay_days"].clip(-30, 30)), x="delay", nbins=60,
                        title="예정일 대비 도착일 차이(일, 음수 = 일찍 도착)",
                        labels={"delay": "도착일 − 예정일(일)"}, color_discrete_sequence=[BLUE])
    hist.update_yaxes(title_text="주문 수(건)")
    hist.add_vline(x=0, line_dash="dash", line_color=RED)
    c2.plotly_chart(style(hist, 360), width="stretch")

    c3, c4 = st.columns(2)
    rv = deliv.dropna(subset=["review_score"]).copy()
    rv["구분"] = np.where(rv["delay_days"] > 0, "지연 도착", "정시·조기 도착")
    rv["점수"] = rv["review_score"].round().astype(int)
    share = (rv.groupby(["구분", "점수"]).size() / rv.groupby("구분").size()).reset_index(name="비중")
    share["비중"] *= 100
    share_fig = px.bar(share, x="점수", y="비중", color="구분", barmode="group", text_auto=".0f",
                       title="도착 구분별 리뷰 점수 분포(%)", labels={"비중": "비중(%)"},
                       color_discrete_map={"지연 도착": RED, "정시·조기 도착": BLUE})
    share_fig.update_traces(textposition="outside", cliponaxis=False)
    c3.plotly_chart(style(share_fig, 360), width="stretch")

    bins = pd.cut(rv["delay_days"], [-100, -10, 0, 3, 7, 1000], labels=["10일+ 일찍", "0~10일 일찍", "0~3일 지연", "3~7일 지연", "7일+ 지연"])
    by_delay = rv.groupby(bins, observed=True).agg(review=("review_score", "mean"), n=("order_id", "nunique")).reset_index()
    by_delay.columns = ["구간", "review", "n"]
    delay_fig = px.bar(by_delay, x="구간", y="review", text_auto=".2f", title="지연 구간별 평균 리뷰 점수",
                       labels={"review": "평균 리뷰 점수"}, color_discrete_sequence=[ORANGE])
    delay_fig.update_yaxes(range=[0, 5.2])
    delay_fig.update_traces(textposition="outside", cliponaxis=False)
    c4.plotly_chart(style(delay_fig, 360), width="stretch")

# ---------- 데이터·정의 ----------
with tab_data:
    st.subheader("월·카테고리별 집계")
    table = summarize(view, ["month", "category"]).sort_values(["month", "sales"], ascending=[True, False])
    table = table.rename(columns={"month": "월", "category": "카테고리", "sales": "매출(R$)", "orders": "주문 수"})
    table["매출(R$)"] = table["매출(R$)"].round(0)
    st.dataframe(table, hide_index=True, width="stretch", height=360)
    d1, d2 = st.columns(2)
    d1.download_button("집계표 CSV 저장", data=table.to_csv(index=False).encode("utf-8-sig"),
                       file_name="olist_summary.csv", mime="text/csv")
    d2.download_button("선택 조건의 주문 상품 원본 CSV 저장",
                       data=view.drop(columns=["customer_uid"]).to_csv(index=False).encode("utf-8-sig"),
                       file_name="olist_selected_rows.csv", mime="text/csv")

    with st.expander("지표 정의와 해석 시 주의할 점"):
        st.markdown(
            """
- **매출**: 상품 가격(`price`) 합계이며 배송비(`freight_value`)는 제외합니다. 통화는 브라질 헤알(R$)입니다.
- **주문 수**: 서로 다른 `order_id`의 개수입니다. 한 주문에 여러 상품이 있어도 1건으로 셉니다.
- **객단가**: 매출 ÷ 주문 수입니다.
- **정시 배송률**: 배송이 완료된 주문 중 실제 도착일이 예정일 이하인 비율입니다.
- **재구매 고객 비율**: 선택 기간 안에서 같은 고객(`customer_unique_id`)이 2건 이상 주문한 비율입니다.
- **전기 대비**: 선택 기간과 길이가 같은 직전 기간을 같은 필터로 계산해 비교합니다.
- 리뷰와 배송의 관계는 **상관관계**이며, 배송 지연이 리뷰 하락의 원인이라고 단정할 수 없습니다.
- 데이터는 2016-09~2018-09의 공개 데이터이며, 주문이 적은 2016년과 2018-09는 조회 기간에서 제외했습니다.
            """)

st.divider()
st.markdown('<p class="note">교육용 개인 프로젝트 · 데이터: Olist (Kaggle, 공개 데이터) · '
            '지도는 주(State)의 대략적인 중심 위치를 표시한 것입니다.</p>', unsafe_allow_html=True)
