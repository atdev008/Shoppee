import streamlit as st
import pyodbc
import bcrypt
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from streamlit_cookies_manager import EncryptedCookieManager 
from datetime import datetime

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(
    page_title="Finance App",
    page_icon="💰",
    layout="wide"
)

# -----------------------------
# Cookie Manager
# -----------------------------
cookies = EncryptedCookieManager(
    prefix="financeapp",
    password="super_secret_key_123"
)
if not cookies.ready():
    st.stop()

# -----------------------------
# Azure Key Vault
# -----------------------------
keyVaultName = "financeproject"
KVUri = f"https://financeproject.vault.azure.net/"
credential = DefaultAzureCredential()
client = SecretClient(vault_url=KVUri, credential=credential)

username = client.get_secret("SQL-Username").value
password = client.get_secret("SQL-Password").value

server = "assetcontrol.database.windows.net"
database = "finance_project"

# -----------------------------
# Connect Azure SQL
# -----------------------------
def get_connection():
    conn = pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE={database};UID={username};PWD={password}"
    )
    return conn

# -----------------------------
# Database Functions
# -----------------------------
def create_user(user_id, user_pass, user_name, role_value):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        hashed = bcrypt.hashpw(user_pass.encode('utf-8'), bcrypt.gensalt())
        hashed_str = hashed.decode('utf-8')
        created_at = datetime.now()
        cursor.execute(
            "INSERT INTO User_App (user_ID, user_pass, user_name, Role_user, Status_user, Created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, hashed_str, user_name, role_value, 1, created_at)
        )
        conn.commit()

        st.session_state.username = user_id
        st.success("✅ Signup successful! Redirecting...")

        st.session_state.mode = "login"
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error: {e}")
    finally:
        cursor.close()
        conn.close()
        
def verify_user(user_id, user_pass):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_pass, Status_user, Role_user, user_name FROM User_App WHERE user_ID=?", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if row:
        stored_hash, Status_user, role, user_name = row
        stored_hash = stored_hash.encode('utf-8') if isinstance(stored_hash, str) else stored_hash

        if Status_user == 1:  # 1 = ไม่อนุมัติ
            return False, "User not approved yet ❌", None
        
        if bcrypt.checkpw(user_pass.encode('utf-8'), stored_hash):
            return True, "Login successful ✅", role
    
    return False, "Invalid user ID or password ❌", None
# -----------------------------
# Session State Init (with cookie)
# -----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = cookies.get("logged_in") == "True"
    st.session_state.username = cookies.get("username") if cookies.get("username") else ""
    st.session_state.role = int(cookies.get("role")) if cookies.get("role") else 0
if "mode" not in st.session_state:
    st.session_state.mode = "login"

if not st.session_state.logged_in:
    st.markdown(
        """
        <style>
        .css-1d391kg {display: none !important;}
        </style>
        """,
        unsafe_allow_html=True
    )

# -----------------------------
# Forms
# -----------------------------
def login_form():
    st.title("🔑 Login Page")
    user_id = st.text_input("User ID")
    user_pass = st.text_input("Password", type="password")

    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Login", use_container_width=True):
            valid, msg, role = verify_user(user_id, user_pass)
            if valid:
                st.session_state.logged_in = True
                st.session_state.username = user_id
                st.session_state.role = role

                # save cookie
                cookies["logged_in"] = "True"
                cookies["username"] = user_id
                cookies["role"] = str(role)
                cookies.save()

                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    with col2:
        if st.button("Signup", use_container_width=True):
            st.session_state.mode = "signup"
            st.rerun()

def signup_form():
    st.title("📝 Signup Page")
    user_id = st.text_input("User ID")
    user_pass = st.text_input("New Password", type="password")
    user_name = st.text_input("User Name")

    role_options = {" ": 0,"แผนกการเงิน": 1, "แผนกวางแผนการเงิน": 2, "แผนกอื่นๆ": 3}
    role_name = st.selectbox("Role", list(role_options.keys()))
    role_value = role_options[role_name]

    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Create Account", use_container_width=True):
            if user_id and user_pass and user_name:
                create_user(user_id, user_pass, user_name, role_value)
            else:
                st.error("Please fill all fields.")
    with col2:
        if st.button("Back to Login", use_container_width=True):
            st.session_state.mode = "login"
            st.rerun()

# -----------------------------
# Main
# -----------------------------
if st.session_state.logged_in:
    role = st.session_state.role
    st.success(f"Welcome, {st.session_state.username} 🎉 | Role: {role}")

    # Dashboard / หน้าอื่น ๆ ตาม role
    if role == 1:  # แผนการเงิน
        st.write("คุณเป็น แผนการเงิน: ทำได้ทุกอย่าง ✅")
    elif role == 2:  # แผนกวางแผนการเงิน
        st.write("คุณเป็น Uแผนกวางแผนการเงิน: ดูได้อย่างเดียว 👀")
    elif role == 3:  # แผนกอื่นๆ
        st.write("คุณเป็น แผนกอื่นๆ: วางแผนการเงิน 💰")

    st.switch_page("pages/0_📊Dashboard.py")

    # ปุ่ม logout
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.role = 0
        cookies["logged_in"] = "False"
        cookies["username"] = ""
        cookies["role"] = ""
        cookies.save()
        st.rerun()
else:
    if st.session_state.mode == "login":
        login_form()
    else:
        signup_form()
