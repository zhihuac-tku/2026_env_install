 # py code beginning

## THE CODING PATTERN FOR NRI CODERS BEGINS HERE. ##############################

# =========================================
# 1. STANDARD LIBRARY — REQUIRED BY NRI PATTERN
# =========================================

import sys
from pathlib import Path


# =========================================
# 2. THIRD-PARTY — REQUIRED BY NRI PATTERN
# =========================================

import streamlit as st


# =========================================
# 3. NRI WORKSPACE / PLATFORM DISCOVERY
# =========================================

SCRIPT_PATH = Path(__file__).resolve()
CODE_DIR = SCRIPT_PATH.parent
ROOT = CODE_DIR.parent
PY_ROOT = ROOT.parent
WORKSPACE_ROOT = PY_ROOT.parent
PLATFORM_ROOT = WORKSPACE_ROOT / "platform"

if str(PY_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PY_ROOT),
    )

if str(PLATFORM_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PLATFORM_ROOT),
    )


# =========================================
# 4. NRI PLATFORM CORE — REQUIRED
# =========================================

from nri_code_core.ui.ui_common import (
    apply_nri_style,
    show_sidebar_branding,
)


# =========================================
# 5. APPLICATION CONFIGURATION
# =========================================

APP_NAME = "NRI Platform Launcher"
APP_CODE = "NRI_LAUNCHER"
APP_VERSION = "4.0"

APP_ICON = "🚀"
APP_TITLE = "🚀 NRI Platform"

APP_CAPTION = (
    "Central entry point to discover, launch, manage, "
    "and monitor NRI applications and platform control tools."
)


# =========================================
# 6. STREAMLIT PAGE
# =========================================

st.set_page_config(
    page_title=APP_NAME,
    page_icon=APP_ICON,
    layout="wide",
)


# =========================================
# 7. NRI PLATFORM INITIALIZATION
# =========================================

apply_nri_style()
show_sidebar_branding()


## THE END OF THE NRI CODING PATTERN ###########################################


# =============================================================================
# APPLICATION-SPECIFIC IMPORTS
# =============================================================================

import ast
import os
import socket
import subprocess
import time
import webbrowser

from urllib.request import urlopen

import httpx
import pandas as pd


# =============================================================================
# NRI CAPABILITY — AI RUNTIME
# =============================================================================

from nri_ai_core.ai_runtime import (
    configure_llm_runtime,
    select_llm_sidebar,
)


# =============================================================================
# LAUNCHER AI CONFIGURATION
# =============================================================================

DEFAULT_LLM_ENV = "Local Notebook"
DEFAULT_MODEL = "gemma4:latest"

NRI_INTRANET_HOST = "192.168.184.13"
NRI_INTRANET_LLM_PORT = 11434

ENABLE_LLM = False


# =============================================================================
# INITIALIZE NRI AI RUNTIME
# =============================================================================

configure_llm_runtime(
    default_model=DEFAULT_MODEL,
    default_env=DEFAULT_LLM_ENV,
    intranet_host=NRI_INTRANET_HOST,
    intranet_port=NRI_INTRANET_LLM_PORT,
)

if ENABLE_LLM:
    llm_cfg = select_llm_sidebar()
else:
    llm_cfg = None


# =========================================
# PATH CONFIG
# =========================================
DEFAULT_SCAN_DIR = ROOT / "code"
LOG_DIR = ROOT / "output" / "launcher_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


# =========================================
# SESSION STATE
# =========================================
if "proc" not in st.session_state:
    st.session_state.proc = {}


# =========================================
# HELPERS — PORT / PROCESS
# =========================================
def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0


def find_free_port(start: int = 8502, end: int = 8999) -> int:
    for p in range(start, end + 1):
        if not port_in_use(p):
            return p
    raise RuntimeError("No free port found.")


def normalize_host(address: str) -> str:
    if not address or address == "localhost":
        return "127.0.0.1"
    return address


# =========================================
# HELPERS — PLATFORM TAXONOMY / METADATA
# =========================================

