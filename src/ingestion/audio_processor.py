import subprocess
from threading import Lock

import numpy as np
from faster_whisper import WhisperModel

from config.settings import FFMPEG_PATH, WHISPER_MODEL


SAMPLE_RATE = 16000


_model = None

_lock = Lock()


def get_whisper_model():

    global _model

    with _lock:
        if _model is None:
            _model = WhisperModel(
                WHISPER_MODEL,
                device="cpu",
                compute_type="int8",
            )

    return _model


def _load_audio(file_path: str):
    """
    Decode any audio/video file to 16 kHz mono float32 with ffmpeg.
    faster-whisper's own PyAV decoder breaks on newer PyAV releases.
    Falls back to the path (PyAV) if ffmpeg is not installed.
    """

    try:
        result = subprocess.run(
            [
                FFMPEG_PATH or "ffmpeg", "-nostdin", "-i", str(file_path),
                "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
                "-f", "f32le", "-loglevel", "error", "-",
            ],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return str(file_path)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            "Could not decode audio: "
            + error.stderr.decode(errors="replace").strip()[-300:]
        )

    return np.frombuffer(result.stdout, dtype=np.float32)


def transcribe(file_path: str, progress=None) -> list[dict]:
    """Whisper segments as [{'text', 'start', 'end'}]."""

    audio = _load_audio(file_path)

    if not isinstance(audio, str) and audio.size == 0:
        return []

    segments, info = get_whisper_model().transcribe(
        audio,
        vad_filter=True,
    )

    results = []

    for segment in segments:

        text = segment.text.strip()

        if not text:
            continue

        results.append(
            {
                "text": text,
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
            }
        )

        if progress and info.duration:
            progress(
                f"Transcribing {min(99, int(100 * segment.end / info.duration))}%"
            )

    return results


def extract_audio_content(file_path: str, progress=None) -> list[dict]:

    return [
        {
            "text": segment["text"],
            "metadata": {
                "source": file_path,
                "file_type": "audio",
                "content_type": "transcript",
                "start_time": segment["start"],
                "end_time": segment["end"],
            },
        }
        for segment in transcribe(file_path, progress)
    ]
