from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import auth

st.set_page_config(page_title="Retail Sales Dashboard", page_icon="🛒", layout="wide")

DATA_PATH = Path(__file__).parent / "data" / "retail_sales.csv"
COLORS = ["#4F46E5", "#06B6D4", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]
ALIASES = {
    "date": ["order_date", "date", "orderdate", "invoice_date"],
    "revenue": ["revenue", "sales", "total_sales", "amount", "total"],
    "quantity": ["quantity", "qty", "units", "units_sold"],
    "unit_price": ["unit_price", "price"],
    "product": ["product", "product_name", "item"],
    "category": ["category", "product_category"],
    "region": ["region", "state", "area"],
    "order_id": ["order_id", "orderid", "invoice", "invoice_no"],
}

st.markdown(
    """
<style>
.block-container {padding-top: 1.5rem; max-width: 1300px;}
[data-testid="stSidebar"] {background: linear-gradient(180deg,#1e1b4b,#312e81);}
[data-testid="stSidebar"] * {color: #e0e7ff !important;}
.hero {background: linear-gradient(90deg,#4F46E5,#06B6D4); color: white;
       padding: 1.2rem 1.5rem; border-radius: 16px; margin-bottom: 1rem;}
.hero h1 {margin: 0; font-size: 1.8rem; color: white;}
.hero p {margin: 0.2rem 0 0; opacity: .9;}
.kpi {background: white; border-radius: 14px; padding: 1rem 1.2rem; margin-bottom: .6rem;
      border-left: 6px solid #4F46E5; box-shadow: 0 2px 10px rgba(0,0,0,.08);}
.kpi .label {color: #6b7280; font-size: .85rem; font-weight: 600;}
.kpi .value {color: #111827; font-size: 1.7rem; font-weight: 800;}
.insight {background: #eef2ff; border-radius: 12px; padding: .8rem 1rem;
          margin-bottom: .6rem; color: #1e1b4b;}
@media (max-width: 640px) {.hero h1 {font-size: 1.3rem;} .kpi .value {font-size: 1.3rem;}}
</style>
""",
    unsafe_allow_html=True,
)


auth.require_login()  # show login page until the user signs in


# ---------- Data loading & cleaning ----------
@st.cache_data
def read_default():
    return pd.read_csv(DATA_PATH)


def read_upload(file):
    try:
        return pd.read_csv(file)
    except UnicodeDecodeError:
        file.seek(0)
        return pd.read_csv(file, encoding="latin-1")


def clean_data(raw):
    """Standardize columns, fix types, drop bad rows. Returns (clean_df, log)."""
    df = raw.copy()
    log = []
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    for target, names in ALIASES.items():
        if target not in df.columns:
            for n in names:
                if n in df.columns:
                    df = df.rename(columns={n: target})
                    break

    if "date" not in df.columns:
        raise ValueError("No date column found. Add a column like 'order_date' or 'date'.")

    for col in ["revenue", "quantity", "unit_price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(r"[^\d.\-]", "", regex=True), errors="coerce"
            )
    if "revenue" not in df.columns:
        if "quantity" in df.columns and "unit_price" in df.columns:
            df["revenue"] = df["quantity"] * df["unit_price"]
            log.append("Revenue column missing - calculated as quantity x unit_price.")
        else:
            raise ValueError("No revenue column found. Add 'revenue' or 'sales' (or quantity + unit_price).")

    start = len(df)
    df = df.drop_duplicates()
    log.append(f"Removed {start - len(df)} duplicate rows.")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    start = len(df)
    df = df.dropna(subset=["date", "revenue"])
    log.append(f"Removed {start - len(df)} rows with invalid/missing date or revenue.")

    start = len(df)
    df = df[df["revenue"] >= 0]
    log.append(f"Removed {start - len(df)} rows with negative revenue.")

    for col in ["category", "region", "product", "order_id"]:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown").astype(str).str.strip()
    if "quantity" in df.columns:
        df["quantity"] = df["quantity"].fillna(0)

    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    return df.reset_index(drop=True), log


def money(x):
    return f"${x:,.0f}"


def kpi(label, value):
    return f'<div class="kpi"><div class="label">{label}</div><div class="value">{value}</div></div>'


def show(fig, title):
    fig.update_layout(
        title=title, height=370, margin=dict(l=10, r=10, t=50, b=10),
        template="plotly_white", legend_title_text="",
    )
    st.plotly_chart(fig, width="stretch")


# ---------- Sidebar ----------
st.sidebar.title("🛒 Retail Analytics")
auth.sidebar_user()
page = st.sidebar.radio("Navigate", ["Dashboard", "Data Preview", "Data Cleaning", "Insights", "Downloads"])
st.sidebar.markdown("---")
source = st.sidebar.radio("Data source", ["Sample dataset", "Upload CSV"])

try:
    if source == "Upload CSV":
        up = st.sidebar.file_uploader("Upload your CSV", type=["csv"])
        if up is None:
            st.info("👈 Upload a CSV file in the sidebar, or switch to the sample dataset.")
            st.stop()
        raw = read_upload(up)
    else:
        raw = read_default()
    df_all, clean_log = clean_data(raw)
    if df_all.empty:
        raise ValueError("No valid rows left after cleaning.")
except ValueError as e:
    st.error(f"⚠️ {e}")
    st.stop()
except Exception as e:
    st.error(f"⚠️ Could not read the file: {e}")
    st.stop()

