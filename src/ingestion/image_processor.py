from src.ingestion.ocr import clean_ocr_text, ocr_image


def extract_image_content(file_path: str, describe=None, progress=None) -> list[dict]:
    """
    OCR text plus (optionally) a vision-model description, so photos and
    charts without text are still searchable.
    """

    text = clean_ocr_text(ocr_image(file_path))

    description = ""

    if describe:

        if progress:
            progress("Describing image")

        description = describe(file_path)

    parts = []

    if description:
        parts.append(f"Image description: {description}")

    if text:
        parts.append(f"Text in image:\n{text}")

    if not parts:
        return []

    methods = []

    if description:
        methods.append("vision")

    if text:
        methods.append("ocr")

    return [
        {
            "text": "\n\n".join(parts),
            "metadata": {
                "source": file_path,
                "file_type": "image",
                "extraction": "+".join(methods),
            },
        }
    ]
