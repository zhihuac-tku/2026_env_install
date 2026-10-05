 # py code beginning

from __future__ import annotations

from urllib.parse import quote_plus
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from nri_code_core.utils.core_utils import session_default

DEFAULT_ENV = "iMac"
DB_NAME = "ai_ready_db"
NRI_INTRANET_HOST = "192.168.10.10"
NRI_INTRANET_DB_PORT = 5432
DB_ENVIRONMENTS = {}

def configure_database_runtime(db_name=DB_NAME, default_env=DEFAULT_ENV, intranet_host=NRI_INTRANET_HOST, intranet_port=NRI_INTRANET_DB_PORT):
    global DB_NAME, DEFAULT_ENV, NRI_INTRANET_HOST, NRI_INTRANET_DB_PORT, DB_ENVIRONMENTS
    DB_NAME=db_name; DEFAULT_ENV=default_env; NRI_INTRANET_HOST=intranet_host; NRI_INTRANET_DB_PORT=intranet_port
    DB_ENVIRONMENTS = build_db_envs(DB_NAME)
    return DB_ENVIRONMENTS

def build_db_envs(db_name: str) -> dict:
    return {
        "iMac": {
            "label": "iMac Local",
            "mode": "fixed_dsn",
            "dsn": f"postgresql+psycopg2://chihjenchen@127.0.0.1:5432/{db_name}",
        },
        "MacBook": {
            "label": "MacBook Local Docker",
            "mode": "fixed_dsn",
            "dsn": f"postgresql+psycopg2://app_admin@127.0.0.1:55436/{db_name}",
        },
        "NRI Notebook": {
            "label": "NRI Notebook Local",
            "mode": "fixed_dsn",
            "dsn": f"postgresql+psycopg2://nri:53951979@127.0.0.1:5432/{db_name}",
        },
        "NRI Intranet": {
            "label": "NRI Internal DB",
            "mode": "login",
            "host": NRI_INTRANET_HOST,
            "port": NRI_INTRANET_DB_PORT,
            "database": db_name,
        },
    }

def build_login_dsn(db_user, db_password, db_host, db_port, db_name):
    safe_user = quote_plus(str(db_user))
    safe_password = quote_plus(str(db_password))

    return (
        f"postgresql+psycopg2://"
        f"{safe_user}:{safe_password}"
        f"@{db_host}:{db_port}/{db_name}"
    )

def select_database_sidebar():
    st.sidebar.header("⚙️ Database")

    env_options = list(DB_ENVIRONMENTS.keys())

    session_default("db_environment", DEFAULT_ENV)

    env = st.sidebar.selectbox(
        "Environment",
        env_options,
        key="db_environment",
    )

    cfg = DB_ENVIRONMENTS[env]

    with st.sidebar.expander("Database connection detail", expanded=False):
        st.caption(cfg["label"])

        if cfg.get("mode") == "login":
            db_host = st.text_input(
                "DB Host",
                value=cfg["host"],
                key=f"db_host_{env}",
            )

            db_port = st.number_input(
                "DB Port",
                value=int(cfg["port"]),
                step=1,
                key=f"db_port_{env}",
            )
            db_user = st.text_input(
                "DB Username",
                key=f"db_user_{env}",
            )

            db_password = st.text_input(
                "DB Password",
                type="password",
                key=f"db_password_{env}",
            )

            db_name = cfg["database"]

            if not db_user or not db_password:
                st.warning("Please enter DB username and password.")
                st.stop()

            dsn = build_login_dsn(
                db_user=db_user,
                db_password=db_password,
                db_host=db_host,
                db_port=db_port,
                db_name=db_name,
            )

        else:
            dsn_key = f"db_dsn_{env}"
            if not st.session_state.get(dsn_key):
                st.session_state[dsn_key] = cfg["dsn"]
            dsn = st.text_input(
                "Postgres DSN",
                key=dsn_key,
                help="postgresql+psycopg2://user@host:port/dbname",
            )
        db_session_box = st.empty()

    return env, dsn, db_session_box

def get_engine(dsn):
    return create_engine(
        dsn,
        pool_pre_ping=True,
        future=True
    )

def show_database_session_sidebar(
    box,
    engine,
    current_db,
    current_db_user,
    password_expiry,
):
    with box.container():
        st.markdown("---")
        st.markdown("### 🔐 DB Session")

        st.success(
            f"""
**Database:** `{current_db}`
**DB User:** `{current_db_user}`
**Password Valid Until:** `{password_expiry if password_expiry else "No expiry"}`
"""
        )

        st.markdown("### 🔑 Change DB Password")

        new_pw = st.text_input(
            "New Password",
            type="password",
            key="new_db_password_self",
        )

        confirm_pw = st.text_input(
            "Confirm New Password",
            type="password",
            key="confirm_db_password_self",
        )

        if st.button("Update DB Password", use_container_width=True):
            if not new_pw:
                st.error("Please enter a new password.")
            elif new_pw != confirm_pw:
                st.error("Passwords do not match.")
            elif len(new_pw) < 8:
                st.error("Password must be at least 8 characters.")
            elif new_pw.strip().lower() == current_db_user.strip().lower():
                st.error("Password cannot be the same as your DB user ID.")
            else:
                valid_until = change_own_db_password(engine, new_pw)
                st.success(f"Password updated. Valid until {valid_until}. Please login again.")
                st.stop()

def verify_database(engine):
    with engine.connect() as conn:
        current_db = conn.execute(
            text("SELECT current_database()")
        ).scalar()

    if current_db != DB_NAME:
        raise RuntimeError(
            f"Expected database={DB_NAME}, "
            f"but connected to {current_db}"
        )

    return current_db

def get_current_db_user(engine):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT current_user")
        ).scalar()

def get_current_user_password_expiry(engine):
    with engine.connect() as conn:
        return conn.execute(
            text("""
                SELECT rolvaliduntil
                FROM pg_roles
                WHERE rolname = current_user
            """)
        ).scalar()

def next_quarter_end():
    today = pd.Timestamp.now().normalize()
    q = ((today.month - 1) // 3) + 1

    if q == 1:
        return pd.Timestamp(today.year, 6, 30, 23, 59, 59)
    elif q == 2:
        return pd.Timestamp(today.year, 9, 30, 23, 59, 59)
    elif q == 3:
        return pd.Timestamp(today.year, 12, 31, 23, 59, 59)
    else:
        return pd.Timestamp(today.year + 1, 3, 31, 23, 59, 59)

def change_own_db_password(engine, new_password):
    valid_until = next_quarter_end().strftime("%Y-%m-%d %H:%M:%S")

    with engine.begin() as conn:
        conn.execute(
            text("""
                ALTER ROLE CURRENT_USER
                PASSWORD :new_password
                VALID UNTIL :valid_until
            """),
            {
                "new_password": new_password,
                "valid_until": valid_until,
            },
        )

    return valid_until

