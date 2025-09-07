import streamlit as st
import pandas as pd
import pyodbc
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import time
import plotly.express as px
from streamlit_cookies_manager import EncryptedCookieManager
from datetime import datetime
import altair as alt

st.set_page_config(
    page_title="Finance App",
    page_icon="💰",
    layout="wide"
)
# -----------------------------
# Cookie Manager (ต้องใช้ prefix/password เดียวกับ app.py)
# -----------------------------
cookies = EncryptedCookieManager(
    prefix="financeapp",
    password="super_secret_key_123"  # ต้องตรงกับใน app.py
)
if not cookies.ready():
    st.stop()

# -----------------------------
# โหลดสถานะจาก cookie เข้ามาใน session_state
# -----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = cookies.get("logged_in") == "True"
    st.session_state.username = cookies.get("username") if cookies.get("username") else ""

# -----------------------------
# เช็ค login ก่อนเข้า page
# -----------------------------
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.warning("❌ กรุณา login ก่อนเข้าใช้งาน")
    st.stop()  # หยุด render หน้า

# -----------------------------
# เนื้อหาหลังจาก login สำเร็จ
# -----------------------------
st.title("📊 Dashboard")
st.write(f"Welcome {st.session_state.username} to the Dashboard!")


# -----------------------------
# Azure Key Vault
# -----------------------------
keyVaultName = "financeproject"
KVUri = f"https://{keyVaultName}.vault.azure.net/"

credential = DefaultAzureCredential()
client = SecretClient(vault_url=KVUri, credential=credential)

sql_username = client.get_secret("SQL-Username").value
sql_password = client.get_secret("SQL-Password").value

server = "assetcontrol.database.windows.net"
database = "finance_project"

def get_connection():
    conn = pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE={database};UID={sql_username};PWD={sql_password}"
    )
    return conn


def load_ap_erp():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM Cash_AP_Upload", conn)
    conn.close()
    st.session_state["AP_ERP"] = df
    return df

# -----------------------------
# Load AP_EXCEL
# -----------------------------
def load_ap_excel():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM Cash_AP_Upload", conn)
    conn.close()
    st.session_state["AP_EXCEL"] = df
    return df


if "AP_ERP" not in st.session_state:
    ap_df = load_ap_erp()
else:
    ap_df = st.session_state["AP_ERP"]
    
if "AP_EXCEL" not in st.session_state:
    ap_df_excel = load_ap_excel()
else:
    ap_df_excel = st.session_state["AP_EXCEL"]

ap_sum = ap_df.groupby(["Vendor_No","Vendor_Name","original_duedate","Status_"], as_index=False)["amount"].sum().rename(columns={"amount": "amount_AP"})
ap_sum_excel = ap_df_excel.groupby(["Vendor_No","Vendor_Name","original_duedate","Status_"], as_index=False)["amount"].sum().rename(columns={"amount": "amount_excel"})

ap_sum["original_duedate"] = pd.to_datetime(ap_sum["original_duedate"], format="%Y-%m-%d", errors="coerce")
ap_sum_excel["original_duedate"] = pd.to_datetime(ap_sum_excel["original_duedate"], format="%Y-%m-%d", errors="coerce")
# -----------------------------
# Merge ทั้งสอง table ด้วย DOC_ID + ITEM_Description
# -----------------------------
merged_df = pd.merge(ap_sum, ap_sum_excel, on=["Vendor_No","Vendor_Name","original_duedate","Status_"], how="outer")

# -----------------------------
# เพิ่ม column รวมทั้งสอง
# -----------------------------
merged_df["Total_Amount"] = merged_df["amount_AP"]+ merged_df["amount_excel"]
# -----------------------------
# เลือกเฉพาะคอลัมน์ที่ต้องการแสดง
# -----------------------------
# -----------------------------
# แปลง DueWeek → w{week}-{month}
# -----------------------------
def week_in_month(d):
    if pd.isna(d):
        return None
    week_num = (d.day - 1) // 7 + 1
    return f"w{week_num}-{d.strftime('%m')}"

merged_df["DueWeek"] = merged_df["original_duedate"].apply(week_in_month)
st.dataframe(merged_df)


# -----------------------------------
# AR
# -----------------------------------
def load_ar_erp():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM Cash_AR_Upload", conn)
    conn.close()
    st.session_state["AR_ERP"] = df
    return df


def load_ar_excel():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM Cash_AR_Upload", conn)
    conn.close()
    st.session_state["AR_EXCEL"] = df
    return df

