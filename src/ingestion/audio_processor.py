from faster_whisper import WhisperModel


MODEL_SIZE = "tiny"

_model = None


def get_whisper_model():
    global _model

    if _model is None:
        _model = WhisperModel(
            MODEL_SIZE,
            device="cpu",
            compute_type="int8",
        )

    return _model


def extract_audio_content(file_path: str) -> list[dict]:
    model = get_whisper_model()

    segments, _ = model.transcribe(
        str(file_path),
        vad_filter=True,
    )

    content = []

    for segment in segments:
        text = segment.text.strip()

        if not text:
            continue

        content.append(
            {
                "text": text,
                "metadata": {
                    "source": file_path,
                    "file_type": "audio",
                    "start_time": round(segment.start, 2),
                    "end_time": round(segment.end, 2),
                },
            }
        )

    return content
