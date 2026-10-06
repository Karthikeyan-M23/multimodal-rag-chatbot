from src.generation.llm import get_llm


QUERY_EXPANSION_PROMPT = """
You are a query understanding component for a document-grounded RAG system.

Rewrite the user's question into 3 alternative search queries that may
retrieve relevant information from the user's documents.

Rules:
- Preserve the original meaning.
- Do not answer the question.
- Do not introduce facts that are not implied by the question.
- Use related terminology and alternative wording.
- Keep each query concise.
- Return ONLY the queries, one per line.
- Do not number them.

User question:
{question}
"""


def expand_query(question: str) -> list[str]:
    prompt = QUERY_EXPANSION_PROMPT.format(question=question)

    response = get_llm().invoke(prompt)

    lines = [
        line.strip()
        for line in response.content.splitlines()
        if line.strip()
    ]

    queries = []

    for query in lines:
        if query.lower() == question.lower():
            continue

        if query not in queries:
            queries.append(query)

    return queries[:3]