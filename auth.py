"""Simple login system. Passwords are stored as salted hashes in data/users.json."""
import hashlib
import hmac
import json
import os
import re
from pathlib import Path

import streamlit as st

USERS_FILE = Path(__file__).parent / "data" / "users.json"

LOGIN_CSS = """
<style>
.stApp {background: linear-gradient(135deg,#1e1b4b 0%,#4F46E5 55%,#06B6D4 100%);}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display: none;}
.login-head {text-align: center; color: white; margin: 2rem 0 1rem;}
.login-head .logo {font-size: 3rem;}
.login-head h1 {color: white; margin: 0; font-size: 2rem;}
.login-head p {opacity: .85; margin: .3rem 0 0;}
[data-testid="stTabs"], [data-testid="stCaptionContainer"] {
    background: white; border-radius: 16px; padding: 1rem 1.2rem;
    box-shadow: 0 10px 30px rgba(0,0,0,.25);}
[data-testid="stCaptionContainer"] {margin-top: .8rem; text-align: center;}
</style>
"""


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()


def _make_user(name, password):
    salt = os.urandom(16).hex()
    return {"name": name, "salt": salt, "hash": _hash(password, salt)}


def save_users(users):
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2))


def load_users():
    """Load users; create the demo accounts if the file is missing or broken."""
    try:
        return json.loads(USERS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        users = {
            "admin": _make_user("Admin", "admin123"),
            "demo": _make_user("Demo User", "demo123"),
        }
        save_users(users)
        return users


def check_login(username, password):
    user = load_users().get(username.strip().lower())
    if not user:
        return None
    if hmac.compare_digest(_hash(password, user["salt"]), user["hash"]):
        return user["name"]
    return None


def register(name, username, password, confirm):
    username = username.strip().lower()
    if not name.strip() or not username or not password:
        return False, "Please fill in all fields."
    if not re.fullmatch(r"[a-z0-9_]{3,20}", username):
        return False, "Username: 3-20 letters, numbers or underscores."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if password != confirm:
        return False, "Passwords do not match."
    users = load_users()
    if username in users:
        return False, "That username is already taken."
    users[username] = _make_user(name.strip(), password)
    save_users(users)
    return True, "Account created! You can now sign in."


def login_page():
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        st.markdown(
            '<div class="login-head"><div class="logo">🛒</div><h1>Retail Analytics</h1>'
            "<p>Sign in to view your sales dashboard</p></div>",
            unsafe_allow_html=True,
        )
        tab_in, tab_up = st.tabs(["🔐 Login", "📝 Sign up"])
        with tab_in:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                go = st.form_submit_button("Sign in", width="stretch")
            if go:
                name = check_login(username, password)
                if name:
                    st.session_state["user"] = {"username": username.strip().lower(), "name": name}
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")
        with tab_up:
            with st.form("signup_form"):
                new_name = st.text_input("Full name")
                new_user = st.text_input("Choose a username")
                new_pass = st.text_input("Password", type="password")
                new_conf = st.text_input("Confirm password", type="password")
                create = st.form_submit_button("Create account", width="stretch")
            if create:
                ok, msg = register(new_name, new_user, new_pass, new_conf)
                (st.success if ok else st.error)(msg)
        st.caption("Demo account: admin / admin123")


def require_login():
    """Call at the top of app.py. Shows the login page and stops until signed in."""
    if "user" not in st.session_state:
        login_page()
        st.stop()


def sidebar_user():
    """Show the signed-in user and a logout button in the sidebar."""
    st.sidebar.markdown(f"👤 **{st.session_state['user']['name']}**")
    if st.sidebar.button("🚪 Logout"):
        del st.session_state["user"]
        st.rerun()
