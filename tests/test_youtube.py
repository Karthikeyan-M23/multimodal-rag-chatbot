import types

import pytest

from src.ingestion import youtube_processor
from src.ingestion.youtube_processor import youtube_video_id
from src.processing.chunker import create_chunks
from tests.test_library_api import chat, sources


@pytest.mark.parametrize("url,video_id", [
    ("https://www.youtube.com/watch?v=aircAruvnKk", "aircAruvnKk"),
    ("https://youtube.com/watch?v=aircAruvnKk&t=42s&list=PL1", "aircAruvnKk"),
    ("https://m.youtube.com/watch?v=aircAruvnKk", "aircAruvnKk"),
    ("https://youtu.be/aircAruvnKk?si=abc", "aircAruvnKk"),
    ("https://www.youtube.com/shorts/aircAruvnKk", "aircAruvnKk"),
    ("https://www.youtube.com/live/aircAruvnKk", "aircAruvnKk"),
    ("https://www.youtube.com/embed/aircAruvnKk", "aircAruvnKk"),
    ("https://www.youtube.com/watch?v=short", None),
    ("https://www.youtube.com/@3blue1brown", None),
    ("https://evil.com/watch?v=aircAruvnKk", None),
    ("https://youtube.com.evil.com/watch?v=aircAruvnKk", None),
    ("ftp://youtu.be/aircAruvnKk", None),
])
def test_video_id_parsing(url, video_id):
    assert youtube_video_id(url) == video_id


INFO = {
    "title": "But what is a neural network?",
    "channel": "3Blue1Brown",
    "description": "An introduction to neural networks.",
    "chapters": [
        {"start_time": 0, "end_time": 60, "title": "Introduction"},
        {"start_time": 60, "end_time": 600, "title": "Layers"},
    ],
}

CAPTIONS = [
    {"text": "Welcome to the video.", "start": 1.0, "end": 4.0},
    {"text": "[Music]", "start": 4.0, "end": 6.0},
    {"text": "Neurons hold a number called an activation.", "start": 20.0, "end": 28.0},
    {"text": "Networks are organised in layers.", "start": 62.0, "end": 70.0},
]


@pytest.fixture
def fake_youtube(monkeypatch):

    calls = {"whisper": 0}

    monkeypatch.setattr(youtube_processor, "_video_info", lambda video_id: INFO)
    monkeypatch.setattr(
        youtube_processor,
        "_caption_segments",
        lambda video_id: [c for c in CAPTIONS if c["text"] != "[Music]"],
    )

    def whisper(video_id, progress=None):
        calls["whisper"] += 1
        return [{"text": "Transcribed locally.", "start": 0.0, "end": 3.0}]

    monkeypatch.setattr(youtube_processor, "_whisper_segments", whisper)

    return calls


def test_extracts_description_and_timed_captions(fake_youtube):

    documents = youtube_processor.extract_youtube_content("https://youtu.be/aircAruvnKk")

    description = documents[0]
    assert description["metadata"]["content_type"] == "description"
    assert "3Blue1Brown" in description["text"] and "01:00 Layers" in description["text"]

    transcript = documents[1:]
    assert [d["metadata"]["chapter"] for d in transcript] == ["Introduction", "Introduction", "Layers"]
    assert transcript[0]["metadata"]["url"] == "https://www.youtube.com/watch?v=aircAruvnKk"
    assert fake_youtube["whisper"] == 0


def test_transcript_windows_break_at_chapters(fake_youtube):

    chunks = create_chunks(youtube_processor.extract_youtube_content("https://youtu.be/aircAruvnKk"))
    transcript = [c for c in chunks if c["metadata"]["content_type"] == "transcript"]

    assert len(transcript) == 2
    assert transcript[0]["metadata"]["chapter"] == "Introduction"
    assert transcript[1]["text"] == "Networks are organised in layers."


def test_falls_back_to_whisper_without_captions(fake_youtube, monkeypatch):

    monkeypatch.setattr(youtube_processor, "_caption_segments", lambda video_id: [])
    documents = youtube_processor.extract_youtube_content("https://youtu.be/aircAruvnKk")

    assert fake_youtube["whisper"] == 1
    assert documents[-1]["metadata"]["extraction"] == "whisper"


def test_youtube_through_the_api(client, alice, fake_youtube):

    response = client.post(
        "/api/sources",
        data={"youtube": "https://www.youtube.com/watch?v=aircAruvnKk&t=10s"},
        headers=alice,
    )
    assert response.status_code == 201

    source = sources(client, alice)[0]
    assert source["status"] == "ready", source
    assert source["kind"] == "youtube" and source["file_type"] == "youtube"
    assert source["name"] == INFO["title"]

    events = chat(client, alice, "What is an activation in a neuron?")
    top = events[0]["sources"][0]
    assert top["file_type"] == "youtube"
    assert top["youtube_id"] == "aircAruvnKk"
    assert top["location"].startswith("00:01–") and "Introduction" in top["location"]

    link = client.get(f"/api/sources/{source['id']}/link", headers=alice).json()
    assert link == {"url": "https://www.youtube.com/watch?v=aircAruvnKk", "youtube_id": "aircAruvnKk"}


def test_youtube_link_in_website_field_is_treated_as_video(client, alice, fake_youtube):
    client.post("/api/sources", data={"urls": "https://youtu.be/aircAruvnKk"}, headers=alice)
    assert sources(client, alice)[0]["kind"] == "youtube"


def test_invalid_youtube_link_rejected(client, alice):
    response = client.post("/api/sources", data={"youtube": "https://www.youtube.com/@channel"}, headers=alice)
    assert response.status_code == 400
    assert sources(client, alice) == []


def test_unavailable_video_fails_with_message(client, alice, monkeypatch):

    def boom(video_id):
        raise RuntimeError("Video unavailable")

    monkeypatch.setattr(youtube_processor, "_video_info", boom)
    client.post("/api/sources", data={"youtube": "https://youtu.be/aircAruvnKk"}, headers=alice)

    source = sources(client, alice)[0]
    assert source["status"] == "failed"
    assert "Could not open this YouTube video" in source["error"]


def test_caption_filtering_with_real_api_shape(monkeypatch):
    """_caption_segments against the youtube-transcript-api object shape."""

    snippet = lambda text, start, duration: types.SimpleNamespace(text=text, start=start, duration=duration)

    fetched = types.SimpleNamespace(snippets=[
        snippet("Hello\nworld", 0.5, 2.0),
        snippet("[Applause]", 2.5, 1.0),
        snippet("  ", 3.5, 1.0),
    ])
    transcript = types.SimpleNamespace(is_generated=False, fetch=lambda: fetched)
    listing = types.SimpleNamespace(find_transcript=lambda languages: transcript)

    class FakeApi:
        def list(self, video_id):
            return listing

    import youtube_transcript_api
    monkeypatch.setattr(youtube_transcript_api, "YouTubeTranscriptApi", FakeApi)

    assert youtube_processor._caption_segments("aircAruvnKk") == [
        {"text": "Hello world", "start": 0.5, "end": 2.5}
    ]
