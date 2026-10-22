"""
YouTube videos: title/description/chapters from yt-dlp, the transcript
from YouTube captions (fast), or Whisper on the downloaded audio when a
video has no captions.
"""

import re
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.ingestion.audio_processor import transcribe


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtube-nocookie.com",
}

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Caption languages to prefer, in order; any other language is used if
# none of these exist.
PREFERRED_LANGUAGES = ["en", "en-US", "en-GB"]


def youtube_video_id(url: str) -> str | None:
    """Video id from watch / youtu.be / shorts / live / embed URLs."""

    parsed = urlparse(url.strip())

    if parsed.scheme not in {"http", "https"} or parsed.hostname not in YOUTUBE_HOSTS:
        return None

    if parsed.hostname == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]

    elif parsed.path == "/watch":
        candidate = parse_qs(parsed.query).get("v", [""])[0]

    else:
        parts = parsed.path.strip("/").split("/")
        candidate = parts[1] if len(parts) >= 2 and parts[0] in {"shorts", "live", "embed", "v"} else ""

    return candidate if VIDEO_ID.match(candidate or "") else None


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _video_info(video_id: str) -> dict:

    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
        return ydl.extract_info(watch_url(video_id), download=False)


def _caption_segments(video_id: str) -> list[dict]:
    """[{'text', 'start', 'end'}] from YouTube captions, or [] if none."""

    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import CouldNotRetrieveTranscript

    try:
        transcripts = YouTubeTranscriptApi().list(video_id)
    except CouldNotRetrieveTranscript:
        return []

    try:
        # Manually created captions are preferred over auto-generated ones.
        transcript = transcripts.find_transcript(PREFERRED_LANGUAGES)
    except CouldNotRetrieveTranscript:
        available = list(transcripts)

        if not available:
            return []

        transcript = next((t for t in available if not t.is_generated), available[0])

    try:
        fetched = transcript.fetch()
    except CouldNotRetrieveTranscript:
        return []

    segments = []

    for snippet in fetched.snippets:

        text = " ".join(snippet.text.replace("\n", " ").split())

        # Skip "[Music]" style cues.
        if not text or re.fullmatch(r"\[[^\]]+\]", text):
            continue

        segments.append(
            {
                "text": text,
                "start": round(snippet.start, 2),
                "end": round(snippet.start + snippet.duration, 2),
            }
        )

    return segments


def _whisper_segments(video_id: str, progress=None) -> list[dict]:
    """Download the audio track and transcribe it locally."""

    import yt_dlp

    with tempfile.TemporaryDirectory() as temp_dir:

        options = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "outtmpl": str(Path(temp_dir) / "audio.%(ext)s"),
        }

        if progress:
            progress("Downloading audio")

        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([watch_url(video_id)])

        files = list(Path(temp_dir).glob("audio.*"))

        if not files:
            raise RuntimeError("Could not download the video's audio.")

        return transcribe(str(files[0]), progress)


def _chapter_at(chapters: list[dict], time: float) -> str:

    for chapter in chapters:
        if chapter.get("start_time", 0) <= time < chapter.get("end_time", float("inf")):
            return chapter.get("title", "")

    return ""


def extract_youtube_content(url: str, progress=None) -> list[dict]:

    video_id = youtube_video_id(url)

    if not video_id:
        raise ValueError("Not a valid YouTube video link.")

    if progress:
        progress("Reading video details")

    try:
        info = _video_info(video_id)
    except Exception as error:
        raise RuntimeError(f"Could not open this YouTube video: {str(error)[:200]}")

    title = info.get("title") or f"YouTube video {video_id}"
    chapters = info.get("chapters") or []

    base = {
        "source": watch_url(video_id),
        "url": watch_url(video_id),
        "file_type": "youtube",
        "title": title,
        "youtube_id": video_id,
        "channel": info.get("channel") or info.get("uploader") or "",
    }

    documents = []

    description = (info.get("description") or "").strip()

    if description or chapters:

        parts = [f"Title: {title}"]

        if base["channel"]:
            parts.append(f"Channel: {base['channel']}")

        if description:
            parts.append(f"Description:\n{description}")

        if chapters:
            parts.append(
                "Chapters:\n"
                + "\n".join(
                    f"{int(c.get('start_time', 0)) // 60:02d}:{int(c.get('start_time', 0)) % 60:02d} {c.get('title', '')}"
                    for c in chapters
                )
            )

        documents.append(
            {
                "text": "\n\n".join(parts),
                "metadata": {**base, "content_type": "description", "section": "Description"},
            }
        )

    if progress:
        progress("Fetching captions")

    segments = _caption_segments(video_id)
    method = "captions"

    if not segments:
        method = "whisper"
        segments = _whisper_segments(video_id, progress)

    for segment in segments:
        documents.append(
            {
                "text": segment["text"],
                "metadata": {
                    **base,
                    "content_type": "transcript",
                    "start_time": segment["start"],
                    "end_time": segment["end"],
                    "chapter": _chapter_at(chapters, segment["start"]),
                    "extraction": method,
                },
            }
        )

    if not segments and not documents:
        raise ValueError("This video has no captions or speech to index.")

    return documents
