import streamlit as st
import pandas as pd
import pyodbc
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import time
from streamlit_option_menu import option_menu
from streamlit_cookies_manager import EncryptedCookieManager
import requests
st.set_page_config(
    page_title="Finance App",
    page_icon="💰",
    layout="wide"
)


cookies = EncryptedCookieManager(
    prefix="financeapp",
    password="super_secret_key_123"  # ต้องตรงกับใน app.py
)
if not cookies.ready():
    st.stop()
    
if "logged_in" not in st.session_state:
    st.session_state.logged_in = cookies.get("logged_in") == "True"
    st.session_state.username = cookies.get("username") if cookies.get("username") else ""


if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.warning("❌ กรุณา login ก่อนเข้าใช้งาน")
    st.stop()  # หยุด render หน้า
current_page = "AP ERP"

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
database = "platform_GP"



# -----------------------------
# Connect DB
# -----------------------------
def get_connection():
    conn = pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE={database};UID={sql_username};PWD={sql_password}"
    )
    return conn

st.title("ข้อมูล GP")



# -----------------------------
# Load AP_upload
# -----------------------------
def load_gp():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM GP", conn)
    conn.close()
    st.session_state["GP"] = df
    return df


# -----------------------------
# Load data if not in session_state
# -----------------------------
if "GP" not in st.session_state:
    gp_df = load_gp()
else:
    gp_df = st.session_state["GP"]
    
    
st.subheader("Data GP (แก้ไขได้)")

# ตารางบน (แก้ไขได้)
edited_df = st.data_editor(
    gp_df,
    num_rows="dynamic",
    use_container_width=True,
    key="gp_editor"
)

def save_to_sql(df, incremental_col="ID"):
    """Saves the dataframe back to the SQL database by overwriting existing data.
    Supports incremental column by enabling IDENTITY_INSERT."""
    
    conn = get_connection()
    cursor = conn.cursor()
    
    table_name = "GP"
    
    try:
        # ลบข้อมูลเก่า
        cursor.execute(f"DELETE FROM {table_name}")
        
        # เตรียม column ทั้งหมด (รวม ID)
        cols = df.columns.tolist()
        cols_str = ", ".join([f"[{col}]" for col in cols])
        placeholders = ", ".join(["?"] * len(cols))
        sql_insert = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"
        
        # เตรียม rows
        rows_to_insert = [tuple(row[col] for col in cols) for _, row in df.iterrows()]
        
        # เปิด IDENTITY_INSERT ชั่วคราว
        cursor.execute(f"SET IDENTITY_INSERT {table_name} ON")
        cursor.executemany(sql_insert, rows_to_insert)
        cursor.execute(f"SET IDENTITY_INSERT {table_name} OFF")
        
        conn.commit()
        st.success("✅ Changes saved successfully!")
        st.session_state["data_saved"] = True

    except pyodbc.Error as ex:
        st.error(f"❌ Error saving data: {ex}")
        conn.rollback()
    finally:
        conn.close()




# Add a button to trigger the save operation
if st.button("💾 Save Changes to Database"):
    save_to_sql(edited_df)
# -----------------------------
# Save back to DB
# -----------------------------

# -----------------------------
# ตารางล่าง แสดงผลลัพธ์ที่แก้ไขแล้ว + %
# -----------------------------
st.subheader("ผลลัพธ์หลังแก้ไข (พร้อม %)")

# ใช้ edited_df ไม่ใช่ gp_df
gp1 = edited_df.copy()

# แปลง GP ให้เป็น float (กัน error เวลา %)
gp1["GP"] = gp1["GP"].astype(float)

# เพิ่ม column %
gp1["GP (%)"] = gp1["GP"] * 100
gp1["GP (%)"] = gp1["GP (%)"].apply(lambda x: f"{x:.2f}%")

# เลือก column ที่จะแสดง
gp1 = gp1[["Third_party", "ITem_fees", "GP", "GP (%)"]]

st.dataframe(gp1, use_container_width=True)