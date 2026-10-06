from src.ingestion.html_processor import extract_html_content


HTML_FILE = r"data\uploads\deployment-dashboard 6.html"


documents = extract_html_content(HTML_FILE)

print()
print("=" * 80)
print("TOTAL EXTRACTED RECORDS:", len(documents))
print("=" * 80)

for index, document in enumerate(documents[:10]):

    print()
    print(f"RECORD {index + 1}")
    print("-" * 80)

    print("TEXT:")
    print(document["text"])

    print()
    print("METADATA:")

    for key, value in document["metadata"].items():
        print(f"  {key}: {value}")