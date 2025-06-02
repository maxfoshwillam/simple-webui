import importlib.metadata
import json
import logging
import os
import sys
import shutil
from pathlib import Path
import typing


def if_true(value:str | bool) -> bool:
    if isinstance(value,bool):
        return value
    
    if isinstance(value,str):
        return value.lower() == "true"

    return False

@typing.overload
def get_env(key:str, default: None) -> None: ...

@typing.overload
def get_env(key:str, default: str) -> str: ...

@typing.overload
def get_env(key:str, default: int) -> int: ...

@typing.overload
def get_env(key:str, default: bool) -> bool: ...

def get_env(key:str, default: typing.Any) -> typing.Any:
    value = os.environ.get(key,default)

    if not value:
        return default

    if isinstance(default,bool):
        return if_true(value)
    
    if isinstance(default, int):
        try:
            return int(value)
        except ValueError:
            return default

    if isinstance(default, float):
        try:
            return float(value)
        except ValueError:
            return default

    return value

####################################
# Load .env file
####################################

OPEN_WEBUI_DIR = Path(__file__).parent  # the path containing this file
print(OPEN_WEBUI_DIR)

BACKEND_DIR = OPEN_WEBUI_DIR.parent  # the path containing this file
BASE_DIR = BACKEND_DIR.parent  # the path containing the backend/

print(BACKEND_DIR)
print(BASE_DIR)

try:
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv(str(BASE_DIR / ".env")))
except ImportError:
    print("dotenv not installed, skipping...")

DOCKER = get_env("DOCKER")

# device type embedding models - "cpu" (default), "cuda" (nvidia gpu required) or "mps" (apple silicon) - choosing this right can lead to better performance
USE_CUDA = get_env("USE_CUDA_DOCKER")

if USE_CUDA:
    try:
        import torch

        assert torch.cuda.is_available(), "CUDA not available"
        DEVICE_TYPE = "cuda"
    except Exception as e:
        cuda_error = (
            "Error when testing CUDA but USE_CUDA_DOCKER is true. "
            f"Resetting USE_CUDA_DOCKER to false: {e}"
        )
        os.environ["USE_CUDA_DOCKER"] = "false"
        USE_CUDA = "false"
        DEVICE_TYPE = "cpu"
else:
    DEVICE_TYPE = "cpu"

try:
    import torch

    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        DEVICE_TYPE = "mps"
except Exception:
    pass

####################################
# LOGGING
####################################

GLOBAL_LOG_LEVEL = get_env("GLOBAL_LOG_LEVEL", "").upper()

if GLOBAL_LOG_LEVEL in logging.getLevelNamesMapping():
    logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL, force=True)
else:
    GLOBAL_LOG_LEVEL = "INFO"

log = logging.getLogger(__name__)
log.info(f"GLOBAL_LOG_LEVEL: {GLOBAL_LOG_LEVEL}")

if "cuda_error" in locals():
    log.exception(cuda_error)
    del cuda_error

log_sources = typing.Literal[
    "AUDIO",
    "COMFYUI",
    "CONFIG",
    "DB",
    "IMAGES",
    "MAIN",
    "MODELS",
    "OLLAMA",
    "OPENAI",
    "RAG",
    "WEBHOOK",
    "SOCKET",
    "OAUTH",
]

SRC_LOG_LEVELS = {}

for source in log_sources:
    log_env_var = source + "_LOG_LEVEL"
    SRC_LOG_LEVELS[source] = os.environ.get(log_env_var, "").upper()
    if SRC_LOG_LEVELS[source] not in logging.getLevelNamesMapping():
        SRC_LOG_LEVELS[source] = GLOBAL_LOG_LEVEL
    log.info(f"{log_env_var}: {SRC_LOG_LEVELS[source]}")

log.setLevel(SRC_LOG_LEVELS["CONFIG"])

WEBUI_NAME = os.environ.get("WEBUI_NAME", "Open WebUI")
if WEBUI_NAME != "Open WebUI":
    WEBUI_NAME += " (Open WebUI)"

WEBUI_FAVICON_URL = "https://openwebui.com/favicon.png"

TRUSTED_SIGNATURE_KEY = get_env("TRUSTED_SIGNATURE_KEY", "")

####################################
# ENV (dev,test,prod)
####################################

ENV = get_env("ENV", "prod")

FROM_INIT_PY = get_env("FROM_INIT_PY")

if FROM_INIT_PY:
    PACKAGE_DATA = {"version": importlib.metadata.version("open-webui")}
else:
    try:
        PACKAGE_DATA = json.loads((BASE_DIR / "package.json").read_text())
    except Exception:
        PACKAGE_DATA = {"version": "0.0.0"}

VERSION = PACKAGE_DATA["version"]


