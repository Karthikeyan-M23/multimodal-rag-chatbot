from pathlib import Path
import subprocess
import tempfile

from PIL import Image
import pytesseract
from faster_whisper import WhisperModel


MODEL_SIZE = "tiny"


def get_whisper_model():
    return WhisperModel(
        MODEL_SIZE,
        device="cpu",
        compute_type="int8",
    )


def extract_audio_from_video(video_path: str, audio_path: str):
    command = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vn",
        "-acodec",
        "pcm_s16le",
        audio_path,
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def extract_video_frames(video_path: str, output_dir: str):
    command = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vf",
        "fps=1",
        f"{output_dir}/frame_%04d.png",
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def extract_video_content(file_path: str) -> list[dict]:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    content = []

    with tempfile.TemporaryDirectory() as temp_dir:

        # ------------------------------------------------
        # 1. Extract audio
        # ------------------------------------------------
        audio_path = str(Path(temp_dir) / "audio.wav")

        extract_audio_from_video(
            str(path),
            audio_path
        )

        # ------------------------------------------------
        # 2. Transcribe audio
        # ------------------------------------------------
        model = get_whisper_model()

        segments, info = model.transcribe(
            audio_path,
            vad_filter=True,
        )

        for segment in segments:

            text = segment.text.strip()

            if not text:
                continue

            content.append({
                "text": text,
                "metadata": {
                    "source": file_path,
                    "file_type": "video",
                    "content_type": "transcript",
                    "start_time": round(segment.start, 2),
                    "end_time": round(segment.end, 2),
                },
            })

        # ------------------------------------------------
        # 3. Extract video frames
        # ------------------------------------------------
        frames_dir = Path(temp_dir) / "frames"
        frames_dir.mkdir()

        extract_video_frames(
            str(path),
            str(frames_dir)
        )

        # ------------------------------------------------
        # 4. OCR each frame
        # ------------------------------------------------
        frame_files = sorted(frames_dir.glob("*.png"))

        for frame_index, frame_file in enumerate(frame_files):

            image = Image.open(frame_file)

            text = pytesseract.image_to_string(
                image
            ).strip()

            if not text:
                continue

            # fps=1 means one frame per second
            timestamp = float(frame_index)

            content.append({
                "text": text,
                "metadata": {
                    "source": file_path,
                    "file_type": "video",
                    "content_type": "frame_ocr",
                    "timestamp": timestamp,
                },
            })

    return content