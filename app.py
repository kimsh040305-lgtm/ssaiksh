from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Olist 이커머스 대시보드", page_icon="🛒", layout="wide")

# ---------- 0. 스타일 ----------
BLUE, ORANGE, GRAY = "#0072B2", "#D55E00", "#6B7280"
st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; max-width: 1300px;}
    div[data-testid="stMetric"] {
        background: #F5F8FB; border: 1px solid #DCE6F0; border-radius: 12px;
        padding: 14px 18px;}
    div[data-testid="stMetricLabel"] {color: #4B5563;}
    .insight {background: #EEF6FF; border-left: 5px solid #0072B2; border-radius: 6px;
        padding: 12px 16px; margin: 6px 0 14px 0; color: #1F2937;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🛒 Olist 브라질 이커머스 대시보드")
st.caption("출처: Olist, Brazilian E-Commerce Public Dataset (Kaggle) · 2016-09 ~ 2018-09 · 금액 단위: 브라질 헤알(R$)")

HERE = Path(__file__).parent   # app.py가 있는 폴더


@st.cache_data
def load_data():
    return pd.read_csv(HERE / "olist_orders.csv")


data = load_data()

# ---------- 1. 사이드바 위젯 ----------
months_all = sorted(data["month"].unique())
months_main = [m for m in months_all if "2017-01" <= m <= "2018-08"]   # 주문이 충분한 기간
status_all = data["order_status"].value_counts().index.tolist()
top_categories = (data.groupby("category")["price"].sum()
                  .sort_values(ascending=False).index.tolist())

st.sidebar.header("조회 조건")
period = st.sidebar.select_slider("기간(월)", options=months_main,
                                  value=(months_main[0], months_main[-1]))
statuses = st.sidebar.multiselect("주문 상태", status_all, default=["delivered"])
categories = st.sidebar.multiselect("상품 카테고리", top_categories, default=top_categories[:8])
metric_label = st.sidebar.selectbox("표시 지표", ["매출", "주문 수"])
st.sidebar.caption("카테고리 기본값은 매출 상위 8개입니다.")

# ---------- 2. 필터와 빈 선택 ----------
view = data.loc[data["order_status"].isin(statuses)
                & data["category"].isin(categories)
                & data["month"].between(period[0], period[1])].copy()
if view.empty:
    st.warning("표시할 데이터가 없습니다. 주문 상태와 카테고리를 하나 이상 선택하세요.")
    st.stop()


def summarize(frame, by):
    """by 기준으로 매출(price 합계)과 주문 수(order_id 고유 개수)를 계산합니다."""
    return (frame.groupby(by, as_index=False)
            .agg(sales=("price", "sum"), orders=("order_id", "nunique")))


metric = {"매출": "sales", "주문 수": "orders"}[metric_label]
unit = "R$" if metric == "sales" else "건"

# ---------- 3. 지표 카드 ----------
total_sales = view["price"].sum()
total_orders = view["order_id"].nunique()
c1, c2, c3, c4 = st.columns(4)
c1.metric("매출 합계", f"R$ {total_sales / 1_000_000:,.2f}M")   # M = 백만(카드 안에서 잘리지 않게 줄여 씁니다)
c2.metric("주문 수", f"{total_orders:,} 건")
c3.metric("평균 주문 금액", f"R$ {total_sales / total_orders:,.0f}")
c4.metric("평균 리뷰 점수", f"{view['review_score'].mean():.2f} / 5")

# ---------- 4. 핵심 요약(선택 조건에 맞춰 자동으로 바뀝니다) ----------
monthly = summarize(view, "month").sort_values("month")
by_cat = summarize(view, "category").sort_values(metric, ascending=False)
peak = monthly.loc[monthly[metric].idxmax()]
best_cat = by_cat.iloc[0]
share = best_cat[metric] / by_cat[metric].sum() * 100
fmt = (lambda v: f"R$ {v:,.0f}") if metric == "sales" else (lambda v: f"{v:,.0f} 건")
st.markdown(
    f'<div class="insight"><b>핵심 요약</b> · 선택한 조건에서 {metric_label}이 가장 큰 달은 '
    f'<b>{peak["month"]}</b>({fmt(peak[metric])})이고, 가장 큰 카테고리는 '
    f'<b>{best_cat["category"]}</b>로 전체의 <b>{share:.0f}%</b>를 차지합니다.</div>',
    unsafe_allow_html=True,
)

# ---------- 5. 탭 ----------
tab1, tab2, tab3, tab4 = st.tabs(["📈 추이와 카테고리", "🗺️ 지역", "⭐ 리뷰와 배송", "📋 표와 내려받기"])

with tab1:
    left, right = st.columns(2)
    trend = px.line(monthly, x="month", y=metric, markers=True,
                    labels={"month": "월", metric: f"{metric_label} ({unit})"},
                    title=f"월별 {metric_label}", color_discrete_sequence=[BLUE])
    trend.update_yaxes(rangemode="tozero")
    left.plotly_chart(trend, width="stretch")

    top10 = by_cat.head(10).sort_values(metric)
    bar = px.bar(top10, x=metric, y="category", orientation="h",
                 labels={"category": "카테고리", metric: f"{metric_label} ({unit})"},
                 title=f"카테고리별 {metric_label} (상위 10개)", color_discrete_sequence=[BLUE])
    right.plotly_chart(bar, width="stretch")

with tab2:
    by_state = summarize(view, "customer_state").sort_values(metric, ascending=False)
    top_state = by_state.iloc[0]
    st.markdown(
        f'<div class="insight">{metric_label}이 가장 큰 주(State)는 <b>{top_state["customer_state"]}</b>이며 '
        f'전체의 <b>{top_state[metric] / by_state[metric].sum() * 100:.0f}%</b>입니다.</div>',
        unsafe_allow_html=True)
    left, right = st.columns(2)
    state_fig = px.bar(by_state.head(10), x="customer_state", y=metric,
                       labels={"customer_state": "주(State)", metric: f"{metric_label} ({unit})"},
                       title=f"주별 {metric_label} (상위 10개)", color_discrete_sequence=[BLUE])
    left.plotly_chart(state_fig, width="stretch")

    delivery_state = (view.dropna(subset=["delivery_days"]).groupby("customer_state", as_index=False)
                      .agg(days=("delivery_days", "mean"), n=("order_id", "nunique")))
    delivery_state = delivery_state[delivery_state["n"] >= 30].sort_values("days", ascending=False).head(10)
    days_fig = px.bar(delivery_state.sort_values("days"), x="days", y="customer_state", orientation="h",
                      labels={"days": "평균 배송일(일)", "customer_state": "주(State)"},
                      title="평균 배송일이 긴 주 (주문 30건 이상)", color_discrete_sequence=[ORANGE])
    right.plotly_chart(days_fig, width="stretch")

with tab3:
    reviewed = view.dropna(subset=["review_score"]).copy()
    reviewed["score"] = reviewed["review_score"].round().astype(int)
    dist = reviewed.groupby("score", as_index=False).agg(orders=("order_id", "nunique"))
    left, right = st.columns(2)
    dist_fig = px.bar(dist, x="score", y="orders",
                      labels={"score": "리뷰 점수", "orders": "주문 수(건)"},
                      title="리뷰 점수 분포", color_discrete_sequence=[BLUE])
    dist_fig.update_xaxes(dtick=1)
    left.plotly_chart(dist_fig, width="stretch")

    delivered = reviewed.dropna(subset=["delivery_days"])
    by_score = delivered.groupby("score", as_index=False).agg(days=("delivery_days", "mean"))
    days_score = px.bar(by_score, x="score", y="days",
                        labels={"score": "리뷰 점수", "days": "평균 배송일(일)"},
                        title="리뷰 점수별 평균 배송일", color_discrete_sequence=[ORANGE])
    days_score.update_xaxes(dtick=1)
    right.plotly_chart(days_score, width="stretch")
    if len(by_score) >= 2:
        low = by_score.loc[by_score["score"].idxmin()]
        high = by_score.loc[by_score["score"].idxmax()]
        st.markdown(
            f'<div class="insight">리뷰 {int(low["score"])}점 주문은 평균 <b>{low["days"]:.1f}일</b>, '
            f'{int(high["score"])}점 주문은 평균 <b>{high["days"]:.1f}일</b> 만에 도착했습니다. '
            f'배송이 늦을수록 리뷰 점수가 낮은 경향이 있습니다(상관관계이며 원인을 단정할 수는 없습니다).</div>',
            unsafe_allow_html=True)

with tab4:
    table = summarize(view, ["month", "category"]).sort_values(["month", "sales"], ascending=[True, False])
    table = table.rename(columns={"month": "월", "category": "카테고리", "sales": "매출(R$)", "orders": "주문 수"})
    table["매출(R$)"] = table["매출(R$)"].round(0)
    st.dataframe(table, hide_index=True, width="stretch")
    st.download_button("현재 선택 CSV 저장", data=table.to_csv(index=False).encode("utf-8-sig"),
                       file_name="olist_selected.csv", mime="text/csv")

st.divider()
st.caption("교육용 개인 프로젝트 · 데이터: Olist (Kaggle, 공개 데이터) · 매출은 상품 가격(price) 합계이며 배송비는 제외했습니다.")
