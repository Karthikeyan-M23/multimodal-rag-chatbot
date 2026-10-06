from src.ingestion.loader import load_document
from src.processing.chunker import create_chunks
from src.retrieval.query_parser import parse_structured_query
from src.retrieval.structured_retriever import retrieve_structured_chunks

HTML_FILE = r"data\uploads\deployment-dashboard 6.html"

documents = load_document(HTML_FILE)
chunks = create_chunks(documents)

query = "Under 20260929 which files are executed in AXQA?"
parsed = parse_structured_query(query)
results = retrieve_structured_chunks(chunks, parsed)

print(f"Extracted documents: {len(documents)}")
print(f"Created chunks: {len(chunks)}")
print("PARSED QUERY:", parsed)
print("MATCHING RECORDS:", len(results))

for index, chunk in enumerate(results, 1):
    metadata = chunk["metadata"]
    print(
        f"{index}. {metadata.get('git_script')} | "
        f"AXQA={metadata.get('axqa')} | "
        f"GroupDate={metadata.get('deployment_group_date')} | "
        f"ScriptDate={metadata.get('script_date')}"
    )
