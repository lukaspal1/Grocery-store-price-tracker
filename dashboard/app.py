# dashboard/app.py
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent.parent / "data" / "prices.db"

st.set_page_config(page_title="Czech Grocery Price Tracker", page_icon="🛒", layout="wide")
st.title("🛒 Czech Grocery Price Tracker")
st.caption("Real-time price and promotion data scraped from Czech online grocers.")


@st.cache_data(ttl=300)
def load_current():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM current_prices", conn)
    conn.close()
    return df


@st.cache_data(ttl=300)
def load_history():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM price_history", conn)
    conn.close()
    return df


df = load_current()

if df.empty:
    st.warning("No data yet. Run `py main.py` to scrape prices.")
    st.stop()

# ------------------------------------------------------------------ #
#  Top-level metrics                                                 #
# ------------------------------------------------------------------ #
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total products", len(df))
col2.metric("On sale", int(df["is_on_sale"].sum()))
col3.metric("Stores", df["store"].nunique())
col4.metric(
    "Last update",
    pd.to_datetime(df["updated_at"]).max().strftime("%Y-%m-%d %H:%M"),
)

st.divider()

# ------------------------------------------------------------------ #
#  Browse products                                                   #
# ------------------------------------------------------------------ #
st.subheader("Browse products")

col_a, col_b, col_c = st.columns([2, 1, 1])
with col_a:
    search = st.text_input("Search product name", "")
with col_b:
    stores = st.multiselect(
        "Store",
        sorted(df["store"].unique()),
        default=list(df["store"].unique()),
    )
with col_c:
    only_sales = st.checkbox("On sale only", value=False)

view = df.copy()
if search:
    view = view[view["name"].str.contains(search, case=False, na=False)]
if stores:
    view = view[view["store"].isin(stores)]
if only_sales:
    view = view[view["is_on_sale"] == 1]

view = view.sort_values(
    ["is_on_sale", "discount_pct", "name"],
    ascending=[False, False, True],
)

display_cols = [
    "store", "name", "brand", "price", "original_price",
    "discount_pct", "unit", "in_stock", "promo_ends", "source_url",
]
st.dataframe(
    view[display_cols],
    use_container_width=True,
    hide_index=True,
    column_config={
        "price": st.column_config.NumberColumn("Price (CZK)", format="%.2f Kč"),
        "original_price": st.column_config.NumberColumn("Was (CZK)", format="%.2f Kč"),
        "discount_pct": st.column_config.NumberColumn("Discount", format="%d%%"),
        "in_stock": st.column_config.CheckboxColumn("In stock"),
        "promo_ends": st.column_config.TextColumn("Promo ends"),
        "store": st.column_config.TextColumn("Store"),
        "name": st.column_config.TextColumn("Product"),
        "brand": st.column_config.TextColumn("Brand"),
        "unit": st.column_config.TextColumn("Unit"),
        "source_url": st.column_config.LinkColumn("Link"),
    },
)

# ------------------------------------------------------------------ #
#  Top discounts                                                     #
# ------------------------------------------------------------------ #
if df["is_on_sale"].any():
    st.divider()
    st.subheader("🔥 Top discounts right now")
    top = df[df["is_on_sale"] == 1].nlargest(10, "discount_pct")
    st.dataframe(
        top[["name", "brand", "original_price", "price", "discount_pct", "promo_ends"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "price": st.column_config.NumberColumn("Now (CZK)", format="%.2f Kč"),
            "original_price": st.column_config.NumberColumn("Was (CZK)", format="%.2f Kč"),
            "discount_pct": st.column_config.NumberColumn("Discount", format="%d%%"),
            "promo_ends": st.column_config.TextColumn("Ends"),
        },
    )

# ------------------------------------------------------------------ #
#  Price history                                                     #
# ------------------------------------------------------------------ #
st.divider()
st.subheader("📈 Price history")

hist = load_history()
if hist.empty:
    st.info("No price history yet. Run the scraper again later to build history.")
else:
    # Let user pick a product that actually has >1 history row
    counts = hist.groupby(["store", "product_id"]).size()
    multi = counts[counts > 1]
    if multi.empty:
        st.info(
            "History is being recorded, but no product has changed price yet. "
            "Come back after a few scrapes."
        )
    else:
        options = [f"{store} · {pid}" for (store, pid) in multi.index]
        choice = st.selectbox("Pick a product with price changes", options)
        store, pid = choice.split(" · ", 1)
        subset = hist[(hist["store"] == store) & (hist["product_id"] == pid)].copy()
        subset = subset.sort_values("recorded_at")
        st.line_chart(subset, x="recorded_at", y="price")
        st.dataframe(subset, use_container_width=True, hide_index=True)