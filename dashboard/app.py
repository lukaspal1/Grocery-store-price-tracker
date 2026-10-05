# dashboard/app.py
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent.parent / "data" / "prices.db"

st.set_page_config(page_title="Czech Grocery Price Tracker", page_icon="🛒", layout="wide")
st.title("🛒 Czech Grocery Price Tracker")
st.caption("Cross-store price comparison for Czech online grocers.")


# ------------------------------------------------------------------ #
#  Data loading                                                      #
# ------------------------------------------------------------------ #
@st.cache_data(ttl=300)
def load_current():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM current_prices", conn)
    conn.close()
    return df


@st.cache_data(ttl=300)
def load_matches():
    """Join matches with both sides' current prices."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        """
        SELECT
            pm.canonical_key,
            pm.score,
            pm.store_a, ca.product_id AS product_id_a, ca.name AS name_a,
            ca.brand AS brand_a, ca.price AS price_a, ca.unit AS unit_a,
            ca.is_on_sale AS sale_a, ca.discount_pct AS disc_a,
            ca.original_price AS orig_a,
            pm.store_b, cb.product_id AS product_id_b, cb.name AS name_b,
            cb.brand AS brand_b, cb.price AS price_b, cb.unit AS unit_b,
            cb.is_on_sale AS sale_b, cb.discount_pct AS disc_b,
            cb.original_price AS orig_b
        FROM product_matches pm
        JOIN current_prices ca
          ON ca.store = pm.store_a AND ca.product_id = pm.product_id_a
        JOIN current_prices cb
          ON cb.store = pm.store_b AND cb.product_id = pm.product_id_b
        """,
        conn,
    )
    conn.close()
    return df


@st.cache_data(ttl=300)
def load_history():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM price_history", conn)
    conn.close()
    return df


df = load_current()
matches = load_matches()

if df.empty:
    st.warning("No data yet. Run `py main.py` to scrape prices, then `py -m pipeline.run_matcher`.")
    st.stop()


# ------------------------------------------------------------------ #
#  Top metrics                                                       #
# ------------------------------------------------------------------ #
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Products tracked", len(df))
col2.metric("On sale", int(df["is_on_sale"].sum()))
col3.metric("Stores", df["store"].nunique())
col4.metric("Cross-store matches", len(matches))
col5.metric(
    "Last scrape",
    pd.to_datetime(df["updated_at"]).max().strftime("%Y-%m-%d %H:%M"),
)

st.divider()


# ------------------------------------------------------------------ #
#  Cross-store comparison                                            #
# ------------------------------------------------------------------ #
st.subheader("💱 Cross-store price comparison")
st.caption(
    f"{len(matches)} products matched across stores. Cheaper store is highlighted."
)

if matches.empty:
    st.info("No matches yet. Run `py -m pipeline.run_matcher` to generate them.")
else:
    # Compute which store is cheaper, and by how much
    cmp_df = matches.copy()
    cmp_df["cheaper_store"] = cmp_df.apply(
        lambda r: r["store_a"] if r["price_a"] < r["price_b"]
        else r["store_b"] if r["price_b"] < r["price_a"]
        else "same",
        axis=1,
    )
    cmp_df["abs_diff"] = (cmp_df["price_a"] - cmp_df["price_b"]).abs()
    cmp_df["pct_diff"] = (cmp_df["abs_diff"] / cmp_df[["price_a", "price_b"]].max(axis=1) * 100).round(1)

    # Filters
    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        match_search = st.text_input("Search matched products", "", key="match_search")
    with col_b:
        min_discount = st.slider("Minimum price difference (Kč)", 0.0, 50.0, 0.0, 0.5)
    with col_c:
        min_score = st.slider("Minimum match confidence", 0.80, 1.00, 0.90, 0.01)

    view = cmp_df[cmp_df["score"] >= min_score]
    view = view[view["abs_diff"] >= min_discount]
    if match_search:
        mask = (
            view["name_a"].str.contains(match_search, case=False, na=False)
            | view["name_b"].str.contains(match_search, case=False, na=False)
        )
        view = view[mask]
    view = view.sort_values("abs_diff", ascending=False)

    # Display table
    display = view[[
        "name_a", "brand_a", "unit_a", "price_a", "sale_a", "disc_a",
        "name_b", "brand_b", "unit_b", "price_b", "sale_b", "disc_b",
        "cheaper_store", "abs_diff", "pct_diff", "score",
    ]].rename(columns={
        "name_a": "Product (store A)",
        "brand_a": "Brand A",
        "unit_a": "Unit A",
        "price_a": f"Price A ({matches['store_a'].iloc[0]})",
        "sale_a": "Sale A",
        "disc_a": "Disc % A",
        "name_b": "Product (store B)",
        "brand_b": "Brand B",
        "unit_b": "Unit B",
        "price_b": f"Price B ({matches['store_b'].iloc[0]})",
        "sale_b": "Sale B",
        "disc_b": "Disc % B",
        "cheaper_store": "Cheaper",
        "abs_diff": "Diff (Kč)",
        "pct_diff": "Diff %",
        "score": "Match",
    })

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=500,
        column_config={
            display.columns[3]: st.column_config.NumberColumn(format="%.2f Kč"),
            display.columns[7]: st.column_config.NumberColumn(format="%.2f Kč"),
            "Diff (Kč)": st.column_config.NumberColumn(format="%.2f Kč"),
            "Diff %": st.column_config.NumberColumn(format="%.1f%%"),
            "Match": st.column_config.NumberColumn(format="%.2f"),
            "Sale A": st.column_config.CheckboxColumn(),
            "Sale B": st.column_config.CheckboxColumn(),
        },
    )

    # Potential savings summary
    total_at_a = view["price_a"].sum()
    total_at_b = view["price_b"].sum()
    total_cheapest = view[["price_a", "price_b"]].min(axis=1).sum()
    savings = max(total_at_a, total_at_b) - total_cheapest

    st.markdown("---")
    st.markdown("**If you bought every matched item at the cheapest store:**")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Total at {matches['store_a'].iloc[0]}", f"{total_at_a:.2f} Kč")
    c2.metric(f"Total at {matches['store_b'].iloc[0]}", f"{total_at_b:.2f} Kč")
    c3.metric("Cheapest combined basket", f"{total_cheapest:.2f} Kč")
    c4.metric("Potential savings", f"{savings:.2f} Kč", delta=None)


st.divider()


# ------------------------------------------------------------------ #
#  Browse all products                                               #
# ------------------------------------------------------------------ #
st.subheader("🔎 Browse all products")

col_a, col_b, col_c = st.columns([2, 1, 1])
with col_a:
    search = st.text_input("Search product name", "", key="browse_search")
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
    height=400,
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
        top[["store", "name", "brand", "original_price", "price", "discount_pct", "promo_ends"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "store": st.column_config.TextColumn("Store"),
            "name": st.column_config.TextColumn("Product"),
            "brand": st.column_config.TextColumn("Brand"),
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