PLATFORM_CATEGORY_ORDER = [
    "Applications",
    "Knowledge & Data",
    "AI & Agents",
    "Security & Access",
    "Operations",
]

PLATFORM_CATEGORY_INFO = {
    "Applications": {
        "icon": "🏠",
        "description": "Business, analytics, and AI applications.",
    },
    "Knowledge & Data": {
        "icon": "🗂️",
        "description": (
            "Data dictionary, metadata, knowledge base, "
            "knowledge graph, and data discovery."
        ),
    },
    "AI & Agents": {
        "icon": "🤖",
        "description": (
            "Agent management, AI tools, testing, "
            "model control, and run monitoring."
        ),
    },
    "Security & Access": {
        "icon": "🔐",
        "description": (
            "Database privileges, users, roles, "
            "permissions, and access audit."
        ),
    },
    "Operations": {
        "icon": "⚙️",
        "description": (
            "ETL, database maintenance, backup/restore, "
            "administration, and operational utilities."
        ),
    },
}


def _normalize_meta_tags(value) -> str:
    if value is None:
        return ""

    if isinstance(value, (list, tuple, set)):
        return "; ".join(
            str(v).strip()
            for v in value
            if str(v).strip()
        )

    return str(value).strip()


def _extract_launcher_meta_from_source(
    py_file: Path,
) -> dict:
    """
    Read an optional LAUNCHER_META dictionary without importing
    or executing the target application.

    Example inside a managed application:

    LAUNCHER_META = {
        "app_code": "database_dictionary",
        "app_name": "Database Dictionary",
        "category": "Knowledge & Data",
        "description": "...",
        "tags": ["database", "dictionary"],
        "run_type": "streamlit",
        "visibility": "user",
    }
    """
    try:
        source = py_file.read_text(
            encoding="utf-8",
            errors="ignore",
        )
        tree = ast.parse(
            source,
            filename=str(py_file),
        )

        for node in tree.body:
            if not isinstance(
                node,
                (ast.Assign, ast.AnnAssign),
            ):
                continue

            target_names = []

            if isinstance(node, ast.Assign):
                target_names = [
                    target.id
                    for target in node.targets
                    if isinstance(target, ast.Name)
                ]
                value_node = node.value
            else:
                if isinstance(node.target, ast.Name):
                    target_names = [node.target.id]
                value_node = node.value

            if (
                "LAUNCHER_META" not in target_names
                or value_node is None
            ):
                continue

            value = ast.literal_eval(value_node)

            if isinstance(value, dict):
                return value

    except Exception:
        # Metadata is optional. A malformed or dynamic metadata
        # block must not prevent the Launcher from finding the app.
        pass

    return {}


