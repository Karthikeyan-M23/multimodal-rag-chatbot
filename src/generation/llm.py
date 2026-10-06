from langchain_ollama import ChatOllama

from config.settings import OLLAMA_BASE_URL, OLLAMA_MODEL


def get_llm():
    return ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_MODEL,
        temperature=0,
    )
