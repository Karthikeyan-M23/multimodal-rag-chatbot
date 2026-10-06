import os

from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3.2:3b",
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "BAAI/bge-base-en-v1.5",
)

TESSERACT_PATH = os.getenv(
    "TESSERACT_PATH",
    "",
)

FFMPEG_PATH = os.getenv(
    "FFMPEG_PATH",
    "",
)
