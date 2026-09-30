from pathlib import Path
from faster_whisper import WhisperModel


MODEL_SIZE = "tiny"


def get_whisper_model():
    return WhisperModel(
        MODEL_SIZE,
        device="cpu",
        compute_type="int8",
    )


def extract_audio_content(file_path: str) -> list[dict]:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    model = get_whisper_model()

    segments, info = model.transcribe(
        str(path),
        vad_filter=True,
    )

    content = []

    for segment in segments:
        text = segment.text.strip()

        if not text:
            continue

        content.append({
            "text": text,
            "metadata": {
                "source": file_path,
                "file_type": "audio",
                "start_time": round(segment.start, 2),
                "end_time": round(segment.end, 2),
            },
        })

    return content