def _fallback_platform_classification(
    py_file: Path,
) -> dict:
    """
    Classify existing NRI programs without requiring immediate
    modification of every application.

    Explicit LAUNCHER_META always overrides this fallback.
    """
    filename = py_file.name.lower()
    stem = py_file.stem.lower()
    full_path = str(py_file).lower()

    result = {
        "category": "Applications",
        "app_type": "application",
        "visibility": "user",
        "description": "",
        "tags": "",
    }

    # -------------------------------------
    # Knowledge & Data
    # -------------------------------------
    if (
        "database_dict" in stem
        or "database_dictionary" in stem
    ):
        result.update({
            "category": "Knowledge & Data",
            "app_type": "data_control",
            "visibility": "dba",
            "description": (
                "Manage database-level business semantics "
                "and AI data dictionary metadata."
            ),
            "tags": (
                "database; dictionary; metadata; "
                "knowledge; semantics"
            ),
        })
        return result

    if (
        "table_dict" in stem
        or "table_dictionary" in stem
        or "data_dictionary" in stem
    ):
        result.update({
            "category": "Knowledge & Data",
            "app_type": "data_control",
            "visibility": "dba",
            "description": (
                "Manage table and column metadata, "
                "business semantics, keys, and dictionary exports."
            ),
            "tags": (
                "table; column; dictionary; metadata; "
                "pk; fk; semantics"
            ),
        })
        return result

    if (
        "knowledge_graph" in stem
        or "kg_" in stem
        or stem.endswith("_kg")
    ):
        result.update({
            "category": "Knowledge & Data",
            "app_type": "knowledge",
            "visibility": "user",
            "tags": "knowledge graph; kg; entities; relationships",
        })
        return result

    if (
        "knowledge" in stem
        or "rag" in stem
    ):
        result.update({
            "category": "Knowledge & Data",
            "app_type": "knowledge",
            "visibility": "user",
            "tags": "knowledge; rag; documents; search",
        })
        return result

    # -------------------------------------
    # AI & Agents
    # -------------------------------------
    if (
        "agent_management" in stem
        or "agent_manager" in stem
    ):
        result.update({
            "category": "AI & Agents",
            "app_type": "agent_control",
            "visibility": "dba",
            "description": (
                "Manage Agent registry, tools, permissions, "
                "testing, and execution audit."
            ),
            "tags": "agent; pydantic ai; tools; permissions; audit",
        })
        return result

    if (
        "agent_test" in stem
        or "agent_monitor" in stem
        or "agent_run" in stem
    ):
        result.update({
            "category": "AI & Agents",
            "app_type": "agent_control",
            "visibility": "dba",
            "tags": "agent; test; monitor; runtime",
        })
        return result

    # -------------------------------------
    # Security & Access
    # -------------------------------------
    if (
        "priviledge" in stem
        or "privilege" in stem
        or "permission" in stem
        or "access_control" in stem
    ):
        result.update({
            "category": "Security & Access",
            "app_type": "security",
            "visibility": "dba",
            "description": (
                "Manage PostgreSQL users, group roles, "
                "database/schema/table privileges, and access checks."
            ),
            "tags": (
                "security; privilege; role; user; "
                "grant; revoke; access"
            ),
        })
        return result

    # -------------------------------------
    # Operations
    # -------------------------------------
    database_maintenance_names = {
        "nri_database_ma_etl.py",
        "nri_database_maintenance.py",
        "nri_database_maintenance_app.py",
    }

    if filename in database_maintenance_names or (
        "database_ma" in stem
        and "database_dict" not in stem
    ):
        result.update({
            "category": "Operations",
            "app_type": "database_maintenance",
            "visibility": "dba",
            "description": (
                "Database maintenance, backup, restore, "
                "schema export/import, and operational administration."
            ),
            "tags": (
                "database; maintenance; backup; restore; "
                "schema; administration"
            ),
        })
        return result

    operational_keywords = [
        "_etl",
        "insert_",
        "rebuild_",
        "loader_",
        "load_",
        "batch_",
        "backup",
        "restore",
        "admin",
        "maintenance",
    ]

    if any(
        keyword in stem or keyword in full_path
        for keyword in operational_keywords
    ):
        result.update({
            "category": "Operations",
            "app_type": "operation",
            "visibility": "dba",
            "tags": "etl; operation; administration",
        })
        return result

    return result


def parse_launcher_meta(py_file: Path) -> dict:
    fallback = _fallback_platform_classification(
        py_file
    )
    declared = _extract_launcher_meta_from_source(
        py_file
    )

    category = str(
        declared.get(
            "category",
            fallback["category"],
        )
    ).strip()

    if category not in PLATFORM_CATEGORY_ORDER:
        category = fallback["category"]

    meta = {
        "app_code": str(
            declared.get(
                "app_code",
                py_file.stem,
            )
        ).strip(),
        "name": str(
            declared.get(
                "app_name",
                declared.get(
                    "name",
                    py_file.stem,
                ),
            )
        ).strip(),
        "category": category,
        "app_type": str(
            declared.get(
                "app_type",
                fallback["app_type"],
            )
        ).strip(),
        "visibility": str(
            declared.get(
                "visibility",
                fallback["visibility"],
            )
        ).strip().lower(),
        "tags": _normalize_meta_tags(
            declared.get(
                "tags",
                fallback["tags"],
            )
        ),
        "description": str(
            declared.get(
                "description",
                fallback["description"],
            )
            or ""
        ).strip(),
        "run_type": str(
            declared.get(
                "run_type",
                "streamlit",
            )
        ).strip().lower(),
        "address": str(
            declared.get(
                "address",
                "127.0.0.1",
            )
        ).strip(),
        "enabled": bool(
            declared.get(
                "enabled",
                True,
            )
        ),
        "agents": declared.get(
            "agents",
            [],
        ),
        "script_path": str(py_file),
        "metadata_source": (
            "LAUNCHER_META"
            if declared
            else "fallback"
        ),
    }

    return meta


