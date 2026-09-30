from src.vector.vector_retriever import retrieve_documents
from src.retrieval.evidence_validator import validate_evidence
from src.generation.llm import get_llm
from src.generation.prompts import RAG_PROMPT


def format_context(documents):
    context_parts = []

    for document in documents:
        context_parts.append(
            f"""
Source: {document.metadata}

Content:
{document.page_content}
"""
        )

    return "\n\n".join(context_parts)


def generate_answer(vector_store, question: str, k: int = 5):

    # 1. Retrieve evidence
    documents = retrieve_documents(
        vector_store,
        question,
        k=k,
    )

    # 2. Validate evidence
    evidence_check = validate_evidence(documents)

    # 3. Stop if there is no usable evidence
    if not evidence_check["sufficient"]:
        return {
            "answer": (
                "The information is not available "
                "in the uploaded documents."
            ),
            "documents": [],
            "evidence": evidence_check,
        }

    # 4. Build context
    relevant_documents = evidence_check["relevant_documents"]

    context = format_context(relevant_documents)

    # 5. Build prompt
    prompt = RAG_PROMPT.format(
        context=context,
        question=question,
    )

    # 6. Generate answer
    llm = get_llm()

    response = llm.invoke(prompt)

    return {
        "answer": response.content,
        "documents": documents,
        "evidence": evidence_check,
    }