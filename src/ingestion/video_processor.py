import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from config.settings import (
    FFMPEG_PATH,
    VIDEO_MAX_FRAMES,
    VIDEO_VISION_FRAMES,
)
from src.ingestion.audio_processor import transcribe
from src.ingestion.ocr import clean_ocr_text, ocr_image


# Frames whose average-hash differs by fewer bits than this from the
# previous kept frame are treated as the same scene.
SAME_SCENE_BITS = 10

MIN_FRAME_INTERVAL = 5.0


def _ffmpeg() -> str:
    return FFMPEG_PATH or "ffmpeg"


def _ffprobe() -> str:

    if FFMPEG_PATH:
        candidate = Path(FFMPEG_PATH).with_name(
            Path(FFMPEG_PATH).name.replace("ffmpeg", "ffprobe")
        )

        if candidate.exists():
            return str(candidate)

    return "ffprobe"


def _run(args):

    try:
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg/ffprobe not found. Install ffmpeg or set FFMPEG_PATH in .env."
        )


def _probe(path: Path) -> dict:

    output = _run(
        [
            _ffprobe(),
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    ).stdout

    data = json.loads(output)

    return {
        "duration": float(data.get("format", {}).get("duration") or 0),
        "has_audio": any(
            stream.get("codec_type") == "audio"
            for stream in data.get("streams", [])
        ),
    }


def _average_hash(image_path: Path) -> int:

    with Image.open(image_path) as image:
        pixels = list(image.convert("L").resize((16, 16)).getdata())

    mean = sum(pixels) / len(pixels)

    return sum(1 << index for index, pixel in enumerate(pixels) if pixel > mean)


def _frame_times(duration: float) -> list[float]:

    if duration <= 0:
        return [0.0]

    interval = max(MIN_FRAME_INTERVAL, duration / VIDEO_MAX_FRAMES)

    times = []
    time = min(1.0, duration / 2)

    while time < duration and len(times) < VIDEO_MAX_FRAMES:
        times.append(round(time, 2))
        time += interval

    return times


def extract_video_content(file_path: str, describe=None, progress=None) -> list[dict]:
    """
    Transcript segments (with start/end) plus sampled keyframes with
    OCR text and, when a vision model is available, a description.
    """

    source = Path(file_path)
    info = _probe(source)
    content = []

    with tempfile.TemporaryDirectory() as temp_dir:

        temp = Path(temp_dir)

        # ------------------------------------------
        # Transcript
        # ------------------------------------------

        if info["has_audio"]:

            if progress:
                progress("Transcribing audio")

            for segment in transcribe(str(source), progress):
                content.append(
                    {
                        "text": segment["text"],
                        "metadata": {
                            "source": str(source),
                            "file_type": "video",
                            "content_type": "transcript",
                            "start_time": segment["start"],
                            "end_time": segment["end"],
                        },
                    }
                )

        # ------------------------------------------
        # Keyframes
        # ------------------------------------------

        times = _frame_times(info["duration"])
        previous_hash = None
        previous_text = ""
        described = 0

        for index, time in enumerate(times, start=1):

            if progress:
                progress(f"Analyzing frame {index}/{len(times)}")

            frame_path = temp / f"frame_{index:03d}.jpg"

            try:
                _run(
                    [
                        _ffmpeg(), "-y", "-ss", str(time), "-i", str(source),
                        "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2",
                        str(frame_path),
                    ]
                )
            except subprocess.CalledProcessError:
                continue

            if not frame_path.exists():
                continue

            frame_hash = _average_hash(frame_path)

            if previous_hash is not None and (
                bin(frame_hash ^ previous_hash).count("1") < SAME_SCENE_BITS
            ):
                continue

            previous_hash = frame_hash

            text = clean_ocr_text(ocr_image(frame_path))

            if text == previous_text:
                text = ""
            else:
                previous_text = text

            description = ""

            if describe and described < VIDEO_VISION_FRAMES:
                description = describe(str(frame_path))
                described += 1

            parts = []

            if description:
                parts.append(f"Scene: {description}")

            if text:
                parts.append(f"On-screen text:\n{text}")

            if not parts:
                continue

            content.append(
                {
                    "text": "\n\n".join(parts),
                    "metadata": {
                        "source": str(source),
                        "file_type": "video",
                        "content_type": "frame",
                        "timestamp": time,
                        "start_time": time,
                    },
                }
            )

    return content
