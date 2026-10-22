from src.providers import build_config, get_llm as _get_llm


def get_llm(config=None):
    """Chat model for the given ProviderConfig (server defaults if None)."""

    return _get_llm(config or build_config())
