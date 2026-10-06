import subprocess
import tempfile
from pathlib import Path

import pytesseract
from PIL import Image

from src.ingestion.audio_processor import get_whisper_model
from config.settings import FFMPEG_PATH, TESSERACT_PATH


if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def _ffmpeg_executable():
    return FFMPEG_PATH or "ffmpeg"


def extract_video_content(file_path: str) -> list[dict]:
    source = Path(file_path)
    model = get_whisper_model()
    content = []

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        audio_path = temp / "audio.wav"
        frames_dir = temp / "frames"
        frames_dir.mkdir()

        subprocess.run(
            [
                _ffmpeg_executable(),
                "-y",
                "-i",
                str(source),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                str(audio_path),
            ],
            check=True,
            capture_output=True,
        )

        segments, _ = model.transcribe(
            str(audio_path),
            vad_filter=True,
        )

        for segment in segments:
            text = segment.text.strip()

            if text:
                content.append(
                    {
                        "text": text,
                        "metadata": {
                            "source": str(source),
                            "file_type": "video",
                            "content_type": "transcript",
                            "start_time": round(segment.start, 2),
                            "end_time": round(segment.end, 2),
                        },
                    }
                )

        subprocess.run(
            [
                _ffmpeg_executable(),
                "-y",
                "-i",
                str(source),
                "-vf",
                "fps=1",
                str(frames_dir / "frame_%06d.jpg"),
            ],
            check=True,
            capture_output=True,
        )

        previous_text = ""

        for frame_number, frame_path in enumerate(
            sorted(frames_dir.glob("*.jpg"))
        ):
            text = pytesseract.image_to_string(
                Image.open(frame_path)
            ).strip()

            # Avoid repeating identical OCR from static frames.
            if not text or text == previous_text:
                previous_text = text
                continue

            previous_text = text

            content.append(
                {
                    "text": text,
                    "metadata": {
                        "source": str(source),
                        "file_type": "video",
                        "content_type": "frame_ocr",
                        "timestamp": float(frame_number),
                    },
                }
            )

    return content
