const API_BASE_URL = "http://127.0.0.1:8000";


// ----------------------------------------
// Elements
// ----------------------------------------

const fileInput =
    document.getElementById("fileInput");

const selectedFiles =
    document.getElementById("selectedFiles");

const websiteUrl =
    document.getElementById("websiteUrl");

const processButton =
    document.getElementById("processButton");

const processingStatus =
    document.getElementById("processingStatus");

const connectionStatus =
    document.getElementById("connectionStatus");

const questionInput =
    document.getElementById("questionInput");

const askButton =
    document.getElementById("askButton");

const chatMessages =
    document.getElementById("chatMessages");


// ----------------------------------------
// Backend health check
// ----------------------------------------

async function checkBackend() {

    try {

        const response = await fetch(
            `${API_BASE_URL}/api/health`
        );

        if (!response.ok) {
            throw new Error(
                "Backend unavailable"
            );
        }

        const data =
            await response.json();

        if (data.status === "ok") {

            connectionStatus.textContent =
                "● Backend connected";

            connectionStatus.style.color =
                "#16a34a";

        }

    } catch (error) {

        connectionStatus.textContent =
            "● Backend unavailable";

        connectionStatus.style.color =
            "#dc2626";
    }
}


// ----------------------------------------
// Display selected files
// ----------------------------------------

fileInput.addEventListener(
    "change",
    () => {

        const files =
            Array.from(
                fileInput.files
            );

        if (files.length === 0) {

            selectedFiles.textContent =
                "No files selected.";

            return;
        }

        selectedFiles.innerHTML =
            files
                .map(
                    file =>
                        `<div>• ${escapeHtml(file.name)}</div>`
                )
                .join("");
    }
);


// ----------------------------------------
// Process knowledge
// ----------------------------------------

processButton.addEventListener(
    "click",
    async () => {

        const files =
            Array.from(
                fileInput.files
            );

        const url =
            websiteUrl.value.trim();


        if (
            files.length === 0 &&
            !url
        ) {

            processingStatus.textContent =
                "Please select files or enter a website URL.";

            processingStatus.style.color =
                "#dc2626";

            return;
        }


        processButton.disabled = true;

        processingStatus.textContent =
            "Processing knowledge sources...";

        processingStatus.style.color =
            "#6b7280";


        try {

            const formData =
                new FormData();


            for (const file of files) {

                formData.append(
                    "files",
                    file
                );
            }


            if (url) {

                formData.append(
                    "urls",
                    url
                );
            }


            const response =
                await fetch(
                    `${API_BASE_URL}/api/knowledge/process`,
                    {
                        method: "POST",
                        body: formData
                    }
                );


            const data =
                await response.json();


            if (
                !response.ok ||
                data.status !== "success"
            ) {

                throw new Error(
                    data.message ||
                    "Knowledge processing failed."
                );
            }


            processingStatus.textContent =
                `Knowledge base ready. ` +
                `${data.documents_extracted} documents, ` +
                `${data.chunks_created} chunks.`;

            processingStatus.style.color =
                "#16a34a";


        } catch (error) {

            processingStatus.textContent =
                error.message;

            processingStatus.style.color =
                "#dc2626";

        } finally {

            processButton.disabled = false;
        }
    }
);


// ----------------------------------------
// Ask question
// ----------------------------------------

askButton.addEventListener(
    "click",
    askQuestion
);


questionInput.addEventListener(
    "keydown",
    event => {

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            askQuestion();
        }
    }
);


async function askQuestion() {

    const question =
        questionInput.value.trim();


    if (!question) {
        return;
    }


    addMessage(
        question,
        "user"
    );


    questionInput.value = "";

    askButton.disabled = true;


    const loadingMessage =
        addMessage(
            "Searching knowledge base...",
            "assistant"
        );


    try {

        const response =
            await fetch(
                `${API_BASE_URL}/api/chat`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        question: question
                    })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "Chat request failed."
            );
        }


        loadingMessage.remove();


        addAssistantMessage(
            data.answer,
            data.sources || []
        );


    } catch (error) {

        loadingMessage.textContent =
            `Error: ${error.message}`;

    } finally {

        askButton.disabled = false;

        questionInput.focus();
    }
}