# ---------- Filters ----------
st.sidebar.markdown("### Filters")
dmin, dmax = df_all["date"].min().date(), df_all["date"].max().date()
dr = st.sidebar.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
d1, d2 = (dr[0], dr[1]) if isinstance(dr, (tuple, list)) and len(dr) == 2 else (dmin, dmax)
df = df_all[(df_all["date"].dt.date >= d1) & (df_all["date"].dt.date <= d2)]

for col, label in [("category", "Category"), ("region", "Region")]:
    if col in df.columns:
        opts = sorted(df_all[col].unique())
        chosen = st.sidebar.multiselect(label, opts, default=opts)
        df = df[df[col].isin(chosen)]

st.markdown(
    '<div class="hero"><h1>Retail Sales Dashboard</h1>'
    "<p>Interactive analysis of orders, revenue and products</p></div>",
    unsafe_allow_html=True,
)

if df.empty:
    st.warning("No data matches the selected filters. Please widen your selection.")
    st.stop()

revenue = df["revenue"].sum()
orders = df["order_id"].nunique() if "order_id" in df.columns else len(df)
units = df["quantity"].sum() if "quantity" in df.columns else None
aov = revenue / orders if orders else 0

# ---------- Pages ----------
if page == "Dashboard":
    c = st.columns(4)
    c[0].markdown(kpi("💰 Total Revenue", money(revenue)), unsafe_allow_html=True)
    c[1].markdown(kpi("🧾 Orders", f"{orders:,}"), unsafe_allow_html=True)
    c[2].markdown(kpi("📦 Units Sold", f"{units:,.0f}" if units is not None else "N/A"), unsafe_allow_html=True)
    c[3].markdown(kpi("🏷️ Avg Order Value", money(aov)), unsafe_allow_html=True)

    monthly = df.groupby("month", as_index=False)["revenue"].sum()
    left, right = st.columns(2)
    with left:
        fig = px.area(monthly, x="month", y="revenue", markers=True, color_discrete_sequence=COLORS)
        show(fig, "Monthly Sales")
    with right:
        if "category" in df.columns:
            cat = df.groupby("category", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
            show(px.bar(cat, x="category", y="revenue", color="category", color_discrete_sequence=COLORS), "Revenue by Category")
        else:
            st.info("Add a 'category' column to see category revenue.")
    left, right = st.columns(2)
    with left:
        if "product" in df.columns:
            top = df.groupby("product", as_index=False)["revenue"].sum().nlargest(10, "revenue").sort_values("revenue")
            show(px.bar(top, x="revenue", y="product", orientation="h", color_discrete_sequence=["#4F46E5"]), "Top 10 Products")
        else:
            st.info("Add a 'product' column to see top products.")
    with right:
        if "region" in df.columns:
            reg = df.groupby("region", as_index=False)["revenue"].sum()
            show(px.pie(reg, names="region", values="revenue", hole=0.5, color_discrete_sequence=COLORS), "Regional Sales")
        else:
            st.info("Add a 'region' column to see regional sales.")

elif page == "Data Preview":
    st.subheader("Data Preview")
    a, b, c = st.columns(3)
    a.metric("Rows", f"{len(df):,}")
    b.metric("Columns", len(df.columns))
    c.metric("Date range", f"{d1} → {d2}")
    st.dataframe(df.head(100), width="stretch")
    st.subheader("Summary statistics")
    st.dataframe(df.describe().T, width="stretch")

elif page == "Data Cleaning":
    st.subheader("Data Cleaning Report")
    a, b = st.columns(2)
    a.metric("Raw rows", f"{len(raw):,}")
    b.metric("Clean rows", f"{len(df_all):,}")
    for line in clean_log:
        st.markdown(f'<div class="insight">✅ {line}</div>', unsafe_allow_html=True)
    st.markdown("**Missing values in original file**")
    missing = raw.isna().sum().reset_index()
    missing.columns = ["column", "missing"]
    st.dataframe(missing, width="stretch")

elif page == "Insights":
    st.subheader("Automatic Insights")
    tips = []
    monthly = df.groupby("month")["revenue"].sum()
    tips.append(f"📈 Best month: **{monthly.idxmax():%B %Y}** with {money(monthly.max())}.")
    if len(monthly) > 1:
        chg = (monthly.iloc[-1] / monthly.iloc[-2] - 1) * 100 if monthly.iloc[-2] else 0
        tips.append(f"📊 Latest month changed **{chg:+.1f}%** versus the previous month.")
    for col, name in [("category", "category"), ("region", "region"), ("product", "product")]:
        if col in df.columns:
            g = df.groupby(col)["revenue"].sum()
            tips.append(f"🏆 Top {name}: **{g.idxmax()}** ({g.max() / revenue:.0%} of revenue).")
            if col != "product" and len(g) > 1:
                tips.append(f"⚠️ Lowest {name}: **{g.idxmin()}** ({money(g.min())}).")
    tips.append(f"🧮 Average order value is **{money(aov)}** across {orders:,} orders.")
    for t in tips:
        st.markdown(f'<div class="insight">{t}</div>', unsafe_allow_html=True)

elif page == "Downloads":
    st.subheader("Download Data")
    st.download_button("⬇️ Filtered data (CSV)", df.drop(columns="month").to_csv(index=False).encode("utf-8"),
                       "filtered_sales.csv", "text/csv")
    st.download_button("⬇️ Full cleaned data (CSV)", df_all.drop(columns="month").to_csv(index=False).encode("utf-8"),
                       "cleaned_sales.csv", "text/csv")