if "AR_ERP" not in st.session_state:
    ar_df = load_ar_erp()
else:
    ar_df = st.session_state["AR_ERP"]
    
if "AR_EXCEL" not in st.session_state:
    ar_df_excel = load_ar_excel()
else:
    ar_df_excel = st.session_state["AR_EXCEL"]

ar_sum = ar_df.groupby(["Customer_No","Customer_Name","original_duedate","Status_"], as_index=False)["amount"].sum().rename(columns={"amount": "amount_AR"})
ar_sum_excel = ar_df_excel.groupby(["Customer_No","Customer_Name","original_duedate","Status_"], as_index=False)["amount"].sum().rename(columns={"amount": "amount_excel"})

ar_sum["original_duedate"] = pd.to_datetime(ar_sum["original_duedate"], format="%Y-%m-%d", errors="coerce")
ar_sum_excel["original_duedate"] = pd.to_datetime(ar_sum_excel["original_duedate"], format="%Y-%m-%d", errors="coerce")
# -----------------------------
# Merge ทั้งสอง table ด้วย DOC_ID + ITEM_Description
# -----------------------------
merged_df_ar = pd.merge(ar_sum, ar_sum_excel, on=["Customer_No","Customer_Name","original_duedate","Status_"], how="outer")

# -----------------------------
# เพิ่ม column รวมทั้งสอง
# -----------------------------
merged_df_ar["Total_Amount"] = merged_df_ar["amount_AR"]+ merged_df_ar["amount_excel"]
# -----------------------------
# เลือกเฉพาะคอลัมน์ที่ต้องการแสดง
# -----------------------------
# -----------------------------
# แปลง DueWeek → w{week}-{month}
# -----------------------------
def week_in_month(d):
    if pd.isna(d):
        return None
    week_num = (d.day - 1) // 7 + 1
    return f"w{week_num}-{d.strftime('%m')}"

merged_df_ar["DueWeek"] = merged_df_ar["original_duedate"].apply(week_in_month)

st.dataframe(merged_df_ar)

# ปุ่ม Logout
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    cookies["logged_in"] = "False"
    cookies["username"] = ""
    cookies.save()
    st.switch_page("Login.py")

# AP processing
ap_df = load_ap_erp()
ap_df_excel = load_ap_excel()
ap_sum = ap_df.groupby(["Vendor_No", "Vendor_Name", "original_duedate", "Status_"], as_index=False)["amount"].sum().rename(columns={"amount": "amount_AP"})
ap_sum_excel = ap_df_excel.groupby(["Vendor_No", "Vendor_Name", "original_duedate", "Status_"], as_index=False)["amount"].sum().rename(columns={"amount": "amount_excel"})
ap_sum["original_duedate"] = pd.to_datetime(ap_sum["original_duedate"], format="%Y-%m-%d", errors="coerce")
ap_sum_excel["original_duedate"] = pd.to_datetime(ap_sum_excel["original_duedate"], format="%Y-%m-%d", errors="coerce")
merged_df = pd.merge(ap_sum, ap_sum_excel, on=["Vendor_No", "Vendor_Name", "original_duedate", "Status_"], how="outer")
merged_df["Total_Amount"] = merged_df["amount_AP"] + merged_df["amount_excel"]
merged_df["DueWeek"] = merged_df["original_duedate"].apply(week_in_month)
merged_df["Category"] = "AP"

# AR processing
ar_df = load_ar_erp()
ar_df_excel = load_ar_excel()
ar_sum = ar_df.groupby(["Customer_No", "Customer_Name", "original_duedate", "Status_"], as_index=False)["amount"].sum().rename(columns={"amount": "amount_AR"})
ar_sum_excel = ar_df_excel.groupby(["Customer_No", "Customer_Name", "original_duedate", "Status_"], as_index=False)["amount"].sum().rename(columns={"amount": "amount_excel"})
ar_sum["original_duedate"] = pd.to_datetime(ar_sum["original_duedate"], format="%Y-%m-%d", errors="coerce")
ar_sum_excel["original_duedate"] = pd.to_datetime(ar_sum_excel["original_duedate"], format="%Y-%m-%d", errors="coerce")
merged_df_ar = pd.merge(ar_sum, ar_sum_excel, on=["Customer_No", "Customer_Name", "original_duedate", "Status_"], how="outer")
merged_df_ar["Total_Amount"] = merged_df_ar["amount_AR"] + merged_df_ar["amount_excel"]
merged_df_ar["DueWeek"] = merged_df_ar["original_duedate"].apply(week_in_month)
merged_df_ar["Category"] = "AR"