def is_admin_script(item: dict) -> bool:
    visibility = str(
        item.get(
            "visibility",
            "user",
        )
    ).lower()

    if visibility in {
        "dba",
        "admin",
        "restricted",
    }:
        return True

    return item.get("category") in {
        "Security & Access",
        "Operations",
    }


def scan_python_files(
    scan_dir: Path,
    recursive: bool = True,
) -> list[dict]:
    if not scan_dir.exists():
        return []

    files = (
        scan_dir.rglob("*.py")
        if recursive
        else scan_dir.glob("*.py")
    )

    items = []

    for f in files:
        if f.name.startswith("_"):
            continue

        if f.name == SCRIPT_PATH.name:
            continue

        meta = parse_launcher_meta(f)

        if meta.get("enabled"):
            items.append(meta)

    category_rank = {
        category: index
        for index, category
        in enumerate(PLATFORM_CATEGORY_ORDER)
    }

    return sorted(
        items,
        key=lambda x: (
            category_rank.get(
                x.get("category", ""),
                999,
            ),
            x.get("name", "").lower(),
        ),
    )


def filter_items_by_role(
    items: list[dict],
    user_mode: str,
) -> list[dict]:
    if user_mode == "DBA":
        return items

    return [
        item
        for item in items
        if str(
            item.get(
                "visibility",
                "user",
            )
        ).lower()
        not in {
            "dba",
            "admin",
            "restricted",
        }
    ]


def make_key(item: dict) -> str:
    return str(
        Path(
            item["script_path"]
        ).resolve()
    )


def is_running(key: str) -> bool:
    info = st.session_state.proc.get(key)

    if not info:
        return False

    pop = info.get("popen")

    return (
        pop is not None
        and pop.poll() is None
    )


def stop_app(key: str):
    info = st.session_state.proc.get(key)

    if not info:
        return

    pop = info.get("popen")

    if pop and pop.poll() is None:
        pop.terminate()

        try:
            pop.wait(timeout=5)
        except Exception:
            pop.kill()

    st.session_state.proc.pop(
        key,
        None,
    )


def start_app(item: dict):
    key = make_key(item)

    if is_running(key):
        st.warning(
            "This app is already running."
        )
        return

    script_path = Path(
        item["script_path"]
    ).resolve()

    run_type = item.get(
        "run_type",
        "streamlit",
    ).lower()

    address = normalize_host(
        item.get(
            "address",
            "127.0.0.1",
        )
    )

    log_path = (
        LOG_DIR
        / f"{script_path.stem}.log"
    )

    log_file = open(
        log_path,
        "a",
        buffering=1,
        encoding="utf-8",
    )

    child_port = None

    if run_type == "streamlit":
        child_port = find_free_port()

        cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(script_path),
            "--server.port",
            str(child_port),
            "--server.address",
            address,
        ]

    else:
        cmd = [
            sys.executable,
            str(script_path),
        ]

    if os.name == "nt":
        cmd_final = (
            subprocess.list2cmdline(cmd)
        )
        use_shell = True
    else:
        cmd_final = cmd
        use_shell = False

    pop = subprocess.Popen(
        cmd_final,
        shell=use_shell,
        cwd=str(script_path.parent),
        stdout=log_file,
        stderr=log_file,
        text=True,
        env=os.environ.copy(),
    )

    st.session_state.proc[key] = {
        "popen": pop,
        "log": str(log_path),
        "port": child_port,
        "address": address,
        "script_path": str(script_path),
    }

    if child_port:
        url = (
            f"http://{address}:"
            f"{child_port}"
        )

        time.sleep(1)

        try:
            urlopen(
                url,
                timeout=1,
            )
        except Exception:
            pass

    st.toast(
        f"Started: {item['name']}"
    )


