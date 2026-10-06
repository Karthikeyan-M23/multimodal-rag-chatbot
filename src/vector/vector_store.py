from pathlib import Path

from langchain_community.vectorstores import FAISS

<<<<<<< Updated upstream

VECTORSTORE_PATH = "vectorstore/current_index"
=======
VECTORSTORE_PATH = "vectorstore/fitness_index"
>>>>>>> Stashed changes


def create_vector_store(chunks, embeddings):
    texts = [chunk["text"] for chunk in chunks]
    metadatas = [chunk["metadata"] for chunk in chunks]
    return FAISS.from_texts(texts=texts, embedding=embeddings, metadatas=metadatas)


def save_vector_store(vector_store, path=VECTORSTORE_PATH):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(path)


def load_vector_store(embeddings, path=VECTORSTORE_PATH):
    if not Path(path).exists():
        raise FileNotFoundError(f"Vector store not found at: {path}")
    return FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
