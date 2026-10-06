from rank_bm25 import BM25Okapi


class BM25Retriever:
    def __init__(self, chunks):
        self.chunks = chunks

        self.tokenized_documents = [
            self._tokenize(chunk["text"])
            for chunk in chunks
        ]

        self.bm25 = BM25Okapi(self.tokenized_documents)

    @staticmethod
    def _tokenize(text):
        return text.lower().split()

    def retrieve(self, query, k=5):
        tokenized_query = self._tokenize(query)

        scores = self.bm25.get_scores(tokenized_query)

        ranked_indexes = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )

        results = []

        for index in ranked_indexes[:k]:
            chunk = self.chunks[index]

            result = {
                "text": chunk["text"],
                "metadata": chunk["metadata"].copy(),
            }

            result["metadata"]["bm25_score"] = float(scores[index])

            results.append(result)

        return results