def read_code(
    path: Path,
    max_chars: int = 30000,
) -> str:
    try:
        source = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
        return source[:max_chars]
    except Exception as e:
        return (
            "# Failed to read file: "
            f"{e}"
        )


def read_log(
    path: str,
    max_chars: int = 8000,
) -> str:
    try:
        source = Path(path).read_text(
            encoding="utf-8",
            errors="ignore",
        )
        return source[-max_chars:]
    except Exception:
        return ""


# =========================================
# HELPERS — LAUNCHER CLASSIFIER AGENT
# =========================================

def _ollama_openai_base_url(
    base_url: str,
) -> str:
    """
    Pydantic AI's Ollama provider uses Ollama's
    OpenAI-compatible /v1 endpoint.
    """
    clean = str(base_url or "").rstrip("/")

    if clean.endswith("/v1"):
        return clean

    return clean + "/v1"


def build_launcher_agent_model(
    llm_cfg: dict,
):
    """
    Build a Pydantic AI model from the Launcher's
    existing NRI LLM configuration.

    V1 supports:
    - Local / intranet Ollama
    - NCHC RAP through its OpenAI-compatible endpoint
    """
    if (
        not llm_cfg
        or not llm_cfg.get("enabled")
    ):
        raise RuntimeError(
            "LLM backend is disabled."
        )

    try:
        api_type = llm_cfg.get(
            "api_type",
            "ollama",
        )

        if api_type == "nchc_rap":
            from openai import AsyncOpenAI
            from pydantic_ai.models.openai import (
                OpenAIChatModel,
            )
            from pydantic_ai.providers.openai import (
                OpenAIProvider,
            )

            api_key = str(
                llm_cfg.get(
                    "api_key",
                    "",
                )
            ).strip()

            if not api_key:
                raise RuntimeError(
                    "NCHC RAP API key is required."
                )

            client = AsyncOpenAI(
                base_url=str(
                    llm_cfg["base_url"]
                ).rstrip("/"),
                api_key=api_key,
                default_headers={
                    "x-api-key": api_key,
                },
            )

            return OpenAIChatModel(
                llm_cfg["model"],
                provider=OpenAIProvider(
                    openai_client=client,
                ),
            )

        from pydantic_ai.models.ollama import (
            OllamaModel,
        )
        from pydantic_ai.providers.ollama import (
            OllamaProvider,
        )

        return OllamaModel(
            llm_cfg["model"],
            provider=OllamaProvider(
                base_url=(
                    _ollama_openai_base_url(
                        llm_cfg["base_url"]
                    )
                ),
            ),
        )

    except ImportError as e:
        raise RuntimeError(
            "Pydantic AI is not installed in the "
            "Python environment running this Launcher. "
            "Install it with: "
            'pip install "pydantic-ai-slim[openai]"'
        ) from e


def build_launcher_agent_input(
    py_file: Path,
    max_chars: int = 24000,
) -> str:
    """
    V1 test input.

    Read the application source directly and send a bounded
    amount of source code to the classification Agent.

    Later this can be replaced by a smarter code summarizer,
    but V1 intentionally stays simple.
    """
    source = py_file.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    clipped = source[:max_chars]

    return f"""
NRI APPLICATION TO CLASSIFY

FILE NAME:
{py_file.name}

FILE PATH:
{py_file}

SOURCE CODE:
------------------------------
{clipped}
------------------------------

Classify this application using the NRI Platform taxonomy.
Base the answer only on evidence visible in the supplied code.
"""


