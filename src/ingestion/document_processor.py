from docx import Document


def extract_docx_content(file_path: str) -> list[dict]:
    document = Document(file_path)

    content = []

    for paragraph_number, paragraph in enumerate(document.paragraphs, start=1):
        text = paragraph.text.strip()

        if not text:
            continue

        content.append({
            "text": text,
            "metadata": {
                "source": file_path,
                "file_type": "docx",
                "paragraph": paragraph_number,
            },
        })

    return content