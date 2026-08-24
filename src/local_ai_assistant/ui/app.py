from __future__ import annotations

import shutil
from pathlib import Path

import streamlit as st

from local_ai_assistant.common.config import get_config
from local_ai_assistant.common.logging import configure_logging, get_logger
from local_ai_assistant.rag import LocalRAG
from local_ai_assistant.ui.coding import render_coding_workspace

CONFIG = get_config()
configure_logging(CONFIG.runtime)
logger = get_logger(__name__)
DOCUMENT_DIR = CONFIG.paths.document_dir


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Local Qwen AI",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 Local Qwen AI")
st.caption(
    "Qwen 35B + Hybrid RAG + FAISS + BM25 + OCR — running locally"
)

workspace = st.sidebar.radio(
    "Workspace", ("Documents", "Coding", "History", "Metrics", "System")
)
if workspace != "Documents":
    render_coding_workspace(CONFIG, workspace)
    st.stop()


# ============================================================
# SESSION STATE
# ============================================================

if "rag" not in st.session_state:
    with st.spinner("Loading local RAG system..."):
        rag = LocalRAG(config=CONFIG)

        if rag.initialize_index():
            st.session_state.rag = rag
        else:
            st.session_state.rag = rag


if "messages" not in st.session_state:
    st.session_state.messages = []


rag: LocalRAG = st.session_state.rag


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("Knowledge Base")

    uploaded_files = st.file_uploader(
        "Upload documents",
        type=[
            "pdf",
            "docx",
            "txt",
            "md",
        ],
        accept_multiple_files=True,
    )

    if uploaded_files:

        if st.button(
            "Save & Reindex",
            type="primary",
            use_container_width=True,
        ):

            saved = []

            with st.spinner(
                "Saving documents..."
            ):

                for uploaded_file in uploaded_files:

                    destination = (
                        DOCUMENT_DIR
                        / uploaded_file.name
                    )

                    with destination.open(
                        "wb"
                    ) as file:

                        shutil.copyfileobj(
                            uploaded_file,
                            file,
                        )

                    saved.append(
                        uploaded_file.name
                    )

            with st.spinner(
                "Rebuilding hybrid index..."
            ):

                rag.force_reindex()

            st.success(
                f"Indexed {len(saved)} file(s)."
            )

            for name in saved:
                st.write(f"• {name}")


    st.divider()

    st.subheader("Indexed documents")

    documents = sorted(
        [
            path
            for path
            in DOCUMENT_DIR.rglob("*")
            if path.is_file()
        ]
    )

    if documents:

        for path in documents:

            relative = path.relative_to(
                DOCUMENT_DIR
            )

            st.text(f"📄 {relative}")

    else:

        st.info(
            "No documents indexed yet."
        )


    st.divider()

    if st.button(
        "Force Reindex",
        use_container_width=True,
    ):

        with st.spinner(
            "Rebuilding index..."
        ):

            rag.force_reindex()

        st.success(
            "Index rebuilt."
        )


    if st.button(
        "Clear Chat",
        use_container_width=True,
    ):

        st.session_state.messages = []

        st.rerun()


    st.divider()

    st.subheader("RAG Stats")

    st.metric(
        "Documents",
        len(rag.manifest),
    )

    st.metric(
        "Chunks",
        len(rag.chunks),
    )

    if rag.index is not None:

        st.metric(
            "FAISS vectors",
            rag.index.ntotal,
        )


    ocr_chunks = sum(
        1
        for chunk in rag.chunks
        if chunk.get(
            "extraction_method"
        )
        == "ocr"
    )

    st.metric(
        "OCR chunks",
        ocr_chunks,
    )


# ============================================================
# CHAT HISTORY
# ============================================================

for message in (
    st.session_state.messages
):

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )

        if (
            message["role"]
            == "assistant"
            and message.get("sources")
        ):

            with st.expander(
                "Retrieved sources"
            ):

                for index, source in enumerate(
                    message["sources"],
                    start=1,
                ):

                    st.markdown(
                        f"**SOURCE {index}**"
                    )

                    st.write(
                        f"File: "
                        f"{source['source']}"
                    )

                    if (
                        source.get("page")
                        is not None
                    ):

                        st.write(
                            f"Page: "
                            f"{source['page']}"
                        )

                    st.write(
                        f"Chunk: "
                        f"{source['chunk']}"
                    )

                    st.write(
                        "Extraction: "
                        f"{source.get('extraction_method', 'native')}"
                    )

                    st.write(
                        "Hybrid score: "
                        f"{source['hybrid_score']:.5f}"
                    )

                    st.code(
                        source["text"],
                        language=None,
                    )

                    st.divider()


# ============================================================
# CHAT INPUT
# ============================================================

question = st.chat_input(
    "Ask a question about your documents..."
)


if question:

    st.session_state.messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.chat_message("user"):

        st.markdown(question)


    with st.chat_message(
        "assistant"
    ):

        with st.spinner(
            "Searching local knowledge base..."
        ):

            try:

                answer, results = (
                    rag.ask(question)
                )

            except Exception as exc:

                st.error(
                    f"RAG error: {exc}"
                )

                st.stop()


        st.markdown(answer)


        if results:

            with st.expander(
                "Retrieved sources"
            ):

                for index, result in enumerate(
                    results,
                    start=1,
                ):

                    st.markdown(
                        f"### SOURCE {index}"
                    )

                    st.write(
                        f"**File:** "
                        f"{result['source']}"
                    )

                    if (
                        result.get("page")
                        is not None
                    ):

                        st.write(
                            f"**Page:** "
                            f"{result['page']}"
                        )

                    st.write(
                        f"**Chunk:** "
                        f"{result['chunk']}"
                    )

                    st.write(
                        "**Extraction:** "
                        f"{result.get('extraction_method', 'native')}"
                    )

                    st.write(
                        "**Vector rank:** "
                        f"{result.get('vector_rank')}"
                    )

                    st.write(
                        "**BM25 rank:** "
                        f"{result.get('bm25_rank')}"
                    )

                    st.write(
                        "**Hybrid score:** "
                        f"{result['hybrid_score']:.5f}"
                    )

                    st.code(
                        result["text"],
                        language=None,
                    )

                    st.divider()


    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": results,
        }
    )