# Combine and aggregate
final_df = pd.concat([merged_df, merged_df_ar])
plot_df = final_df.groupby(["DueWeek", "Category"])["Total_Amount"].sum().reset_index()

# Sort the DueWeek for correct order on the chart
plot_df["sort_order"] = plot_df["DueWeek"].str.extract('w(\d+)').astype(int)
plot_df = plot_df.sort_values(by="sort_order")

# Pivot the table to have separate columns for AR and AP amounts for line chart
pivot_df = plot_df.pivot_table(index='DueWeek', columns='Category', values='Total_Amount').reset_index()
pivot_df['Difference'] = pivot_df['AR'] - pivot_df['AP']


# Calculate the total AR amount
total_ar = merged_df_ar["Total_Amount"].sum()
total_ap = merged_df["Total_Amount"].sum()
total_cash = total_ar - total_ap
# --- สร้าง Layout ของ Streamlit ---
st.title("Financial Overview Dashboard")

# สร้าง 3 คอลัมน์
col1, col2, col3 = st.columns(3)

# คอลัมน์ที่ 1: แสดงยอดรวม AR ในรูปแบบ Box Chart (st.metric)
with col1:
    st.metric(label="Cash RReceived", value=f"{total_ar:,.2f}")

# คอลัมน์ที่ 2 และ 3 ยังว่างเปล่า รอรับคำสั่งเพิ่มเติม
with col2:
    st.metric(label="Cash Payment", value=f"{total_ap:,.2f}")
    st.write("---")

with col3:
    st.metric(label="Total Cash On Hand", value=f"{total_cash:,.2f}")
    st.write("---")

# --- สร้างและแสดงผลกราฟใน Streamlit ---
st.title("Total AR & AP and Difference by Week")

# 1. สร้างกราฟแท่ง
bar_chart = alt.Chart(plot_df).mark_bar().encode(
    x=alt.X('DueWeek:N', title='Due Week'),
    xOffset=alt.XOffset('Category:N', title='Category'),
    y=alt.Y('Total_Amount:Q', title='Total Amount'),
    color=alt.Color('Category:N', title='Category'),
    tooltip=['DueWeek', 'Category', 'Total_Amount']
)

# 2. สร้างกราฟเส้น
line_chart = alt.Chart(pivot_df).mark_line(point=True, color='red').encode(
    x=alt.X('DueWeek:N', title='Due Week'),
    y=alt.Y('Difference:Q', title='AR - AP Difference'),
    tooltip=['DueWeek', 'Difference']
)

# 3. รวมกราฟทั้งสองเข้าด้วยกัน
combined_chart = alt.layer(bar_chart, line_chart).resolve_scale(
    y='independent'  # แยกแกน Y ของแต่ละกราฟเพื่อให้แสดงผลได้ถูกต้อง
).properties(
    title='Combined AR & AP Bar Chart and AR-AP Line Chart'
).interactive()

st.altair_chart(combined_chart, use_container_width=True)

# --- สร้าง Layout ของ Streamlit ---
st.title("Percent Status")

col1, col2 = st.columns(2)

# --- AR Donut Chart ---
with col1:
    st.subheader("AR Status Distribution")
    
    # Calculate AR status percentages
    ar_status_counts = ar_df.groupby('Status_').size().reset_index(name='count')
    total_ar_count = ar_df.shape[0]
    if total_ar_count > 0:
        ar_status_counts['percentage'] = (ar_status_counts['count'] / total_ar_count) * 100
    else:
        ar_status_counts['percentage'] = 0

    # Create and display AR donut chart
    ar_donut_chart = px.pie(
        ar_status_counts,
        names='Status_',
        values='percentage',
        hole=0.4
    )
    ar_donut_chart.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(ar_donut_chart, use_container_width=True)

# --- AP Donut Chart ---
with col2:
    st.subheader("AP Status Distribution")

    # Calculate AP status percentages
    ap_status_counts = ap_df.groupby('Status_').size().reset_index(name='count')
    total_ap_count = ap_df.shape[0]
    if total_ap_count > 0:
        ap_status_counts['percentage'] = (ap_status_counts['count'] / total_ap_count) * 100
    else:
        ap_status_counts['percentage'] = 0

    # Create and display AP donut chart
    ap_donut_chart = px.pie(
        ap_status_counts,
        names='Status_',
        values='percentage',
        hole=0.4
    )
    ap_donut_chart.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(ap_donut_chart, use_container_width=True)

