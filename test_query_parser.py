from src.retrieval.query_parser import parse_structured_query

queries = [
    "Under 20260929 which files are executed in AXQA?",
    "Under 20260930 which files are not executed in CI?",
    "How many files were executed in TPQA under 20260929?",
]

for query in queries:
    print("=" * 80)
    print(query)
    print(parse_structured_query(query))
