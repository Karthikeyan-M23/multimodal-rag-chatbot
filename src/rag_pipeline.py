from src.vector.vector_retriever import retrieve_documents
from src.retrieval.evidence_validator import validate_evidence
from src.generation.llm import get_llm
from src.generation.prompts import RAG_PROMPT
from src.retrieval.query_parser import parse_structured_query
from src.retrieval.structured_retriever import retrieve_structured_chunks
from src.retrieval.structured_answer import build_structured_answer
from src.retrieval.query_expander import expand_query

ABSTAIN = "The information is not available in the uploaded documents."


def format_context(documents):
    return "\n\n".join(
        f"Source: {document.metadata}\n\nContent:\n{document.page_content}"
        for document in documents
    )


def build_conversation_context(chat_history, limit=6):
    if not chat_history:
        return ""
    recent = chat_history[-limit:]
    return "\n".join(
        f"{message['role'].upper()}: {message['content']}"
        for message in recent
    )


def generate_answer(vector_store, question: str, k: int = 5, chunks=None, chat_history=None,bm25_retriever=None):
    parsed_query = parse_structured_query(question)

    if parsed_query["is_structured"] and chunks:
        results = retrieve_structured_chunks(chunks, parsed_query)
        return {
            "answer": build_structured_answer(results, parsed_query),
            "documents": results,
            "evidence": {
                "sufficient": bool(results),
                "reason": "Exact metadata filtering was used for a structured query.",
            },
            "query_type": "structured",
            "parsed_query": parsed_query,
        }

    expanded_queries = expand_query(question)

    documents = retrieve_documents(
    vector_store,
    question,
    k=k,
    expanded_queries=expanded_queries,
    bm25_retriever=bm25_retriever,
    )
    evidence_check = validate_evidence(documents)

    if not evidence_check["sufficient"]:
        return {
            "answer": ABSTAIN,
            "documents": [],
            "evidence": evidence_check,
            "query_type": "semantic",
            "parsed_query": parsed_query,
        }

    relevant_documents = evidence_check["relevant_documents"]
    context = format_context(relevant_documents)
    conversation_context = build_conversation_context(chat_history or [])
    if conversation_context:
        context = f"Recent conversation:\n{conversation_context}\n\nRetrieved evidence:\n{context}"

    prompt = RAG_PROMPT.format(context=context, question=question)
    response = get_llm().invoke(prompt)
    return {
        "answer": response.content,
        "documents": relevant_documents,
        "evidence": evidence_check,
        "query_type": "semantic",
        "parsed_query": parsed_query,
    }