# Function to parse each section
def parse_section(section):
    items = []
    for li in section.find_all("li"):
        # Extract raw HTML string
        raw_html = str(li)

        # Extract text without HTML tags
        text = li.get_text(separator=" ", strip=True)

        # Split into title and content
        parts = text.split(": ", 1)
        title = parts[0].strip() if len(parts) > 1 else ""
        content = parts[1].strip() if len(parts) > 1 else text

        items.append({"title": title, "content": content, "raw": raw_html})
    return items

CHANGELOG = {"date":"mewo"}

####################################
# SAFE_MODE
####################################

SAFE_MODE = get_env("SAFE_MODE", False)

####################################
# ENABLE_FORWARD_USER_INFO_HEADERS
####################################

ENABLE_FORWARD_USER_INFO_HEADERS = (
    get_env("ENABLE_FORWARD_USER_INFO_HEADERS")
)

####################################
# WEBUI_BUILD_HASH
####################################

WEBUI_BUILD_HASH = get_env("WEBUI_BUILD_HASH", "dev-build")

####################################
# DATA/FRONTEND BUILD DIR
####################################

DATA_DIR = Path(os.getenv("DATA_DIR", BACKEND_DIR / "data")).resolve()

if FROM_INIT_PY:
    NEW_DATA_DIR = Path(os.getenv("DATA_DIR", OPEN_WEBUI_DIR / "data")).resolve()
    NEW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Check if the data directory exists in the package directory
    if DATA_DIR.exists() and DATA_DIR != NEW_DATA_DIR:
        log.info(f"Moving {DATA_DIR} to {NEW_DATA_DIR}")
        for item in DATA_DIR.iterdir():
            dest = NEW_DATA_DIR / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

        # Zip the data directory
        shutil.make_archive(DATA_DIR.parent / "open_webui_data", "zip", DATA_DIR)

        # Remove the old data directory
        shutil.rmtree(DATA_DIR)

    DATA_DIR = Path(os.getenv("DATA_DIR", OPEN_WEBUI_DIR / "data"))

STATIC_DIR = Path(os.getenv("STATIC_DIR", OPEN_WEBUI_DIR / "static"))

FONTS_DIR = Path(os.getenv("FONTS_DIR", OPEN_WEBUI_DIR / "static" / "fonts"))

FRONTEND_BUILD_DIR = Path(os.getenv("FRONTEND_BUILD_DIR", BASE_DIR / "build")).resolve()

if FROM_INIT_PY:
    FRONTEND_BUILD_DIR = Path(
        os.getenv("FRONTEND_BUILD_DIR", OPEN_WEBUI_DIR / "frontend")
    ).resolve()

####################################
# Database
####################################
DATABASE_URL = get_env("DATABASE_URL", f"sqlite:///{DATA_DIR}/webui.db")

DATABASE_SCHEMA = get_env("DATABASE_SCHEMA", None)

DATABASE_POOL_SIZE = get_env("DATABASE_POOL_SIZE", 0)

DATABASE_POOL_MAX_OVERFLOW = get_env("DATABASE_POOL_MAX_OVERFLOW", 0)

DATABASE_POOL_TIMEOUT = get_env("DATABASE_POOL_TIMEOUT", 30)

DATABASE_POOL_RECYCLE = get_env("DATABASE_POOL_RECYCLE", 3600)

RESET_CONFIG_ON_START = get_env("RESET_CONFIG_ON_START", False)

ENABLE_REALTIME_CHAT_SAVE = get_env("ENABLE_REALTIME_CHAT_SAVE", False)


####################################
# REDIS
####################################

REDIS_URL = get_env("REDIS_URL", "")
REDIS_SENTINEL_HOSTS = get_env("REDIS_SENTINEL_HOSTS", "")
REDIS_SENTINEL_PORT = get_env("REDIS_SENTINEL_PORT", "26379")

####################################
# UVICORN WORKERS
####################################

# Number of uvicorn worker processes for handling requests
UVICORN_WORKERS = get_env("UVICORN_WORKERS", 1)

try:
    if UVICORN_WORKERS < 1:
        UVICORN_WORKERS = 1
except ValueError:
    UVICORN_WORKERS = 1
    log.warn(f"Invalid UVICORN_WORKERS value, defaulting to {UVICORN_WORKERS}")

####################################
# WEBUI_AUTH (Required for security)
####################################

WEBUI_AUTH = get_env("WEBUI_AUTH", True)
WEBUI_AUTH_TRUSTED_EMAIL_HEADER = get_env(
    "WEBUI_AUTH_TRUSTED_EMAIL_HEADER", None
)
WEBUI_AUTH_TRUSTED_NAME_HEADER =get_env("WEBUI_AUTH_TRUSTED_NAME_HEADER", None)

BYPASS_MODEL_ACCESS_CONTROL = get_env("BYPASS_MODEL_ACCESS_CONTROL", "False").lower() == "true"


