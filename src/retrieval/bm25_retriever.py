import re

from rank_bm25 import BM25Okapi


TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*")

PART_SEPARATOR = re.compile(r"[._-]")

STOPWORDS = frozenset(
    """
    a an and are as at be but by for from has have how i in is it its of on
    or that the their there these this to was were what when where which who
    why will with you your do does did can could should would about into
    """.split()
)


def tokenize(text: str) -> list[str]:

    tokens = []

    for compound in TOKEN_PATTERN.findall(text.lower()):

        # Keep "005_product_data" whole for exact matches, and its parts
        # so a query for "product data" still finds it.
        parts = PART_SEPARATOR.split(compound)
        words = [compound] + parts if len(parts) > 1 else [compound]

        for token in words:

            if not token or token in STOPWORDS:
                continue

            # Light plural folding so "invoices" matches "invoice".
            if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
                token = token[:-1]

            tokens.append(token)

    return tokens


class BM25Retriever:

    def __init__(self, chunks):

        self.chunks = chunks

        self.tokenized_documents = [
            tokenize(chunk.get("search_text") or chunk["text"])
            for chunk in chunks
        ]

        # BM25Okapi cannot be built over an empty corpus.
        self.bm25 = (
            BM25Okapi(self.tokenized_documents)
            if any(self.tokenized_documents)
            else None
        )

    def retrieve(self, query, k=5, source_ids=None):
        """source_ids: optional set; only chunks from these sources."""

        tokenized_query = tokenize(query)

        if self.bm25 is None or not tokenized_query:
            return []

        scores = self.bm25.get_scores(tokenized_query)

        indexes = range(len(scores))

        if source_ids:
            indexes = [
                index
                for index in indexes
                if self.chunks[index]["metadata"].get("source_id") in source_ids
            ]

        ranked_indexes = sorted(
            indexes,
            key=lambda index: scores[index],
            reverse=True,
        )

        results = []

        for index in ranked_indexes[:k]:

            # No shared terms: not a keyword match at all.
            if scores[index] <= 0:
                break

            chunk = self.chunks[index]

            result = {
                "text": chunk["text"],
                "metadata": chunk["metadata"].copy(),
            }

            result["metadata"]["bm25_score"] = float(scores[index])

            results.append(result)

        return results