def run_launcher_classifier(
    py_file: Path,
    llm_cfg: dict,
):
    """
    Run the shared LAUNCHER_CLASSIFIER Agent and return
    its validated LauncherClassification Pydantic object.
    """
    try:
        from agents.launcher_classifier_agent import (
            create_launcher_classifier_agent,
        )
    except ImportError as e:
        raise RuntimeError(
            "Cannot import the NRI Launcher Agent. "
            "Expected shared package structure:\n"
            "nri_ai_runtime/\n"
            "  __init__.py\n"
            "  agents/\n"
            "    __init__.py\n"
            "    launcher_classifier_agent.py\n"
            "  models/\n"
            "    __init__.py\n"
            "    launcher_models.py"
        ) from e

    model = build_launcher_agent_model(
        llm_cfg
    )

    agent = (
        create_launcher_classifier_agent(
            model
        )
    )

    prompt = build_launcher_agent_input(
        py_file
    )

    result = agent.run_sync(
        prompt
    )

    return result.output


def show_launcher_agent_result(
    result,
):
    """
    Display the typed Agent result.
    V1 is review-only: it does not modify source code
    or write classification metadata to PostgreSQL.
    """
    st.markdown(
        "#### 🤖 Agent Suggested Classification"
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Platform Area",
        result.category,
    )

    col2.metric(
        "Visibility",
        result.visibility.upper(),
    )

    col3.metric(
        "Confidence",
        f"{result.confidence:.0%}",
    )

    st.markdown(
        f"**Application Name:** "
        f"{result.app_name}"
    )

    st.markdown(
        f"**Application Type:** "
        f"`{result.app_type}`"
    )

    st.markdown(
        f"**Description:** "
        f"{result.description}"
    )

    if result.tags:
        st.markdown(
            "**Tags:** "
            + " ".join(
                f"`{tag}`"
                for tag in result.tags
            )
        )

    st.markdown(
        f"**Reason:** "
        f"{result.reason}"
    )



# =========================================
# SIDEBAR
# =========================================

with st.sidebar:
    st.header("Platform Launcher")

    user_mode_input = st.selectbox(
        "User Mode",
        [
            "User",
            "DBA",
        ],
        index=0,
    )

    if user_mode_input == "DBA":
        st.warning(
            "DBA mode can show Knowledge/Data control, "
            "security, ETL, admin, backup, restore, "
            "and database tools. Use only if authorized."
        )

        dba_confirm = st.checkbox(
            "I confirm I am authorized "
            "to use DBA tools."
        )

        if dba_confirm:
            user_mode = "DBA"
        else:
            user_mode = "User"
            st.info(
                "DBA mode is locked "
                "until confirmation."
            )
    else:
        user_mode = "User"

    scan_dir_text = st.text_input(
        "Python folder",
        value=str(DEFAULT_SCAN_DIR),
    )

    recursive = st.checkbox(
        "Recursive scan",
        value=True,
    )

    q = st.text_input(
        "Search",
        "",
    )

    selected_categories = st.multiselect(
        "Platform Area",
        options=PLATFORM_CATEGORY_ORDER,
        default=[],
        help=(
            "Leave empty to show all platform areas "
            "available to the current mode."
        ),
    )

    show_code = st.checkbox(
        "Show code preview",
        value=False,
    )

    if st.button(
        "🔄 Refresh",
        use_container_width=True,
    ):
        st.rerun()


# =========================================
# SCAN FILES
# =========================================
scan_dir = (
    Path(scan_dir_text)
    .expanduser()
    .resolve()
)

items_all = scan_python_files(
    scan_dir,
    recursive=recursive,
)

items = filter_items_by_role(
    items_all,
    user_mode=user_mode,
)

if selected_categories:
    items = [
        item
        for item in items
        if item.get("category")
        in selected_categories
    ]