// ----------------------------------------
// Add user/assistant message
// ----------------------------------------

function addMessage(
    text,
    type
) {

    const message =
        document.createElement(
            "div"
        );


    message.className =
        `message ${
            type === "user"
                ? "user-message"
                : "assistant-message"
        }`;


    message.textContent =
        text;


    chatMessages.appendChild(
        message
    );


    scrollChatToBottom();


    return message;
}


function addAssistantMessage(
    answer,
    sources
) {

    const message =
        document.createElement(
            "div"
        );


    message.className =
        "message assistant-message";


    const answerElement =
        document.createElement(
            "div"
        );


    answerElement.textContent =
        answer;


    message.appendChild(
        answerElement
    );


    if (sources.length > 0) {

        const sourcesContainer =
            document.createElement(
                "div"
            );


        sourcesContainer.className =
            "sources";


        const title =
            document.createElement(
                "div"
            );


        title.className =
            "sources-title";


        title.textContent =
            "Sources";


        sourcesContainer.appendChild(
            title
        );


        sources.forEach(
            source => {

                const sourceElement =
                    document.createElement(
                        "div"
                    );


                sourceElement.className =
                    "source";


                sourceElement.textContent =
                    formatSource(
                        source
                    );


                sourcesContainer.appendChild(
                    sourceElement
                );
            }
        );


        message.appendChild(
            sourcesContainer
        );
    }


    chatMessages.appendChild(
        message
    );


    scrollChatToBottom();
}


// ----------------------------------------
// Source formatting
// ----------------------------------------

function formatSource(
    metadata
) {

    const source =
        metadata.source ||
        "Unknown source";


    const fileType =
        metadata.file_type ||
        "";


    if (fileType === "pdf") {

        return `${getFilename(source)} — Page ${
            metadata.page ?? "Unknown"
        }`;
    }


    if (fileType === "docx") {

        return `${getFilename(source)} — Paragraph ${
            metadata.paragraph ?? "Unknown"
        }`;
    }


    if (fileType === "audio") {

        return `${getFilename(source)} — ${
            formatTimestamp(
                metadata.start_time
            )
        }–${
            formatTimestamp(
                metadata.end_time
            )
        }`;
    }


    if (fileType === "video") {

        return `${getFilename(source)} — ${
            formatTimestamp(
                metadata.start_time ??
                metadata.timestamp
            )
        }`;
    }


    if (fileType === "web") {

        return metadata.url ||
            source;
    }


    return getFilename(source);
}


function getFilename(
    path
) {

    return path
        .split("/")
        .pop()
        .split("\\")
        .pop();
}


function formatTimestamp(
    seconds
) {

    if (
        seconds === undefined ||
        seconds === null
    ) {

        return "Unknown time";
    }


    const totalSeconds =
        Math.floor(
            Number(seconds)
        );


    const minutes =
        Math.floor(
            totalSeconds / 60
        );


    const remaining =
        totalSeconds % 60;


    return `${String(minutes).padStart(2, "0")}:${
        String(remaining).padStart(2, "0")
    }`;
}


// ----------------------------------------
// Security helper
// ----------------------------------------

function escapeHtml(
    value
) {

    const div =
        document.createElement(
            "div"
        );

    div.textContent =
        value;

    return div.innerHTML;
}


// ----------------------------------------
// Chat scroll
// ----------------------------------------

function scrollChatToBottom() {

    chatMessages.scrollTop =
        chatMessages.scrollHeight;
}


// ----------------------------------------
// Start
// ----------------------------------------

checkBackend();