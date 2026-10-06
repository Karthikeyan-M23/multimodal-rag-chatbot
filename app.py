from pathlib import Path

import streamlit as st

from src.knowledge_base import build_knowledge_base
from src.rag_pipeline import generate_answer
from src.retrieval.citation_formatter import get_unique_citations


UPLOAD_DIR = Path("data/uploads")

SUPPORTED_TYPES = [
<<<<<<< Updated upstream
    "pdf",
    "docx",
    "png",
    "jpg",
    "jpeg",
    "webp",
    "mp3",
    "wav",
    "m4a",
    "aac",
    "flac",
    "mp4",
    "avi",
    "mov",
    "mkv",
    "webm",
    "html",
    "htm",
=======
    "pdf", "docx",
    "png", "jpg", "jpeg", "webp",
    "mp3", "wav", "m4a", "aac", "flac",
    "mp4", "avi", "mov", "mkv", "webm",
    "html", "htm",
>>>>>>> Stashed changes
]


def load_css():
    css_path = Path("assets/style.css")
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )


def init_state():
    defaults = {
        "vector_store": None,
        "chunks": [],
        "processed_files": [],
        "knowledge_base_ready": False,
        "messages": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def process_sources(uploaded_files, website_url):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    file_paths = []
    urls = []

    if website_url.strip():
        urls.append(website_url.strip())

    for existing_file in UPLOAD_DIR.iterdir():
        if existing_file.is_file():
            existing_file.unlink()

    progress = st.progress(0)
    status = st.empty()

    total = len(uploaded_files)

    for index, uploaded_file in enumerate(uploaded_files):
        file_path = UPLOAD_DIR / uploaded_file.name
        file_path.write_bytes(uploaded_file.getbuffer())
        file_paths.append(str(file_path))

        status.write(f"Saved: {uploaded_file.name}")

        if total:
            progress.progress(int(((index + 1) / total) * 30))

    status.write("Building unified knowledge base...")

    result = build_knowledge_base(
        file_paths=file_paths,
        urls=urls,
    )

    st.session_state.vector_store = result["vector_store"]
    st.session_state.chunks = result["chunks"]
    st.session_state.processed_files = [
        uploaded_file.name for uploaded_file in uploaded_files
    ] + urls
    st.session_state.knowledge_base_ready = True
    st.session_state.messages = []

    progress.progress(100)
    status.empty()

    return result


def render_sources(result):
    documents = result.get("documents", [])

    if not documents:
        st.caption("No supporting sources found.")
        return

    if result.get("query_type") == "structured":
        shown = set()
        for chunk in documents:
            metadata = chunk.get("metadata", {})
            source = metadata.get("git_script", "Unknown script")
            if source not in shown:
                st.markdown(f"- `{source}`")
                shown.add(source)
        return

    for citation in get_unique_citations(documents):
        st.markdown(f"- {citation}")


def render_sidebar():
    with st.sidebar:
        st.markdown("## Knowledge Base")

        if st.session_state.knowledge_base_ready:
            st.success("Ready")
            st.caption(
                f"{len(st.session_state.chunks)} searchable chunks"
            )

            if st.session_state.processed_files:
                st.markdown("**Sources**")
                for name in st.session_state.processed_files:
                    st.caption(f"• {name}")

            if st.button("Clear knowledge base", use_container_width=True):
                st.session_state.vector_store = None
                st.session_state.chunks = []
                st.session_state.processed_files = []
                st.session_state.knowledge_base_ready = False
                st.session_state.messages = []
                st.rerun()
        else:
            st.info("Upload and process sources to begin.")


def main():
    st.set_page_config(
        page_title="Multimodal RAG Chatbot",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    load_css()
    init_state()
    render_sidebar()

    st.markdown(
        '<div class="hero">'
        '<div class="hero-badge">LOCAL MULTIMODAL RAG</div>'
        '<h1>Knowledge Chat</h1>'
        '<p>Ask grounded questions across documents, images, audio, video, HTML reports and websites.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Add knowledge sources", expanded=not st.session_state.knowledge_base_ready):
        col1, col2 = st.columns([1.2, 0.8])

        with col1:
            uploaded_files = st.file_uploader(
                "Upload files",
                type=SUPPORTED_TYPES,
                accept_multiple_files=True,
                help="PDF, DOCX, image, audio, video and HTML files.",
            )

        with col2:
            website_url = st.text_input(
                "Website URL",
                placeholder="https://example.com/article",
            )

        if uploaded_files:
            st.caption(
                "Selected: " + ", ".join(f.name for f in uploaded_files)
            )

        if st.button("Process Knowledge Sources", type="primary"):
            if not uploaded_files and not website_url.strip():
                st.warning("Add at least one file or website URL.")
            else:
                try:
                    result = process_sources(uploaded_files or [], website_url)
                    st.success(
                        f"Knowledge base ready — {len(result['chunks'])} chunks."
                    )
                except Exception as exc:
                    st.error(f"Processing failed: {exc}")

    if not st.session_state.knowledge_base_ready:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-icon">📚</div>'
            '<h3>Your knowledge base is empty</h3>'
            '<p>Upload your sources above, process them, and start chatting.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown('<div class="chat-shell">', unsafe_allow_html=True)

    for message in st.session_state.messages:
        role = message["role"]
        with st.chat_message(role):
            st.markdown(message["content"])

            if role == "assistant" and message.get("sources"):
                with st.expander("Sources"):
                    for source in message["sources"]:
                        st.markdown(f"- {source}")

    st.markdown("</div>", unsafe_allow_html=True)

    question = st.chat_input(
        "Ask a question about your uploaded knowledge..."
    )

    if question:
        st.session_state.messages.append(
            {"role": "user", "content": question}
        )

        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Searching your knowledge base..."):
                try:
                    result = generate_answer(
                        st.session_state.vector_store,
                        question,
                        chunks=st.session_state.chunks,
                        chat_history=st.session_state.messages[:-1],
                    )

                    answer = result["answer"]

                    if result.get("query_type") == "structured":
                        sources = []
                        for chunk in result.get("documents", []):
                            source = chunk.get("metadata", {}).get(
                                "git_script"
                            )
                            if source and source not in sources:
                                sources.append(source)
                    else:
                        sources = get_unique_citations(
                            result.get("documents", [])
                        )

                    st.markdown(answer)

                    if sources:
                        with st.expander("Sources"):
                            for source in sources:
                                st.markdown(f"- {source}")

                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": answer,
                            "sources": sources,
                        }
                    )

                except Exception as exc:
                    error_message = f"Error while answering: {exc}"
                    st.error(error_message)
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": error_message,
                            "sources": [],
                        }
                    )


if __name__ == "__main__":
    main()
