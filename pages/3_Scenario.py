import streamlit as st
import pandas as pd
import pyodbc
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from streamlit_cookies_manager import EncryptedCookieManager
import plotly.express as px

st.set_page_config(
    page_title="Finance App",
    page_icon="💰",
    layout="wide"
)

# -----------------------------
# Cookies & login
# -----------------------------
cookies = EncryptedCookieManager(
    prefix="financeapp",
    password="super_secret_key_123"
)
if not cookies.ready():
    st.stop()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = cookies.get("logged_in") == "True"
    st.session_state.username = cookies.get("username") or ""

if not st.session_state.logged_in:
    st.warning("❌ กรุณา login ก่อนเข้าใช้งาน")
    st.stop()

# -----------------------------
# Azure Key Vault & SQL connection
# -----------------------------
keyVaultName = "financeproject"
KVUri = f"https://{keyVaultName}.vault.azure.net/"
credential = DefaultAzureCredential()
client = SecretClient(vault_url=KVUri, credential=credential)

sql_username = client.get_secret("SQL-Username").value
sql_password = client.get_secret("SQL-Password").value

server = "assetcontrol.database.windows.net"
database = "platform_GP"

def get_connection():
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE={database};UID={sql_username};PWD={sql_password}"
    )

# -----------------------------
# Load GP from SQL
# -----------------------------
def load_gp():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM GP", conn)
    conn.close()
    st.session_state["GP1"] = df
    return df

if "GP1" not in st.session_state:
    gp_df = load_gp()
else:
    gp_df = st.session_state["GP1"]

gp_df["Third_party"] = gp_df["Third_party"].str.strip()
gp_df["ITem_fees"] = gp_df["ITem_fees"].str.strip()
gp_df["GP"] = gp_df["GP"].astype(float)

# -----------------------------
# Create fees dictionary
# -----------------------------
fees = {}
for _, row in gp_df.iterrows():
    shop = row["Third_party"]
    fee_type = row["ITem_fees"]
    rate = float(row["GP"])
    if shop not in fees:
        fees[shop] = {}
    fees[shop][fee_type] = rate

fee_types = gp_df["ITem_fees"].unique().tolist()
shops = gp_df["Third_party"].unique().tolist()

st.title("🪙 คำนวณต้นทุนและกำไรจากร้านค้าออนไลน์")
st.subheader("ปรับราคาขายและค่าธรรมเนียมต่างๆ เพื่อดูผลกระทบต่อกำไร")
st.subheader("แก้ไขได้เฉพาะที่กำหนด (ราคาขาย, ส่วนลด, ค่าส่ง)")

# -----------------------------
# Input price (4 columns)
# -----------------------------
col1, col2, col3, col4 = st.columns(4)
with col1:
    price = st.number_input("ราคาขายเริ่มต้น (รวม Vat7%)", min_value=0, value=490, step=1)

# -----------------------------
# Initialize editable DataFrame
# -----------------------------
rows = [
    "ราคาขาย (รวม Vat7%)",
    "ส่วนลดจากร้านค้า",
    "ราคาขายหลังหักส่วนลด",
    "ใช้โค้ดส่วนลด",
    "ค่าจัดส่งที่ชำระโดยผู้ซื้อ",
    "ค่าส่งตามจริง (ขนส่ง)",
    "ยอดชำระผู้ซื้อ"
] + list(fee_types) + ["ค่าธรรมเนียมรวม", "ยอดเงินบริษัทได้รับ"]

df = pd.DataFrame(index=rows, columns=shops, dtype=float)
for shop in shops:
    df[shop] = [float(price), 0.0, float(price), 0.0, 0.0, 0.0, 0.0] + [0.0]*len(fee_types) + [0.0, 0.0]

# -----------------------------
# Update function with total fee & company revenue
# -----------------------------
def update_all(df, fees):
    for shop in df.columns:
        shop_norm = shop.strip()
        price_val = float(df.loc["ราคาขาย (รวม Vat7%)", shop])
        discount_val = float(df.loc["ส่วนลดจากร้านค้า", shop])
        code_discount = float(df.loc["ใช้โค้ดส่วนลด", shop])
        buyer_ship = float(df.loc["ค่าจัดส่งที่ชำระโดยผู้ซื้อ", shop])
        actual_ship = float(df.loc["ค่าส่งตามจริง (ขนส่ง)", shop])
        
        net_price = price_val - discount_val
        df.loc["ราคาขายหลังหักส่วนลด", shop] = net_price
        
        buyer_amount = net_price - code_discount - buyer_ship - actual_ship
        df.loc["ยอดชำระผู้ซื้อ", shop] = buyer_amount
        
        for fee_type in fee_types:
            rate = fees.get(shop_norm, {}).get(fee_type, 0)
            df.loc[fee_type, shop] = round(buyer_amount * rate, 2)

        total_fee_types = [
            "ค่าคอมมิชชัน",
            "ค่าธรรมเนียมขนส่ง Shipping extra",
            "ค่าธรรมเนียมการชำระเงิน",
            "ค่าธรรมเนียม Affiliate (10%) +Vat7%"
        ]
        total_fee = sum(df.loc[ft, shop] for ft in total_fee_types if ft in df.index)
        df.loc["ค่าธรรมเนียมรวม", shop] = round(total_fee, 2)

        df.loc["ยอดเงินบริษัทได้รับ", shop] = round(buyer_amount - total_fee, 2)

    return df

