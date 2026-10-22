from threading import Lock

from langchain_huggingface import HuggingFaceEmbeddings

from config.settings import EMBEDDING_MODEL


# BGE English models retrieve noticeably better when the *query*
# (not the passage) carries this instruction.
BGE_QUERY_INSTRUCTION = (
    "Represent this sentence for searching relevant passages: "
)

_models = {}

_lock = Lock()


class LocalEmbeddings(HuggingFaceEmbeddings):

    query_instruction: str = ""

    def embed_query(self, text: str) -> list[float]:
        return super().embed_query(self.query_instruction + text)


def get_embedding_model(model_name: str = EMBEDDING_MODEL):
    """Loaded once per model name; loading takes several seconds."""

    with _lock:

        if model_name not in _models:

            is_bge_en = "bge" in model_name.lower() and "-en" in model_name.lower()

            _models[model_name] = LocalEmbeddings(
                model_name=model_name,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
                query_instruction=BGE_QUERY_INSTRUCTION if is_bge_en else "",
            )

        return _models[model_name]