if q.strip():
    q_lower = q.lower()

    items = [
        item
        for item in items
        if q_lower
        in item.get(
            "name",
            "",
        ).lower()
        or q_lower
        in item.get(
            "category",
            "",
        ).lower()
        or q_lower
        in item.get(
            "app_type",
            "",
        ).lower()
        or q_lower
        in item.get(
            "tags",
            "",
        ).lower()
        or q_lower
        in item.get(
            "description",
            "",
        ).lower()
        or q_lower
        in item.get(
            "script_path",
            "",
        ).lower()
    ]


# =========================================
# TOP SUMMARY
# =========================================
st.title("🚀 NRI Launcher Platform")
st.caption(
    "Central entry point to discover, launch, "
    "manage, and monitor NRI applications "
    "and platform control tools."
)

summary_cols = st.columns(
    len(PLATFORM_CATEGORY_ORDER)
)

for col, category in zip(
    summary_cols,
    PLATFORM_CATEGORY_ORDER,
):
    info = PLATFORM_CATEGORY_INFO[
        category
    ]

    count = sum(
        1
        for item in items_all
        if item.get("category")
        == category
    )

    col.metric(
        f"{info['icon']} {category}",
        f"{count:,}",
    )

# =========================================
# LAUNCHER STATUS
# =========================================

if not scan_dir.exists():
    st.warning(
        f"Folder does not exist: "
        f"{scan_dir}"
    )
    st.stop()

if not items:
    st.warning(
        "No applications are visible "
        "for the current mode/filter."
    )
    st.stop()


# =========================================
# PLATFORM APPLICATION LIST
# =========================================
st.subheader(
    f"Available modules: {len(items)}"
)