df = update_all(df, fees)

# -----------------------------
# Editable rows only
# -----------------------------
editable_rows = [
    "ราคาขาย (รวม Vat7%)",
    "ส่วนลดจากร้านค้า",
    "ใช้โค้ดส่วนลด",
    "ค่าจัดส่งที่ชำระโดยผู้ซื้อ",
    "ค่าส่งตามจริง (ขนส่ง)"
]

editable_df = df.loc[editable_rows]

edited_df = st.data_editor(
    editable_df,
    num_rows="dynamic",
    use_container_width=True,
    key="df_editor_main"
)

if edited_df is not None:
    for row in editable_rows:
        df.loc[row] = edited_df.loc[row]
    df = update_all(df, fees)

# -----------------------------
# Dynamic Scenario Tabs in Sidebar
# -----------------------------
st.sidebar.subheader("⚡ Scenario")

# Init scenarios
if "scenarios" not in st.session_state:
    st.session_state.scenarios = ["Scenario A", "Scenario B"]

# Add new Scenario
new_scenario = st.sidebar.text_input("เพิ่ม Scenario ใหม่", key="add_scenario_sidebar")
if st.sidebar.button("เพิ่ม Scenario"):
    if new_scenario and new_scenario not in st.session_state.scenarios:
        st.session_state.scenarios.append(new_scenario)
        st.rerun()

# Delete Scenario
scenario_to_delete = st.sidebar.selectbox("ลบ Scenario", options=[""] + st.session_state.scenarios)
if st.sidebar.button("ลบ Scenario"):
    if scenario_to_delete:
        st.session_state.scenarios.remove(scenario_to_delete)
        st.rerun()

# -----------------------------
# Scenario Tabs with Editable Table + Donut Chart
# -----------------------------
tabs = st.tabs(st.session_state.scenarios)
scenario_dfs = {}

for i, scenario in enumerate(st.session_state.scenarios):
    with tabs[i]:
        st.subheader(f"📋 ตาราง {scenario}")
        df_s = df.copy()

        # ตัวอย่าง logic: ปรับราคาหรือส่วนลดตามชื่อ scenario
        if scenario.lower().find("ลด") >= 0:
            for shop in shops:
                df_s.loc["ส่วนลดจากร้านค้า", shop] = df_s.loc["ราคาขาย (รวม Vat7%)", shop] * 0.10
        elif scenario.lower().find("ส่งฟรี") >= 0:
            for shop in shops:
                df_s.loc["ค่าจัดส่งที่ชำระโดยผู้ซื้อ", shop] = 0

        scenario_df = update_all(df_s, fees)
        scenario_dfs[scenario] = scenario_df

        # Editable Table
        editable_scenario_df = scenario_df.loc[editable_rows]
        edited_scenario_df = st.data_editor(
            editable_scenario_df,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{scenario}"
        )
        if edited_scenario_df is not None:
            for row in editable_rows:
                scenario_df.loc[row] = edited_scenario_df.loc[row]
            scenario_df = update_all(scenario_df, fees)
            scenario_dfs[scenario] = scenario_df

        # DataFrame display
        row_height = 38
        table_height = len(scenario_df) * row_height

        st.dataframe(scenario_df, use_container_width=True, height=table_height)

        # Donut Chart
        st.subheader(f"📊 Portion% Fees VS Profit {scenario}")
        cols_chart = st.columns(3)
        for j, shop in enumerate(shops):
            col = cols_chart[j % 3]
            with col:
                labels = ["ค่าธรรมเนียมรวม", "ยอดเงินบริษัทได้รับ"]
                values = [
                    scenario_df.loc["ค่าธรรมเนียมรวม", shop],
                    scenario_df.loc["ยอดเงินบริษัทได้รับ", shop]
                ]
                fig = px.pie(
                    names=labels,
                    values=values,
                    hole=0.5,
                    title=f"{shop}",
                    color=labels,
                    color_discrete_map={
                        "ค่าธรรมเนียมรวม": "#E74C3C",       # แดง
                        "ยอดเงินบริษัทได้รับ": "#27AE60"      # เขียวเข้ม
                    }
                )

                # กำหนดกรอบสี่เหลี่ยมรอบกราฟ
                fig.update_traces(
                    marker=dict(line=dict(color='white', width=2))  # ขอบสีขาว กว้าง 2px
                )
                # ใส่ key เฉพาะสำหรับแต่ละ chart
                st.plotly_chart(fig, use_container_width=True, key=f"{scenario}_{shop}_chart")
            if (j + 1) % 3 == 0:
                cols_chart = st.columns(3)