####################################
# WEBUI_SECRET_KEY
####################################

WEBUI_SECRET_KEY = get_env("WEBUI_SECRET_KEY", "HELLO_WORLD")

WEBUI_SESSION_COOKIE_SAME_SITE = get_env("WEBUI_SESSION_COOKIE_SAME_SITE", "lax")

WEBUI_SESSION_COOKIE_SECURE = get_env("WEBUI_SESSION_COOKIE_SECURE", False)


WEBUI_AUTH_COOKIE_SAME_SITE = get_env(
    "WEBUI_AUTH_COOKIE_SAME_SITE", WEBUI_SESSION_COOKIE_SAME_SITE
)

WEBUI_AUTH_COOKIE_SECURE = get_env("WEBUI_AUTH_COOKIE_SECURE", False)

ENABLE_WEBSOCKET_SUPPORT = get_env("ENABLE_WEBSOCKET_SUPPORT", True)
 
WEBSOCKET_MANAGER = get_env("WEBSOCKET_MANAGER", "")

WEBSOCKET_REDIS_URL = get_env("WEBSOCKET_REDIS_URL", REDIS_URL)
WEBSOCKET_REDIS_LOCK_TIMEOUT = get_env("WEBSOCKET_REDIS_LOCK_TIMEOUT", 60)

WEBSOCKET_SENTINEL_HOSTS = get_env("WEBSOCKET_SENTINEL_HOSTS", "")

WEBSOCKET_SENTINEL_PORT = get_env("WEBSOCKET_SENTINEL_PORT", "26379")

AIOHTTP_CLIENT_TIMEOUT = get_env("AIOHTTP_CLIENT_TIMEOUT", None)

if AIOHTTP_CLIENT_TIMEOUT:
    try:
        AIOHTTP_CLIENT_TIMEOUT = int(AIOHTTP_CLIENT_TIMEOUT)
    except Exception:
        AIOHTTP_CLIENT_TIMEOUT = 300

AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST = get_env(
    "AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST",
   10
)


AIOHTTP_CLIENT_TIMEOUT_TOOL_SERVER_DATA = os.environ.get(
    "AIOHTTP_CLIENT_TIMEOUT_TOOL_SERVER_DATA", 10
)

####################################
# OFFLINE_MODE
####################################

OFFLINE_MODE = get_env("OFFLINE_MODE", False)

if OFFLINE_MODE:
    os.environ["HF_HUB_OFFLINE"] = "1"

####################################
# AUDIT LOGGING
####################################
# Where to store log file
AUDIT_LOGS_FILE_PATH = f"{DATA_DIR}/audit.log"
# Maximum size of a file before rotating into a new log file
AUDIT_LOG_FILE_ROTATION_SIZE = os.getenv("AUDIT_LOG_FILE_ROTATION_SIZE", "10MB")
# METADATA | REQUEST | REQUEST_RESPONSE
AUDIT_LOG_LEVEL = os.getenv("AUDIT_LOG_LEVEL", "NONE").upper()
try:
    MAX_BODY_LOG_SIZE = int(os.environ.get("MAX_BODY_LOG_SIZE") or 2048)
except ValueError:
    MAX_BODY_LOG_SIZE = 2048

# Comma separated list for urls to exclude from audit
AUDIT_EXCLUDED_PATHS = os.getenv("AUDIT_EXCLUDED_PATHS", "/chats,/chat,/folders").split(
    ","
)
AUDIT_EXCLUDED_PATHS = [path.strip() for path in AUDIT_EXCLUDED_PATHS]
AUDIT_EXCLUDED_PATHS = [path.lstrip("/") for path in AUDIT_EXCLUDED_PATHS]

####################################
# OPENTELEMETRY
####################################

ENABLE_OTEL = get_env("ENABLE_OTEL", False)
OTEL_EXPORTER_OTLP_ENDPOINT = get_env(
    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
)
OTEL_SERVICE_NAME = get_env("OTEL_SERVICE_NAME", "open-webui")
OTEL_RESOURCE_ATTRIBUTES = get_env(
    "OTEL_RESOURCE_ATTRIBUTES", ""
)  # e.g. key1=val1,key2=val2
OTEL_TRACES_SAMPLER = get_env(
    "OTEL_TRACES_SAMPLER", "parentbased_always_on"
).lower()

####################################
# TOOLS/FUNCTIONS PIP OPTIONS
####################################

PIP_OPTIONS = os.getenv("PIP_OPTIONS", "").split()
PIP_PACKAGE_INDEX_OPTIONS = os.getenv("PIP_PACKAGE_INDEX_OPTIONS", "").split()


####################################
# PROGRESSIVE WEB APP OPTIONS
####################################

EXTERNAL_PWA_MANIFEST_URL = os.environ.get("EXTERNAL_PWA_MANIFEST_URL")