for category in PLATFORM_CATEGORY_ORDER:
    group = [
        item
        for item in items
        if item.get("category")
        == category
    ]

    if not group:
        continue

    category_info = (
        PLATFORM_CATEGORY_INFO[
            category
        ]
    )

    with st.expander(
        (
            f"{category_info['icon']} "
            f"{category} — {len(group)}"
        ),
        expanded=True,
    ):
        st.caption(
            category_info[
                "description"
            ]
        )

        for item in group:
            key = make_key(item)

            script_path = Path(
                item["script_path"]
            )

            left, right = st.columns(
                [6, 2]
            )

            with left:
                st.markdown(
                    f"### {item.get('name', script_path.stem)}"
                )

                app_type = item.get(
                    "app_type",
                    "application",
                )

                visibility = item.get(
                    "visibility",
                    "user",
                ).upper()

                st.caption(
                    f"Type: `{app_type}` | "
                    f"Access: `{visibility}` | "
                    f"Run: `{item.get('run_type', 'streamlit')}`"
                )

                if item.get(
                    "description"
                ):
                    st.write(
                        item[
                            "description"
                        ]
                    )

                if item.get(
                    "tags"
                ):
                    tags = [
                        tag.strip()
                        for tag
                        in item[
                            "tags"
                        ].replace(
                            ",",
                            ";",
                        ).split(";")
                        if tag.strip()
                    ]

                    st.write(
                        " ".join(
                            f"`{tag}`"
                            for tag in tags
                        )
                    )

                agents = item.get(
                    "agents",
                    [],
                )

                if agents:
                    if isinstance(
                        agents,
                        str,
                    ):
                        agents = [
                            agents
                        ]

                    st.caption(
                        "Managed Agents: "
                        + ", ".join(
                            str(agent)
                            for agent
                            in agents
                        )
                    )

                st.code(
                    str(script_path),
                    language="bash",
                )

                if (
                    item.get(
                        "metadata_source"
                    )
                    == "fallback"
                ):
                    st.caption(
                        "Metadata: automatic fallback "
                        "classification"
                    )

            with right:
                running = is_running(
                    key
                )

                if running:
                    st.success(
                        "Running"
                    )

                    info = (
                        st.session_state.proc.get(
                            key,
                            {},
                        )
                    )

                    if info.get(
                        "port"
                    ):
                        url = (
                            f"http://"
                            f"{info['address']}:"
                            f"{info['port']}"
                        )

                        st.link_button(
                            "🌐 Open",
                            url,
                            use_container_width=True,
                        )

                    if st.button(
                        "⏹ Stop",
                        key=f"stop_{key}",
                        use_container_width=True,
                    ):
                        stop_app(
                            key
                        )
                        st.rerun()

                else:
                    st.info(
                        "Stopped"
                    )

                    if st.button(
                        "▶️ Start",
                        key=f"start_{key}",
                        use_container_width=True,
                    ):
                        start_app(
                            item
                        )

            # ---------------------------------
            # LAUNCHER CLASSIFIER AGENT — V1
            # ---------------------------------
            agent_state_key = (
                f"launcher_agent_result_{key}"
            )

            agent_error_key = (
                f"launcher_agent_error_{key}"
            )

            with st.expander(
                "🤖 Launcher Classification Agent",
                expanded=False,
            ):
                st.caption(
                    "Ask LAUNCHER_CLASSIFIER to inspect this "
                    "Python application and suggest NRI Platform "
                    "metadata. V1 is review-only."
                )

                current_model = (
                    llm_cfg.get("model")
                    if llm_cfg
                    else None
                )

                current_env = (
                    llm_cfg.get("env")
                    if llm_cfg
                    else None
                )

                if (
                    not llm_cfg
                    or not llm_cfg.get("enabled")
                ):
                    st.warning(
                        "Select an enabled LLM backend in the "
                        "sidebar before running the Agent."
                    )
                else:
                    st.caption(
                        f"LLM: `{current_env}` / "
                        f"`{current_model}`"
                    )

                    analyze_col, clear_col = (
                        st.columns([3, 1])
                    )

                    with analyze_col:
                        if st.button(
                            "🤖 Analyze with Agent",
                            key=f"agent_analyze_{key}",
                            use_container_width=True,
                        ):
                            try:
                                st.session_state.pop(
                                    agent_error_key,
                                    None,
                                )

                                with st.spinner(
                                    "LAUNCHER_CLASSIFIER is "
                                    "analyzing the application..."
                                ):
                                    agent_result = (
                                        run_launcher_classifier(
                                            script_path,
                                            llm_cfg,
                                        )
                                    )

                                st.session_state[
                                    agent_state_key
                                ] = (
                                    agent_result.model_dump()
                                )

                                st.success(
                                    "Agent classification completed."
                                )

                            except Exception as e:
                                st.session_state[
                                    agent_error_key
                                ] = str(e)

                    with clear_col:
                        if st.button(
                            "Clear",
                            key=f"agent_clear_{key}",
                            use_container_width=True,
                        ):
                            st.session_state.pop(
                                agent_state_key,
                                None,
                            )
                            st.session_state.pop(
                                agent_error_key,
                                None,
                            )
                            st.rerun()

                if st.session_state.get(
                    agent_error_key
                ):
                    st.error(
                        st.session_state[
                            agent_error_key
                        ]
                    )

                saved_agent_result = (
                    st.session_state.get(
                        agent_state_key
                    )
                )

                if saved_agent_result:
                    try:
                        from models.launcher_models import (
                            LauncherClassification,
                        )

                        typed_agent_result = (
                            LauncherClassification(
                                **saved_agent_result
                            )
                        )

                        show_launcher_agent_result(
                            typed_agent_result
                        )

                        st.caption(
                            "Review only — this result has not "
                            "changed LAUNCHER_META, source code, "
                            "or PostgreSQL."
                        )

                    except Exception as e:
                        st.error(
                            "Stored Agent result could not be "
                            f"validated: {e}"
                        )

            if show_code:
                with st.expander(
                    "View code",
                    expanded=False,
                ):
                    st.code(
                        read_code(
                            script_path
                        ),
                        language="python",
                    )

            info = (
                st.session_state.proc.get(
                    key
                )
            )

            if (
                info
                and info.get("log")
            ):
                with st.expander(
                    "View log",
                    expanded=False,
                ):
                    st.code(
                        read_log(
                            info["log"]
                        ),
                        language="bash",
                    )

            st.divider()

