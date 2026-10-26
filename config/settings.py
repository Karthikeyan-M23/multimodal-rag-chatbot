import os

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:

    value = os.getenv(name)

    if value is None or value.strip() == "":
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:

    value = os.getenv(name, "").strip()

    return int(value) if value else default


def _float(name: str, default: float) -> float:

    value = os.getenv(name, "").strip()

    return float(value) if value else default


# --------------------------------------------------
# Providers (server defaults; users can override in Settings)
# --------------------------------------------------

# "ollama" or "openai"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

# "local" (sentence-transformers) or "openai"
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3.2:3b",
)

# Ollama's default context window is small and silently truncates long
# prompts (evidence + history).
OLLAMA_NUM_CTX = _int("OLLAMA_NUM_CTX", 8192)

OLLAMA_VISION_MODEL = os.getenv(
    "OLLAMA_VISION_MODEL",
    "qwen2.5vl:3b",
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Leave empty for api.openai.com. Any OpenAI-compatible endpoint works
# (Azure OpenAI proxy, LiteLLM, vLLM, LM Studio, ...).
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini",
)

OPENAI_VISION_MODEL = os.getenv(
    "OPENAI_VISION_MODEL",
    "gpt-4o-mini",
)

OPENAI_EMBEDDING_MODEL = os.getenv(
    "OPENAI_EMBEDDING_MODEL",
    "text-embedding-3-small",
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "BAAI/bge-base-en-v1.5",
)

VISION_ENABLED = _bool("VISION_ENABLED", True)


# --------------------------------------------------
# Retrieval
# --------------------------------------------------

RERANKER_ENABLED = _bool("RERANKER_ENABLED", True)

RERANKER_MODEL = os.getenv(
    "RERANKER_MODEL",
    "BAAI/bge-reranker-base",
)

# Candidates pulled from each of vector + keyword search.
RETRIEVAL_CANDIDATES = _int("RETRIEVAL_CANDIDATES", 25)

# Candidates passed to the reranker after fusion.
RERANK_CANDIDATES = _int("RERANK_CANDIDATES", 24)

# Chunks given to the LLM as evidence.
CONTEXT_CHUNKS = _int("CONTEXT_CHUNKS", 6)

# Upper bound on evidence text per answer. Prompt processing dominates
# latency for local models on CPU (~60 tokens/s for a 3B model).
MAX_CONTEXT_CHARS = _int("MAX_CONTEXT_CHARS", 4500)

# Reranker relevance (0-1) below which a chunk is not used as evidence.
# Calibrated on bge-reranker-base: unrelated questions score < 0.003,
# paraphrased relevant ones from ~0.02.
RERANK_MIN_SCORE = _float("RERANK_MIN_SCORE", 0.01)

# Also drop chunks scoring below this fraction of the best chunk, so a
# strong match is not diluted with marginal ones.
RERANK_RELATIVE_CUTOFF = _float("RERANK_RELATIVE_CUTOFF", 0.05)

# When the reranker rejects everything, still use passages that both
# vector and keyword search found with at least this BM25 score (a rare
# query term such as a name or ID matched).
KEYWORD_RESCUE_SCORE = _float("KEYWORD_RESCUE_SCORE", 3.0)

# Used only when the reranker is disabled (L2 distance on unit vectors).
MAX_VECTOR_DISTANCE = _float("MAX_VECTOR_DISTANCE", 1.0)

# Rewrite follow-up questions into standalone search queries.
QUERY_REWRITE = _bool("QUERY_REWRITE", True)

# Load the local embedding model and reranker at startup.
WARM_UP_MODELS = _bool("WARM_UP_MODELS", True)

CHUNK_SIZE = _int("CHUNK_SIZE", 1000)

CHUNK_OVERLAP = _int("CHUNK_OVERLAP", 150)


# --------------------------------------------------
# Media
# --------------------------------------------------

TESSERACT_PATH = os.getenv(
    "TESSERACT_PATH",
    "",
)

FFMPEG_PATH = os.getenv(
    "FFMPEG_PATH",
    "",
)

# faster-whisper size: tiny, base, small, medium, large-v3
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

# Frames sampled across a video for OCR / captions.
VIDEO_MAX_FRAMES = _int("VIDEO_MAX_FRAMES", 12)

# How many of those frames get a vision caption (slow on CPU).
VIDEO_VISION_FRAMES = _int("VIDEO_VISION_FRAMES", 6)


# --------------------------------------------------
# Uploads
# --------------------------------------------------

MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 500)

# Allow the server to fetch localhost / private-network URLs.
ALLOW_PRIVATE_URLS = _bool("ALLOW_PRIVATE_URLS", False)

# Private-network hosts that are allowed anyway, comma-separated
# (e.g. "tfs.company.local,wiki.company.local").
PRIVATE_URL_ALLOWLIST = {
    host.strip().lower()
    for host in os.getenv("PRIVATE_URL_ALLOWLIST", "").split(",")
    if host.strip()
}

# Upper bound on work items imported from one TFS / Azure DevOps source.
TFS_MAX_WORK_ITEMS = _int("TFS_MAX_WORK_ITEMS", 2000)


# --------------------------------------------------
# Storage
# --------------------------------------------------

# Database, uploads and generated secrets.
DATA_DIR = os.getenv("DATA_DIR") or "data"

# Per-user FAISS indexes.
VECTORSTORE_DIR = os.getenv("VECTORSTORE_DIR") or "vectorstore"


# --------------------------------------------------
# Auth
# --------------------------------------------------

# If JWT_SECRET is empty a random one is generated and stored in
# DATA_DIR/.jwt_secret so tokens survive restarts.
JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "",
)

JWT_EXPIRE_MINUTES = _int("JWT_EXPIRE_MINUTES", 480)

# Encrypts users' saved API keys. Generated in DATA_DIR/.encryption_key
# when empty. Must be a Fernet key (cryptography.fernet.Fernet.generate_key()).
APP_ENCRYPTION_KEY = os.getenv("APP_ENCRYPTION_KEY", "")

DATABASE_PATH = os.getenv("DATABASE_PATH") or os.path.join(DATA_DIR, "app.db")
