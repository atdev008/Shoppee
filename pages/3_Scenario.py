import streamlit as st
import pandas as pd
import pyodbc
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from streamlit_cookies_manager import EncryptedCookieManager

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

# Normalize column names
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

# Unique fee types and shops
fee_types = gp_df["ITem_fees"].unique().tolist()
shops = gp_df["Third_party"].unique().tolist()

# -----------------------------
# Input price
# -----------------------------
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
] + list(fee_types)  # append fee types dynamically

df = pd.DataFrame(index=rows, columns=shops, dtype=float)

for shop in shops:
    df[shop] = [float(price), 0.0, float(price), 0.0, 0.0, 0.0, 0.0] + [0.0]*len(fee_types)

# -----------------------------
# Update function
# -----------------------------
def update_all(df, fees):
    for shop in df.columns:
        shop_norm = shop.strip()
        price_val = float(df.loc["ราคาขาย (รวม Vat7%)", shop])
        discount_val = float(df.loc["ส่วนลดจากร้านค้า", shop])
        code_discount = float(df.loc["ใช้โค้ดส่วนลด", shop])
        buyer_ship = float(df.loc["ค่าจัดส่งที่ชำระโดยผู้ซื้อ", shop])
        actual_ship = float(df.loc["ค่าส่งตามจริง (ขนส่ง)", shop])
        
        # ราคาหลังหักส่วนลด
        net_price = price_val - discount_val
        df.loc["ราคาขายหลังหักส่วนลด", shop] = net_price
        
        # ยอดผู้ซื้อ
        buyer_amount = net_price - code_discount - buyer_ship - actual_ship
        df.loc["ยอดชำระผู้ซื้อ", shop] = buyer_amount
        
        # คำนวณ Fee ทุกชนิด
        for fee_type in fee_types:
            fee_type_norm = fee_type.strip()
            rate = fees.get(shop_norm, {}).get(fee_type_norm, 0)
            df.loc[fee_type, shop] = round(buyer_amount * rate, 2)
    return df

# Initial calculation
df = update_all(df, fees)

# -----------------------------
# Streamlit editable table
# -----------------------------
edited_df = st.data_editor(
    df,
    num_rows="dynamic",
    use_container_width=True,
    key="df_editor"
)

# Live update after editing
if edited_df is not None:
    edited_df = update_all(edited_df, fees)
    st.dataframe(edited_df)