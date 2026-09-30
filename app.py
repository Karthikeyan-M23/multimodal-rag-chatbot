import os
import shutil
from pathlib import Path

import streamlit as st

from src.knowledge_base import build_knowledge_base
from src.rag_pipeline import generate_answer

from src.retrieval.citation_formatter import (
    get_unique_citations,
)

UPLOAD_DIR = Path("data/uploads")


SUPPORTED_TYPES = [
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
]


st.set_page_config(
    page_title="Multimodal RAG Chatbot",
    page_icon="📚",
    layout="wide",
)


st.title("📚 Multimodal RAG Chatbot")

st.write(
    "Upload one or more documents and ask questions "
    "based only on the uploaded content."
)


# --------------------------------------------------
# Session state
# --------------------------------------------------

if "vector_store" not in st.session_state:
    st.session_state.vector_store = None

if "processed_files" not in st.session_state:
    st.session_state.processed_files = []

if "knowledge_base_ready" not in st.session_state:
    st.session_state.knowledge_base_ready = False


# --------------------------------------------------
# File upload
# --------------------------------------------------

st.header("1. Upload Documents")

uploaded_files = st.file_uploader(
    "Upload your files",
    type=SUPPORTED_TYPES,
    accept_multiple_files=True,
)


st.header("2. Add Website")

website_url = st.text_input(
    "Paste a website URL",
    placeholder="https://example.com/article",
)

# --------------------------------------------------
# Process documents
# --------------------------------------------------
if uploaded_files or website_url.strip():

    if uploaded_files:

        st.write(
            f"Selected files: **{len(uploaded_files)}**"
        )

        for uploaded_file in uploaded_files:
            st.write(
                f"• {uploaded_file.name}"
            )

    if website_url.strip():

        st.write(
            f"Website: **{website_url.strip()}**"
        )

    if st.button(
        "Process Knowledge Sources",
        type="primary",
    ):

        UPLOAD_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_paths = []
        urls = []

        if website_url.strip():

            urls.append(
        website_url.strip()
    )
        progress = st.progress(0)

        status = st.empty()

        try:

            # Remove previous uploaded files
            for existing_file in UPLOAD_DIR.iterdir():

                if existing_file.is_file():
                    existing_file.unlink()

            # Save uploaded files
            for index, uploaded_file in enumerate(
                uploaded_files
            ):

                file_path = (
                    UPLOAD_DIR
                    / uploaded_file.name
                )

                with open(
                    file_path,
                    "wb",
                ) as file:

                    file.write(
                        uploaded_file.getbuffer()
                    )

                file_paths.append(
                    str(file_path)
                )

                status.write(
                    f"Saved: {uploaded_file.name}"
                )

                progress.progress(
                    int(
                        ((index + 1)
                        / len(uploaded_files))
                        * 30
                    )
                )

            status.write(
                "Processing documents..."
            )

            result = build_knowledge_base(
             file_paths=file_paths,
                urls=urls,
            )

            st.session_state.vector_store = (
                result["vector_store"]
            )

            st.session_state.processed_files = [
                uploaded_file.name
                for uploaded_file in uploaded_files
            ]

            st.session_state.knowledge_base_ready = True

            progress.progress(100)

            status.empty()

            st.success(
                f"Knowledge base created successfully. "
                f"{len(uploaded_files)} file(s), "
                f"{len(result['chunks'])} chunks."
            )

        except Exception as e:

            st.error(
                f"Error while processing files: {e}"
            )


# --------------------------------------------------
# Knowledge base status
# --------------------------------------------------

if st.session_state.knowledge_base_ready:

    st.divider()

    st.header("2. Knowledge Base")

    st.success("Knowledge base is ready.")

    st.write("Processed files:")

    for file_name in st.session_state.processed_files:
        st.write(f"• {file_name}")


# --------------------------------------------------
# Question answering
# --------------------------------------------------

st.divider()

st.header("3. Ask a Question")

question = st.text_input(
    "Ask something about the uploaded documents:"
)


if st.button("Ask"):

    if not st.session_state.knowledge_base_ready:

        st.warning(
            "Please upload and process documents first."
        )

    elif not question.strip():

        st.warning(
            "Please enter a question."
        )

    else:

        with st.spinner("Searching documents..."):

            try:

                result = generate_answer(
                    st.session_state.vector_store,
                    question,
                    k=5,
                )

                st.subheader("Answer")

                st.write(
                    result["answer"]
                )

                st.subheader("Sources")

                if result["documents"]:

                    citations = get_unique_citations(
                        result["documents"]
                    )

                    for citation in citations:

                        st.write(
                            f"• {citation}"
                        )

                else:

                    st.write(
                        "No supporting sources found."
                    )

            except Exception as e:

                st.error(
                    f"Error while answering question: {e}"
                )