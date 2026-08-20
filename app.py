import sqlite3
from datetime import date, datetime
import pandas as pd
import plotly.express as px
import streamlit as st

# --- PAGE SETUP ---
st.set_page_config(
    page_title="Personal Expense Tracker", page_icon="💰", layout="wide"
)

# --- DATABASE SETUP ---
DB_NAME = "expenses.db"


def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                month TEXT PRIMARY KEY,
                limit_amount REAL NOT NULL
            )
        """
        )
        conn.commit()


init_db()


def add_transaction(t_date, t_type, category, amount, description):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO transactions (date, type, category, amount, description)
            VALUES (?, ?, ?, ?, ?)
        """,
            (t_date, t_type, category, amount, description),
        )
        conn.commit()


def set_budget(month, limit_amount):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO budgets (month, limit_amount)
            VALUES (?, ?)
            ON CONFLICT(month) DO UPDATE SET limit_amount = excluded.limit_amount
        """,
            (month, limit_amount),
        )
        conn.commit()


def load_data():
    with sqlite3.connect(DB_NAME) as conn:
        df = pd.read_sql_query("SELECT * FROM transactions", conn)
        budgets_df = pd.read_sql_query("SELECT * FROM budgets", conn)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df["month"] = df["date"].dt.strftime("%Y-%m")
    return df, budgets_df

def clear_all_transactions():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM transactions")
        cursor.execute(
            "DELETE FROM sqlite_sequence WHERE name='transactions'"
        )  # Resets ID counter to 1
        conn.commit()


def clear_all_budgets():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM budgets")
        conn.commit()

# --- SIDEBAR: DATA ENTRY ---
st.sidebar.header("➕ Add Transaction")

with st.sidebar.form("transaction_form", clear_on_submit=True):
    t_date = st.date_input("Date", value=date.today())
    t_type = st.selectbox("Type", ["Expense", "Income"])

    categories = {
        "Expense": [
            "Food & Dining",
            "Rent & Utilities",
            "Shopping",
            "Transport",
            "Entertainment",
            "Healthcare",
            "Other",
        ],
        "Income": ["Salary", "Freelance", "Investments", "Gifts", "Other"],
    }
    category = st.selectbox("Category", categories[t_type])
    amount = st.number_input("Amount (₹)", min_value=0.01, step=50.0, format="%.2f")
    description = st.text_input("Description (Optional)")

    submitted = st.form_submit_button("Save Transaction")
    if submitted:
        add_transaction(
            t_date.strftime("%Y-%m-%d"), t_type, category, amount, description
        )
        st.sidebar.success("Transaction recorded!")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🎯 Monthly Budget Limit")
current_month_str = datetime.today().strftime("%Y-%m")
budget_input = st.sidebar.number_input(
    f"Set Expense Budget for {current_month_str} (₹)",
    min_value=0.0,
    step=500.0,
    format="%.2f",
)

if st.sidebar.button("Save Budget"):
    set_budget(current_month_str, budget_input)
    st.sidebar.success("Budget updated!")
    st.rerun()

# --- SIDEBAR: DANGER ZONE (RESET DATA) ---
st.sidebar.markdown("---")
st.sidebar.subheader("⚠️ Manage Data")

with st.sidebar.expander("Reset Options"):
    if st.button("🗑️ Clear All Transactions", type="secondary"):
        clear_all_transactions()
        st.sidebar.warning("All transactions deleted!")
        st.rerun()

    if st.button("🗑️ Reset Everything (Full Reset)", type="primary"):
        clear_all_transactions()
        clear_all_budgets()
        st.sidebar.error("All data and budgets have been wiped!")
        st.rerun()

# --- MAIN DASHBOARD ---
st.title("💰 Personal Expense Tracker")

df, budgets_df = load_data()

if df.empty:
    st.info(
        "No transactions found. Add your first income or expense using the sidebar to generate insights."
    )
    st.stop()

# --- TOP KPI METRICS ---
total_income = df[df["type"] == "Income"]["amount"].sum()
total_expenses = df[df["type"] == "Expense"]["amount"].sum()
net_savings = total_income - total_expenses
savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Income", f"₹{total_income:,.2f}")
col2.metric("Total Expenses", f"₹{total_expenses:,.2f}")
col3.metric("Net Balance", f"₹{net_savings:,.2f}")
col4.metric("Savings Rate", f"{savings_rate:.1f}%")

# --- BUDGET ALERT SYSTEM ---
current_month_expenses = df[
    (df["month"] == current_month_str) & (df["type"] == "Expense")
]["amount"].sum()

budget_row = budgets_df[budgets_df["month"] == current_month_str]
if not budget_row.empty:
    monthly_limit = budget_row["limit_amount"].values[0]
    percent_used = (
        (current_month_expenses / monthly_limit) * 100 if monthly_limit > 0 else 0
    )

    st.markdown("---")
    st.subheader(f"🔔 Budget Status for {current_month_str}")
    st.progress(min(percent_used / 100, 1.0))

    if percent_used >= 100:
        st.error(
            f"🚨 Alert: You have exceeded your budget! Spent: **₹{current_month_expenses:,.2f}** / **₹{monthly_limit:,.2f}** ({percent_used:.1f}%)"
        )
    elif percent_used >= 85:
        st.warning(
            f"⚠️ Caution: You have reached **{percent_used:.1f}%** of your monthly limit (₹{current_month_expenses:,.2f} / ₹{monthly_limit:,.2f})."
        )
    else:
        st.success(
            f"✅ On track: Spent **₹{current_month_expenses:,.2f}** of **₹{monthly_limit:,.2f}** ({percent_used:.1f}%)."
        )

# --- ANALYTICAL INSIGHTS (RESUME VALUE) ---
st.markdown("---")
st.subheader("💡 Automated Insights")

expense_df = df[df["type"] == "Expense"].copy()
if not expense_df.empty:
    monthly_cat = (
        expense_df.groupby(["month", "category"])["amount"].sum().unstack(fill_value=0)
    )
    all_months = sorted(df["month"].unique())

    if len(all_months) >= 2:
        curr_m, prev_m = all_months[-1], all_months[-2]
        insights = []

        for cat in monthly_cat.columns:
            prev_val = (
                monthly_cat.loc[prev_m, cat] if prev_m in monthly_cat.index else 0
            )
            curr_val = (
                monthly_cat.loc[curr_m, cat] if curr_m in monthly_cat.index else 0
            )

            if prev_val > 0 and curr_val > 0:
                pct_change = ((curr_val - prev_val) / prev_val) * 100
                if abs(pct_change) >= 10:
                    trend = "increased" if pct_change > 0 else "decreased"
                    insights.append(
                        f"• Your **{cat}** spending {trend} by **{abs(pct_change):.1f}%** compared to last month."
                    )

        if insights:
            for item in insights:
                st.write(item)
        else:
            st.write("Spending patterns are stable across recent months.")
    else:
        st.write("Add transactions across at least two months to view MoM trends.")

# --- VISUALIZATIONS ---
st.markdown("---")
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Expense Breakdown")
    if not expense_df.empty:
        cat_summary = (
            expense_df.groupby("category")["amount"].sum().reset_index()
        )
        fig_pie = px.pie(
            cat_summary,
            values="amount",
            names="category",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No expense data recorded yet.")

with col_right:
    st.subheader("Monthly Income vs. Expense")
    monthly_summary = (
        df.groupby(["month", "type"])["amount"].sum().reset_index()
    )
    fig_bar = px.bar(
        monthly_summary,
        x="month",
        y="amount",
        color="type",
        barmode="group",
        color_discrete_map={"Income": "#2ecc71", "Expense": "#e74c3c"},
    )
    fig_bar.update_layout(
        xaxis_title="Month", yaxis_title="Amount (₹)", legend_title="Type"
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# Spending Trend Over Time
st.subheader("Cumulative Spending Over Time")
expense_timeline = (
    expense_df.sort_values("date").groupby("date")["amount"].sum().reset_index()
)
if not expense_timeline.empty:
    fig_line = px.line(
        expense_timeline,
        x="date",
        y="amount",
        markers=True,
        line_shape="spline",
        title="Daily Expense Trends",
    )
    fig_line.update_layout(xaxis_title="Date", yaxis_title="Daily Expense (₹)")
    st.plotly_chart(fig_line, use_container_width=True)

# --- RECENT TRANSACTIONS TABLE ---
st.markdown("---")
st.subheader("Recent Transactions")
st.dataframe(
    df.sort_values("date", ascending=False)[
        ["date", "type", "category", "amount", "description"]
    ].style.format({"amount": "₹{:,.2f}", "date": lambda x: x.strftime("%Y-%m-%d")}),
    use_container_width=True,
)