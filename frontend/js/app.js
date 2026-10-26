// The backend serves this page, so the API is on the same origin. Only
// when the page is opened as a file or from VS Code Live Server (5500)
// fall back to the default local backend.
const API_BASE_URL =
    window.location.protocol === "file:" || ["5500", "5501"].includes(window.location.port)
        ? "http://127.0.0.1:8000"
        : "";

const TOKEN_KEY = "rag_token";
const THEME_KEY = "rag_theme";
const POLL_MS = 2000;


// ----------------------------------------
// Helpers
// ----------------------------------------

const $ = id => document.getElementById(id);

const ICONS = {
    upload: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
    pdf: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    docx: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 12h6M9 16h6"/>',
    text: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 12h6M9 16h6"/>',
    excel: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 10h16M4 15h16M10 4v16"/>',
    csv: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 10h16M4 15h16M10 4v16"/>',
    image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/>',
    audio: '<path d="M9 18V6l11-2v12"/><circle cx="6" cy="18" r="3"/><circle cx="17" cy="16" r="3"/>',
    video: '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3"/>',
    web: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    html: '<path d="m8 8-4 4 4 4M16 8l4 4-4 4M14 5l-4 14"/>',
    file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>',
    retry: '<path d="M4 12a8 8 0 0 1 14-5.3L20 9M20 4v5h-5M20 12a8 8 0 0 1-14 5.3L4 15M4 20v-5h5"/>',
    send: '<path d="M12 19V5M5 12l7-7 7 7"/>',
    stop: '<rect x="7" y="7" width="10" height="10" rx="1.5" fill="currentColor"/>',
    close: '<path d="M6 6l12 12M18 6 6 18"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    logout: '<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H3"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
    check: '<path d="m5 12 5 5 9-10"/>',
    alert: '<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/>',
    external: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    tfs: '<rect x="4" y="4" width="16" height="17" rx="2"/><path d="M9 4V3h6v1M8 10h8M8 14h8M8 18h5"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    refresh: '<path d="M4 12a8 8 0 0 1 14-5.3L20 9M20 4v5h-5M20 12a8 8 0 0 1-14 5.3L4 15M4 20v-5h5"/>',
    youtube: '<rect x="2.5" y="5" width="19" height="14" rx="4"/><path d="m10 9 5 3-5 3z" fill="currentColor"/>',
    chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
    library: '<path d="M4 19V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1zM10 19V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-3a1 1 0 0 1-1-1z"/><path d="m16.5 5.5 3 .8a1 1 0 0 1 .7 1.2l-3.3 12.2"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    chevron: '<path d="m7 10 5 5 5-5"/>'
};

function icon(name, size = 16) {
    return `<svg class="icon" viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true">${ICONS[name] || ICONS.file}</svg>`;
}

function escapeHtml(value) {
    return Markdown.escapeHtml(String(value ?? ""));
}

function formatBytes(bytes) {
    if (!bytes) return "";
    const units = ["B", "KB", "MB", "GB"];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
        value /= 1024;
        unit++;
    }
    return `${value.toFixed(value < 10 && unit ? 1 : 0)} ${units[unit]}`;
}

function toast(message, type = "info") {
    const element = document.createElement("div");
    element.className = `toast ${type}`;
    element.innerHTML = `${icon(type === "error" ? "alert" : "check")}<div>${escapeHtml(message)}</div>`;
    $("toasts").appendChild(element);
    setTimeout(() => element.remove(), type === "error" ? 6000 : 3500);
}

function storage(action, key, value) {
    try {
        if (action === "get") return localStorage.getItem(key);
        if (action === "set") localStorage.setItem(key, value);
        if (action === "remove") localStorage.removeItem(key);
    } catch (error) {
        return null;
    }
    return null;
}

function setIcons() {
    document.querySelectorAll("[data-icon]").forEach(el => {
        el.innerHTML = icon(el.dataset.icon, 18);
    });
    $("sidebarClose").innerHTML = icon("close");
    $("sidebarOpen").innerHTML = icon("menu", 18);
    $("settingsButton").innerHTML = icon("settings");
    $("logoutButton").innerHTML = icon("logout");
    $("previewClose").innerHTML = icon("close");
    document.querySelectorAll(".modal-header [data-close]").forEach(el => {
        el.innerHTML = icon("close");
    });
    setSendState(false);
    updateThemeIcon();
}


// ----------------------------------------
// API
// ----------------------------------------

class ApiError extends Error {}

async function api(path, options = {}) {

    const headers = new Headers(options.headers || {});
    const token = storage("get", TOKEN_KEY);

    if (token) headers.set("Authorization", `Bearer ${token}`);

    if (options.json !== undefined) {
        headers.set("Content-Type", "application/json");
        options = { ...options, body: JSON.stringify(options.json) };
    }

    let response;

    try {
        response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
    } catch (error) {
        if (error.name === "AbortError") throw error;
        setConnection(false);
        throw new ApiError("Cannot reach the server.");
    }

    setConnection(true);

    // A 401 from login/register is a wrong password, not an expired session.
    if (response.status === 401 && !/^\/api\/auth\/(login|register)/.test(path)) {
        signOut("Your session expired. Please sign in again.");
        throw new ApiError("Please sign in again.");
    }

    if (!response.ok) {
        let detail = `Request failed (${response.status}).`;
        try {
            const data = await response.json();
            if (typeof data.detail === "string") detail = data.detail;
            else if (Array.isArray(data.detail)) detail = data.detail.map(d => d.msg).join(" ");
        } catch (error) { /* not JSON */ }
        throw new ApiError(detail);
    }

    return options.raw ? response : response.json();
}

function setConnection(ok) {
    const el = $("connection");
    el.className = `connection ${ok ? "ok" : "down"}`;
    el.title = ok ? "Connected" : "Server unreachable";
}


// ----------------------------------------
// Theme
// ----------------------------------------

function currentTheme() {
    return document.documentElement.dataset.theme ||
        (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}

function updateThemeIcon() {
    $("themeToggle").innerHTML = icon(currentTheme() === "dark" ? "sun" : "moon");
}

$("themeToggle").addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    storage("set", THEME_KEY, next);
    updateThemeIcon();
});


// ----------------------------------------
// Auth
// ----------------------------------------

let registerMode = false;

function setAuthMode(register) {
    registerMode = register;
    $("authTitle").textContent = register ? "Create your account" : "Welcome back";
    $("authSubtitle").textContent = register
        ? "Start building your knowledge workspace"
        : "Sign in to your knowledge workspace";
    $("authSubmit").textContent = register ? "Create account" : "Sign in";
    $("authSwitchText").textContent = register ? "Already have an account?" : "Don't have an account?";
    $("authToggle").textContent = register ? "Sign in" : "Create one";
    $("authPassword").autocomplete = register ? "new-password" : "current-password";
    $("authHint").hidden = !register;
    $("authError").textContent = "";
}

$("authToggle").addEventListener("click", () => setAuthMode(!registerMode));

$("authForm").addEventListener("submit", async event => {

    event.preventDefault();

    const username = $("authUsername").value.trim();
    const password = $("authPassword").value;

    if (!username || !password) {
        $("authError").textContent = "Enter your username and password.";
        return;
    }

    $("authSubmit").disabled = true;
    $("authError").textContent = "";

    try {
        const data = await api(`/api/auth/${registerMode ? "register" : "login"}`, {
            method: "POST",
            json: { username, password }
        });

        storage("set", TOKEN_KEY, data.access_token);
        await enterApp(data.user);

    } catch (error) {
        $("authError").textContent = error.message;
        const card = $("authForm");
        card.classList.remove("shake");
        void card.offsetWidth; // restart the animation
        card.classList.add("shake");
    } finally {
        $("authSubmit").disabled = false;
    }
});

function showAuth(message = "") {
    $("appView").hidden = true;
    $("authView").hidden = false;
    $("authError").textContent = message;
    $("authPassword").value = "";
    $("authUsername").focus();
    startAuthAnimation();
}

function signOut(message = "") {
    storage("remove", TOKEN_KEY);
    stopPolling();
    abortStream();
    closePreview();
    closeScopeMenu();
    state.sources = [];
    state.conversations = [];
    state.conversationId = null;
    state.scope = [];
    resetMessages();
    showAuth(message);
}

$("logoutButton").addEventListener("click", () => signOut());


// ----------------------------------------
// Login page animation
// ----------------------------------------

const ROTATING_WORDS = ["documents", "spreadsheets", "meetings", "videos", "YouTube", "websites", "images"];

const FLOATER_TYPES = [
    ["pdf", "#dc2626"], ["excel", "#16a34a"], ["video", "#7c3aed"], ["audio", "#c026d3"],
    ["image", "#d97706"], ["web", "#0891b2"], ["youtube", "#ef4444"], ["docx", "#2563eb"]
];

const authAnimation = { timer: null, started: false };

function startAuthAnimation() {

    if (authAnimation.started) return;
    authAnimation.started = true;

    const floaters = $("authFloaters");
    floaters.innerHTML = "";

    // Spread icons across the width with varied speed, size and delay.
    for (let i = 0; i < 10; i++) {
        const [type, tone] = FLOATER_TYPES[i % FLOATER_TYPES.length];
        const el = document.createElement("span");
        el.className = "floater";
        el.style.setProperty("--tone", tone);
        el.style.left = `${(i * 9.7 + (i % 3) * 3.1) % 96}%`;
        el.style.animationDuration = `${16 + (i * 3.7) % 14}s`;
        el.style.animationDelay = `-${(i * 2.9) % 18}s`;
        el.style.transform = `scale(${0.75 + (i % 4) * 0.12})`;
        el.innerHTML = icon(type);
        floaters.appendChild(el);
    }

    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let index = 0;
    const word = $("authRotator");

    authAnimation.timer = setInterval(() => {
        if ($("authView").hidden) return;
        word.classList.remove("swap-in");
        word.classList.add("swap-out");
        setTimeout(() => {
            index = (index + 1) % ROTATING_WORDS.length;
            word.textContent = ROTATING_WORDS[index];
            word.classList.remove("swap-out");
            word.classList.add("swap-in");
        }, 320);
    }, 2400);
}


// ----------------------------------------
// State
// ----------------------------------------

const state = {
    user: null,
    sources: [],
    uploads: [],
    library: null,
    settings: null,
    pollTimer: null,
    streaming: null,
    conversations: [],
    conversationId: null,
    // Source ids the current chat is limited to; empty = whole library.
    scope: []
};


// ----------------------------------------
// Library
// ----------------------------------------

function typeLabel(source) {
    return {
        pdf: "PDF", docx: "Word", excel: "Excel", csv: "CSV", image: "Image",
        audio: "Audio", video: "Video", web: "Website", html: "HTML", text: "Text",
        youtube: "YouTube", tfs: "TFS"
    }[source.file_type] || source.file_type.toUpperCase();
}

function statusText(source) {
    if (source.status === "ready") {
        const parts = [typeLabel(source), `${source.chunk_count} chunk${source.chunk_count === 1 ? "" : "s"}`];
        if (source.size_bytes) parts.push(formatBytes(source.size_bytes));
        return parts.join(" · ");
    }
    if (source.status === "failed") return source.error || "Failed";
    if (source.status === "queued") return "Waiting…";
    return source.progress || "Processing…";
}

// Link sources can be re-fetched to pick up changes (e.g. new TFS tickets).
const REFRESHABLE = new Set(["url", "tfs", "youtube"]);

function renderSources() {

    const list = $("sourceList");
    const items = [...state.uploads, ...state.sources];

    $("libraryCount").textContent = state.sources.length;
    $("libraryEmpty").hidden = items.length > 0;

    list.innerHTML = items.map(source => {

        const busy = ["queued", "processing", "uploading"].includes(source.status);
        const failed = source.status === "failed";
        const progressValue = source.status === "uploading" ? source.percent : null;

        return `
            <li class="source-item" data-id="${escapeHtml(source.id)}">
                <span class="type-icon" data-type="${escapeHtml(source.file_type)}">${icon(source.file_type)}</span>
                <div class="source-body">
                    <div class="source-name" title="${escapeHtml(source.name)}">${escapeHtml(source.name)}</div>
                    <div class="source-meta">
                        <span class="status-dot ${source.status}"></span>
                        <span class="${failed ? "error-text" : ""}" title="${escapeHtml(statusText(source))}">${escapeHtml(statusText(source))}</span>
                        ${source.has_auth ? `<span class="signed-in" title="Signed in with saved credentials">${icon("lock", 11)}</span>` : ""}
                    </div>
                    ${source.note ? `<div class="source-note">${escapeHtml(source.note)}</div>` : ""}
                    ${busy ? `<div class="progress-bar ${progressValue === null ? "indeterminate" : ""}"><span style="${progressValue !== null ? `width:${progressValue}%` : ""}"></span></div>` : ""}
                </div>
                ${source.status === "uploading" ? "" : `
                <div class="source-actions">
                    ${failed ? `<button class="icon-btn" data-action="retry" title="Retry" aria-label="Retry">${icon("retry", 14)}</button>` : ""}
                    ${source.status === "ready" && REFRESHABLE.has(source.kind) ? `<button class="icon-btn" data-action="retry" title="Refresh from source" aria-label="Refresh">${icon("refresh", 14)}</button>` : ""}
                    <button class="icon-btn" data-action="delete" title="Remove" aria-label="Remove">${icon("trash", 14)}</button>
                </div>`}
            </li>`;
    }).join("");

    renderReindexBanner();
}

function renderReindexBanner() {

    const banner = $("reindexBanner");
    const library = state.library;

    if (!library) {
        banner.hidden = true;
        return;
    }

    if (library.reindexing) {
        banner.hidden = false;
        banner.innerHTML = "Re-indexing your library with the new embedding model…";
        return;
    }

    if (library.reindex_error) {
        banner.hidden = false;
        banner.innerHTML = `Re-indexing failed: ${escapeHtml(library.reindex_error)}`;
        return;
    }

    if (library.reindex_suggested) {
        banner.hidden = false;
        banner.innerHTML =
            `Library is indexed with <strong>${escapeHtml(library.embedding)}</strong>. ` +
            `<button class="link" type="button" id="reindexButton">Re-index with ${escapeHtml(library.selected_embedding)}</button>`;
        $("reindexButton").addEventListener("click", reindex);
        return;
    }

    banner.hidden = true;
}

async function reindex() {
    try {
        state.library = await api("/api/library/reindex", { method: "POST" });
        renderReindexBanner();
        schedulePoll();
    } catch (error) {
        toast(error.message, "error");
    }
}

async function loadSources() {

    const data = await api("/api/sources");

    const previous = new Map(state.sources.map(source => [source.id, source.status]));

    state.sources = data.sources;
    state.library = data.library;

    for (const source of data.sources) {
        const before = previous.get(source.id);
        if (before && before !== source.status) {
            if (source.status === "ready") toast(`${source.name} is ready`, "success");
            if (source.status === "failed") toast(`${source.name}: ${source.error}`, "error");
        }
    }

    // Drop deleted sources from the chat's scope.
    const existing = new Set(state.sources.map(source => source.id));
    state.scope = state.scope.filter(id => existing.has(id));

    renderSources();
    renderScope();
    schedulePoll();
}

function needsPolling() {
    return state.library?.reindexing ||
        state.sources.some(source => ["queued", "processing"].includes(source.status));
}

function schedulePoll() {
    stopPolling();
    if (needsPolling()) {
        state.pollTimer = setTimeout(() => loadSources().catch(() => schedulePoll()), POLL_MS);
    }
}

function stopPolling() {
    clearTimeout(state.pollTimer);
    state.pollTimer = null;
}

function uploadFiles(files) {

    files = Array.from(files);

    if (!files.length) return;

    const allowed = new Set(state.library?.supported_extensions || []);
    const maxBytes = (state.library?.max_upload_mb || 500) * 1024 * 1024;

    const valid = files.filter(file => {
        const extension = "." + file.name.split(".").pop().toLowerCase();
        if (allowed.size && !allowed.has(extension)) {
            toast(`${file.name}: unsupported file type`, "error");
            return false;
        }
        if (file.size > maxBytes) {
            toast(`${file.name} is larger than ${state.library.max_upload_mb} MB`, "error");
            return false;
        }
        return true;
    });

    if (!valid.length) return;

    const form = new FormData();
    valid.forEach(file => form.append("files", file, file.name));

    const upload = {
        id: `upload-${Date.now()}`,
        name: valid.length === 1 ? valid[0].name : `${valid.length} files`,
        file_type: valid.length === 1 ? guessType(valid[0].name) : "file",
        status: "uploading",
        progress: "Uploading 0%",
        percent: 0
    };

    state.uploads.unshift(upload);
    renderSources();

    // XHR (not fetch) for upload progress events.
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/api/sources`);
    xhr.setRequestHeader("Authorization", `Bearer ${storage("get", TOKEN_KEY)}`);

    xhr.upload.onprogress = event => {
        if (event.lengthComputable) {
            upload.percent = Math.round(100 * event.loaded / event.total);
            upload.progress = upload.percent < 100 ? `Uploading ${upload.percent}%` : "Finishing upload…";
            renderSources();
        }
    };

    const finish = () => {
        state.uploads = state.uploads.filter(item => item !== upload);
        renderSources();
    };

    xhr.onload = () => {
        finish();
        if (xhr.status === 401) return signOut("Your session expired. Please sign in again.");
        if (xhr.status >= 400) {
            let message = "Upload failed.";
            try { message = JSON.parse(xhr.responseText).detail || message; } catch (error) {}
            return toast(message, "error");
        }
        loadSources().catch(error => toast(error.message, "error"));
    };

    xhr.onerror = () => {
        finish();
        toast("Upload failed. Check your connection.", "error");
    };

    xhr.send(form);
}

function guessType(name) {
    const extension = name.split(".").pop().toLowerCase();
    if (["png", "jpg", "jpeg", "webp", "gif", "bmp", "tif", "tiff"].includes(extension)) return "image";
    if (["mp3", "wav", "m4a", "aac", "flac", "ogg", "opus"].includes(extension)) return "audio";
    if (["mp4", "mov", "mkv", "webm", "avi", "m4v"].includes(extension)) return "video";
    if (["xlsx", "xlsm"].includes(extension)) return "excel";
    if (["html", "htm"].includes(extension)) return "html";
    if (["txt", "md"].includes(extension)) return "text";
    return extension;
}

const dropZone = $("dropZone");

dropZone.addEventListener("click", () => $("fileInput").click());
dropZone.addEventListener("keydown", event => {
    if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        $("fileInput").click();
    }
});

$("fileInput").addEventListener("change", event => {
    uploadFiles(event.target.files);
    event.target.value = "";
});

["dragenter", "dragover"].forEach(type => dropZone.addEventListener(type, event => {
    event.preventDefault();
    dropZone.classList.add("dragging");
}));

["dragleave", "drop"].forEach(type => dropZone.addEventListener(type, event => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
}));

dropZone.addEventListener("drop", event => uploadFiles(event.dataTransfer.files));

// Dropping anywhere else should not navigate away from the app.
window.addEventListener("dragover", event => event.preventDefault());
window.addEventListener("drop", event => event.preventDefault());

const YOUTUBE_LINK = /^https?:\/\/(www\.|m\.|music\.)?(youtube\.com|youtu\.be)\/\S+$/i;

function bindLinkForm(formId, inputId, field, validate, extend = () => "") {

    $(formId).addEventListener("submit", async event => {

        event.preventDefault();

        const input = $(inputId);
        const url = input.value.trim();
        const form = new FormData();
        const problem = validate(url) || extend(form);

        if (problem) {
            toast(problem, "error");
            return;
        }

        form.append(field, url);

        const button = $(formId).querySelector("button");
        button.disabled = true;

        try {
            await api("/api/sources", { method: "POST", body: form });
            input.value = "";
            $(formId).dispatchEvent(new Event("added"));
            await loadSources();
        } catch (error) {
            toast(error.message, "error");
        } finally {
            button.disabled = false;
        }
    });
}

const TFS_LINK = /^https?:\/\/([^/]+\.)?(dev\.azure\.com|visualstudio\.com)\/|\/tfs\/|\/_(workitems|boards|backlogs|queries|sprints)\b/i;

bindLinkForm(
    "urlForm",
    "urlInput",
    "urls",
    url => /^https?:\/\/\S+$/i.test(url) ? "" : "Enter a full URL starting with http:// or https://",
    form => {

        const enabled = $("siteAuthEnabled").checked;
        const username = $("siteUsername");
        const password = $("sitePassword");

        if (!enabled) {
            return TFS_LINK.test($("urlInput").value)
                ? "TFS / Azure DevOps needs sign-in. Turn on \"Requires sign-in\"."
                : "";
        }

        username.classList.toggle("invalid", !username.value.trim());
        password.classList.toggle("invalid", !password.value);

        if (!username.value.trim() || !password.value) {
            return "Username and password are required when sign-in is enabled.";
        }

        form.append("auth_enabled", "true");
        form.append("auth_username", username.value.trim());
        form.append("auth_password", password.value);
        return "";
    }
);

$("siteAuthEnabled").addEventListener("change", event => {
    $("siteAuthFields").hidden = !event.target.checked;
    if (event.target.checked) $("siteUsername").focus();
});

// Don't keep credentials in the form after they've been sent.
$("urlForm").addEventListener("added", () => {
    $("siteUsername").value = "";
    $("sitePassword").value = "";
    $("siteAuthEnabled").checked = false;
    $("siteAuthFields").hidden = true;
});

["siteUsername", "sitePassword"].forEach(id =>
    $(id).addEventListener("input", () => $(id).classList.remove("invalid"))
);

bindLinkForm("youtubeForm", "youtubeInput", "youtube", url =>
    YOUTUBE_LINK.test(url) ? "" : "Enter a YouTube video link, e.g. https://www.youtube.com/watch?v=…"
);

$("sourceList").addEventListener("click", async event => {

    const button = event.target.closest("[data-action]");
    if (!button) return;

    const id = button.closest(".source-item").dataset.id;
    const source = state.sources.find(item => item.id === id);
    if (!source) return;

    if (button.dataset.action === "retry") {
        try {
            await api(`/api/sources/${id}/retry`, { method: "POST" });
            await loadSources();
        } catch (error) {
            toast(error.message, "error");
        }
    }

    if (button.dataset.action === "delete") {
        const ok = await confirmDialog(
            "Remove source?",
            `"${source.name}" and its indexed content will be removed from your library.`
        );
        if (!ok) return;

        try {
            await api(`/api/sources/${id}`, { method: "DELETE" });
            await loadSources();
        } catch (error) {
            toast(error.message, "error");
        }
    }
});


// ----------------------------------------
// Sidebar tabs
// ----------------------------------------

function showTab(name) {
    document.querySelectorAll(".sidebar-tab").forEach(tab => {
        const active = tab.dataset.tab === name;
        tab.classList.toggle("active", active);
        tab.setAttribute("aria-selected", String(active));
    });
    $("chatsPanel").hidden = name !== "chats";
    $("libraryPanel").hidden = name !== "library";
    storage("set", "rag_tab", name);
}

document.querySelectorAll(".sidebar-tab").forEach(tab => {
    tab.addEventListener("click", () => showTab(tab.dataset.tab));
});


// ----------------------------------------
// Conversations
// ----------------------------------------

function parseServerTime(value) {
    // SQLite CURRENT_TIMESTAMP is UTC without a zone marker.
    return new Date(value.replace(" ", "T") + "Z");
}

function relativeTime(value) {
    const seconds = (Date.now() - parseServerTime(value)) / 1000;
    if (seconds < 60) return "just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return parseServerTime(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function conversationGroup(value) {
    const date = parseServerTime(value);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const days = (today - new Date(date.getFullYear(), date.getMonth(), date.getDate())) / 86400000;
    if (days <= 0) return "Today";
    if (days === 1) return "Yesterday";
    if (days < 7) return "Previous 7 days";
    if (days < 30) return "Previous 30 days";
    return "Older";
}

function renderConversations() {

    const list = $("conversationList");
    let group = null;
    let html = "";

    for (const conversation of state.conversations) {

        const label = conversationGroup(conversation.updated_at);

        if (label !== group) {
            group = label;
            html += `<li class="conversation-group">${label}</li>`;
        }

        const scoped = conversation.source_ids.length;

        html += `
            <li class="conversation-item ${conversation.id === state.conversationId ? "active" : ""}" data-id="${escapeHtml(conversation.id)}">
                <button class="conversation-open" type="button" title="${escapeHtml(conversation.title)}">
                    <span class="conversation-title">${escapeHtml(conversation.title)}</span>
                    <span class="conversation-meta">
                        <span>${relativeTime(conversation.updated_at)}</span>
                        ${scoped ? `<span>· ${scoped} source${scoped === 1 ? "" : "s"}</span>` : ""}
                    </span>
                </button>
                <div class="source-actions">
                    <button class="icon-btn" data-action="delete" title="Delete chat" aria-label="Delete chat">${icon("trash", 14)}</button>
                </div>
            </li>`;
    }

    list.innerHTML = html;
    $("chatCount").textContent = state.conversations.length;
    $("chatsEmpty").hidden = state.conversations.length > 0;
}

async function loadConversations() {
    state.conversations = (await api("/api/conversations")).conversations;
    renderConversations();
}

function upsertConversation(conversation) {
    state.conversations = [
        conversation,
        ...state.conversations.filter(item => item.id !== conversation.id)
    ];
    renderConversations();
}

function setChatTitle(title) {
    $("chatTitle").textContent = title || "New chat";
    document.title = title ? `${title} · Multimodal RAG` : "Multimodal RAG";
}

function newChat() {
    abortStream();
    closePreview();
    state.conversationId = null;
    state.scope = [];
    resetMessages();
    setChatTitle("");
    renderConversations();
    renderScope();
    setSidebar(false);
    questionInput.focus();
}

async function openConversation(id) {

    if (state.streaming) abortStream();

    try {
        const data = await api(`/api/conversations/${id}`);

        state.conversationId = data.id;
        state.scope = data.source_ids;

        closePreview();
        resetMessages();
        renderMessages(data.messages);
        setChatTitle(data.title);
        renderConversations();
        renderScope();
        setSidebar(false);

    } catch (error) {
        toast(error.message, "error");
    }
}

$("conversationList").addEventListener("click", async event => {

    const item = event.target.closest(".conversation-item");
    if (!item) return;

    const id = item.dataset.id;

    if (event.target.closest('[data-action="delete"]')) {

        const conversation = state.conversations.find(c => c.id === id);
        const ok = await confirmDialog(
            "Delete chat?",
            `"${conversation?.title || "This chat"}" and its messages will be permanently deleted.`
        );
        if (!ok) return;

        try {
            await api(`/api/conversations/${id}`, { method: "DELETE" });
            state.conversations = state.conversations.filter(c => c.id !== id);
            if (state.conversationId === id) newChat();
            renderConversations();
        } catch (error) {
            toast(error.message, "error");
        }
        return;
    }

    if (event.target.closest(".conversation-open") && id !== state.conversationId) {
        openConversation(id);
    }
});

$("newChatButton").addEventListener("click", newChat);


// ----------------------------------------
// Source scope ("search in")
// ----------------------------------------

function readySources() {
    return state.sources.filter(source => source.status === "ready");
}

function renderScope() {

    const button = $("scopeButton");
    const selected = state.sources.filter(source => state.scope.includes(source.id));

    let label = "All sources";

    if (selected.length === 1) label = selected[0].name;
    else if (selected.length > 1) label = `${selected.length} sources`;

    $("scopeLabel").textContent = label;
    button.classList.toggle("filtered", selected.length > 0);
    button.title = selected.length
        ? `Searching only: ${selected.map(source => source.name).join(", ")}`
        : "Searching your whole library. Click to choose sources.";

    if (!$("scopeMenu").hidden) renderScopeList();
}

function renderScopeList() {

    const filter = $("scopeFilter").value.trim().toLowerCase();
    const sources = readySources().filter(source => source.name.toLowerCase().includes(filter));

    $("scopeEmpty").hidden = sources.length > 0;
    $("scopeEmpty").textContent = readySources().length ? "No sources match." : "No ready sources yet.";

    $("scopeList").innerHTML = sources.map(source => `
        <li class="scope-item">
            <label>
                <input type="checkbox" value="${escapeHtml(source.id)}" ${state.scope.includes(source.id) ? "checked" : ""}>
                <span class="type-icon" data-type="${escapeHtml(source.file_type)}">${icon(source.file_type, 13)}</span>
                <span class="name" title="${escapeHtml(source.name)}">${escapeHtml(source.name)}</span>
            </label>
        </li>`).join("");
}

async function setScope(ids) {

    state.scope = ids;
    renderScope();

    // Existing chats remember their scope; a new chat saves it with the first question.
    if (state.conversationId) {
        try {
            const conversation = await api(`/api/conversations/${state.conversationId}`, {
                method: "PATCH",
                json: { source_ids: ids }
            });
            upsertConversationInPlace(conversation);
        } catch (error) {
            toast(error.message, "error");
        }
    }
}

function upsertConversationInPlace(conversation) {
    state.conversations = state.conversations.map(item =>
        item.id === conversation.id ? conversation : item
    );
    renderConversations();
}

function openScopeMenu() {
    $("scopeMenu").hidden = false;
    $("scopeButton").setAttribute("aria-expanded", "true");
    $("scopeFilter").value = "";
    renderScopeList();
    $("scopeFilter").focus();
}

function closeScopeMenu() {
    $("scopeMenu").hidden = true;
    $("scopeButton").setAttribute("aria-expanded", "false");
}

$("scopeButton").addEventListener("click", () => {
    if ($("scopeMenu").hidden) openScopeMenu();
    else closeScopeMenu();
});

$("scopeFilter").addEventListener("input", renderScopeList);

$("scopeList").addEventListener("change", event => {
    const ids = [...$("scopeList").querySelectorAll("input:checked")].map(input => input.value);
    // Keep selections hidden by the filter.
    const hidden = state.scope.filter(id => !$("scopeList").querySelector(`input[value="${CSS.escape(id)}"]`));
    setScope([...hidden, ...ids]);
});

$("scopeAll").addEventListener("click", () => {
    setScope([]);
    renderScopeList();
});

document.addEventListener("click", event => {
    if (!$("scopeMenu").hidden && !event.target.closest(".scope")) closeScopeMenu();
});


// ----------------------------------------
// Chat
// ----------------------------------------

const messagesEl = $("messages");
const emptyStateHtml = $("emptyState").outerHTML;
const questionInput = $("questionInput");

function resetMessages() {
    messagesEl.innerHTML = emptyStateHtml;
    bindSuggestions();
}

function bindSuggestions() {
    messagesEl.querySelectorAll(".suggestion").forEach(button => {
        button.addEventListener("click", () => {
            questionInput.value = button.textContent;
            ask();
        });
    });
}

function hideEmptyState() {
    $("emptyState")?.remove();
}

function scrollToBottom(force = false) {
    const nearBottom = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 160;
    if (force || nearBottom) messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addUserMessage(text) {
    hideEmptyState();
    const element = document.createElement("div");
    element.className = "message user";
    element.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
    messagesEl.appendChild(element);
    scrollToBottom(true);
}

function addAssistantMessage() {

    hideEmptyState();

    const element = document.createElement("div");
    element.className = "message assistant";
    element.innerHTML = `
        <div class="brand-mark assistant-avatar" aria-hidden="true">M</div>
        <div class="answer">
            <div class="answer-body"><div class="typing"><span></span><span></span><span></span><em>Searching your library…</em></div></div>
            <div class="source-cards"></div>
            <div class="answer-actions" hidden>
                <button class="icon-btn" data-copy title="Copy answer" aria-label="Copy answer">${icon("copy", 14)}</button>
            </div>
        </div>`;

    messagesEl.appendChild(element);
    scrollToBottom(true);

    const view = {
        element,
        body: element.querySelector(".answer-body"),
        cards: element.querySelector(".source-cards"),
        actions: element.querySelector(".answer-actions"),
        text: "",
        sources: []
    };

    element.querySelector("[data-copy]").addEventListener("click", async event => {
        try {
            await navigator.clipboard.writeText(view.text);
            event.currentTarget.innerHTML = icon("check", 14);
        } catch (error) {
            toast("Could not copy to clipboard.", "error");
        }
    });

    return view;
}

function renderAnswer(view, done = false) {

    view.body.innerHTML = Markdown.render(view.text, view.sources.length);

    view.body.querySelectorAll(".cite").forEach(button => {
        const source = view.sources[Number(button.dataset.cite) - 1];
        if (source) {
            button.title = `${source.name}${source.location ? " — " + source.location : ""}`;
            button.addEventListener("click", () => openPreview(source));
        }
    });

    if (done) {
        view.actions.hidden = !view.text;
        view.element.querySelector(".answer").classList.toggle(
            "abstain",
            view.sources.length === 0
        );
    }
}

function renderSourceCards(view) {

    // Only show sources the answer actually cites, when it cites any.
    const cited = new Set([...view.text.matchAll(/\[(\d+(?:\s*,\s*\d+)*)\]/g)]
        .flatMap(match => match[1].split(",").map(n => Number(n.trim()))));

    const shown = cited.size
        ? view.sources.filter(source => cited.has(source.n))
        : view.sources;

    view.cards.innerHTML = "";

    for (const source of shown) {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "source-card";
        card.title = `${source.name}${source.location ? " — " + source.location : ""}`;
        card.innerHTML = `
            <span class="n">${source.n}</span>
            <span class="type-icon" data-type="${escapeHtml(source.file_type)}" style="width:20px;height:20px;border-radius:5px">${icon(source.file_type, 12)}</span>
            <span class="label">${escapeHtml(source.name)}</span>
            ${source.location ? `<span class="loc">${escapeHtml(source.location)}</span>` : ""}`;
        card.addEventListener("click", () => openPreview(source));
        view.cards.appendChild(card);
    }
}

function setSendState(streaming) {
    const button = $("sendButton");
    button.classList.toggle("stop", streaming);
    button.innerHTML = icon(streaming ? "stop" : "send", 18);
    button.setAttribute("aria-label", streaming ? "Stop" : "Send");
    button.disabled = !streaming && !questionInput.value.trim();
}

function abortStream() {
    if (state.streaming) {
        state.streaming.abort();
        state.streaming = null;
    }
}

async function ask() {

    const question = questionInput.value.trim();

    if (!question || state.streaming) return;

    questionInput.value = "";
    autosize();

    addUserMessage(question);

    const view = addAssistantMessage();
    const controller = new AbortController();

    state.streaming = controller;
    setSendState(true);

    try {
        const response = await api("/api/chat/stream", {
            method: "POST",
            json: {
                question,
                conversation_id: state.conversationId,
                source_ids: state.scope
            },
            signal: controller.signal,
            raw: true
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let started = false;

        while (true) {

            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            let newline;

            while ((newline = buffer.indexOf("\n")) >= 0) {

                const line = buffer.slice(0, newline).trim();
                buffer = buffer.slice(newline + 1);

                if (!line) continue;

                const event = JSON.parse(line);

                if (event.type === "conversation") {
                    state.conversationId = event.conversation.id;
                    setChatTitle(event.conversation.title);
                    upsertConversation(event.conversation);
                }

                if (event.type === "sources") {
                    view.sources = event.sources;
                    if (event.sources.length) {
                        view.body.innerHTML =
                            `<div class="typing"><span></span><span></span><span></span><em>Reading ${event.sources.length} passage${event.sources.length === 1 ? "" : "s"}…</em></div>`;
                    }
                }

                if (event.type === "token") {
                    started = true;
                    view.text += event.text;
                    renderAnswer(view);
                    scrollToBottom();
                }

                if (event.type === "done") {
                    view.text = event.answer || view.text;
                    if (event.sources) view.sources = event.sources;
                    renderAnswer(view, true);
                    renderSourceCards(view);
                }

                if (event.type === "error") {
                    throw new ApiError(event.message);
                }
            }
        }

        if (!started && !view.text) {
            view.text = "No answer was returned.";
            renderAnswer(view, true);
        }

    } catch (error) {

        if (error.name === "AbortError") {
            renderAnswer(view, true);
            renderSourceCards(view);
            if (!view.text) view.body.innerHTML = '<span class="muted">Stopped.</span>';
        } else {
            view.element.querySelector(".answer").classList.add("error");
            view.body.textContent = error.message;
        }

    } finally {
        // A newer chat may already be streaming if the user switched away.
        if (state.streaming === controller) state.streaming = null;
        setSendState(Boolean(state.streaming));
        scrollToBottom();
        questionInput.focus();
        // Refresh "updated" times and ordering.
        loadConversations().catch(() => {});
    }
}

function autosize() {
    questionInput.style.height = "auto";
    questionInput.style.height = `${Math.min(questionInput.scrollHeight, 200)}px`;
    if (!state.streaming) setSendState(false);
}

questionInput.addEventListener("input", autosize);

questionInput.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        ask();
    }
});

$("composer").addEventListener("submit", event => {
    event.preventDefault();
    if (state.streaming) abortStream();
    else ask();
});

$("clearChat").addEventListener("click", newChat);

function renderMessages(messages) {

    if (!messages.length) return;

    hideEmptyState();

    for (const message of messages) {

        if (message.role === "user") {
            addUserMessage(message.content);
            continue;
        }

        const view = addAssistantMessage();
        view.text = message.content;
        view.sources = message.sources || [];
        renderAnswer(view, true);
        renderSourceCards(view);
    }

    scrollToBottom(true);
}


// ----------------------------------------
// Source preview
// ----------------------------------------

async function openPreview(source) {

    $("previewPanel").hidden = false;
    $("previewIcon").dataset.type = source.file_type;
    $("previewIcon").innerHTML = icon(source.file_type);
    $("previewName").textContent = source.name;
    $("previewLocation").textContent = source.location || "";
    $("previewText").textContent = source.snippet || "";
    $("previewMedia").innerHTML = "";
    $("previewActions").innerHTML = "";

    if (!source.source_id) return;

    let link;

    try {
        link = await api(`/api/sources/${source.source_id}/link`);
    } catch (error) {
        $("previewActions").innerHTML = `<span class="muted small">${escapeHtml(error.message)}</span>`;
        return;
    }

    const url = link.url.startsWith("/") ? `${API_BASE_URL}${link.url}` : link.url;
    const media = $("previewMedia");

    if (source.file_type === "youtube" && link.youtube_id) {

        const start = Math.floor(Number(source.start_time) || 0);
        const frame = document.createElement("iframe");
        frame.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(link.youtube_id)}?start=${start}&rel=0`;
        frame.title = source.name;
        frame.allow = "accelerometer; autoplay; encrypted-media; picture-in-picture";
        frame.allowFullscreen = true;
        frame.referrerPolicy = "strict-origin-when-cross-origin";
        media.appendChild(frame);

        const anchor = document.createElement("a");
        anchor.className = "btn btn-secondary";
        anchor.href = `https://www.youtube.com/watch?v=${encodeURIComponent(link.youtube_id)}&t=${start}s`;
        anchor.target = "_blank";
        anchor.rel = "noopener noreferrer";
        anchor.innerHTML = `${icon("external", 14)}<span>Open on YouTube</span>`;
        $("previewActions").appendChild(anchor);
        return;
    }

    if (source.file_type === "video" || source.file_type === "audio") {
        const player = document.createElement(source.file_type);
        player.controls = true;
        player.preload = "auto";
        player.src = url;
        // Seeking (even to ~0) makes the browser paint the cited frame
        // instead of a black box.
        player.addEventListener("loadedmetadata", () => {
            player.currentTime = Math.max(Number(source.start_time) || 0, 0.05);
        }, { once: true });
        media.appendChild(player);
    }

    if (source.file_type === "image") {
        const image = document.createElement("img");
        image.alt = source.name;
        image.src = url;
        media.appendChild(image);
    }

    let target = source.file_type === "pdf" && source.page ? `${url}#page=${source.page}` : url;

    // TFS citations link to the exact ticket.
    if (source.file_type === "tfs" && source.url) target = source.url;

    const label = { web: "Open website", tfs: "Open in TFS" }[source.file_type] || "Open original";

    const anchor = document.createElement("a");
    anchor.className = "btn btn-secondary";
    anchor.href = target;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    anchor.innerHTML = `${icon("external", 14)}<span>${label}</span>`;
    $("previewActions").appendChild(anchor);
}

function closePreview() {
    $("previewPanel").hidden = true;
    $("previewMedia").innerHTML = "";
}

$("previewClose").addEventListener("click", closePreview);


// ----------------------------------------
// Modals
// ----------------------------------------

function openModal(id) {
    $(id).hidden = false;
    const body = $(id).querySelector(".modal-body");
    if (body) body.scrollTop = 0;
    $(id).querySelector(".modal-card").focus({ preventScroll: true });
}

function closeModal(id) {
    $(id).hidden = true;
}

document.querySelectorAll(".modal").forEach(modal => {
    modal.addEventListener("click", event => {
        if (event.target.closest("[data-close]")) closeModal(modal.id);
    });
});

document.addEventListener("keydown", event => {
    if (event.key !== "Escape") return;
    const open = [...document.querySelectorAll(".modal")].find(modal => !modal.hidden);
    // Go through the Cancel button so a pending confirm() resolves.
    if (open) open.querySelector(".modal-footer [data-close], [data-close]").click();
    else if (!$("scopeMenu").hidden) closeScopeMenu();
    else if (!$("previewPanel").hidden) closePreview();
});

function confirmDialog(title, text) {

    return new Promise(resolve => {

        $("confirmTitle").textContent = title;
        $("confirmText").textContent = text;
        openModal("confirmModal");

        const modal = $("confirmModal");

        const cleanup = result => {
            modal.removeEventListener("click", onClick);
            $("confirmOk").removeEventListener("click", onOk);
            closeModal("confirmModal");
            resolve(result);
        };

        const onOk = () => cleanup(true);
        const onClick = event => {
            if (event.target.closest("[data-close]")) cleanup(false);
        };

        $("confirmOk").addEventListener("click", onOk);
        modal.addEventListener("click", onClick);
        $("confirmOk").focus();
    });
}


// ----------------------------------------
// Settings
// ----------------------------------------

const settingsForm = $("settingsForm");

function field(name) {
    return settingsForm.elements[name];
}

function radioValue(name) {
    return settingsForm.querySelector(`input[name="${name}"]:checked`)?.value;
}

function updateModelPlaceholders() {

    const defaults = state.settings?.defaults;
    if (!defaults) return;

    const llm = radioValue("llm_provider");
    const embedding = radioValue("embedding_provider");

    field("llm_model").placeholder = defaults.llm[llm];
    field("vision_model").placeholder = defaults.vision[llm];
    field("embedding_model").placeholder = defaults.embedding[embedding];

    const key = state.settings.openai_key;
    const usesOpenAI = llm === "openai" || embedding === "openai";

    $("openaiGroup").style.opacity = usesOpenAI ? "1" : "0.6";
    $("openaiKeyStatus").textContent = key.saved
        ? `A key ending in ${key.hint.replace("…", "")} is saved (encrypted). Enter a new one to replace it.`
        : key.server
            ? "No personal key saved. The server's default key will be used."
            : usesOpenAI
                ? "Required for OpenAI. Stored encrypted and never shown again."
                : "Only needed if you choose OpenAI.";
    $("removeKey").hidden = !key.saved;
}

function fillSettings(data) {

    state.settings = data;

    const saved = data.settings;
    const effective = data.effective;

    settingsForm.querySelector(`input[name="llm_provider"][value="${effective.llm_provider}"]`).checked = true;
    settingsForm.querySelector(`input[name="embedding_provider"][value="${effective.embedding_provider}"]`).checked = true;

    // Empty field = use the provider's default (shown as placeholder).
    field("llm_model").value = saved.llm_model || "";
    field("embedding_model").value = saved.embedding_model || "";
    field("vision_model").value = saved.vision_model || "";
    field("vision_enabled").checked = effective.vision_enabled;
    field("openai_base_url").value = saved.openai_base_url || "";
    field("openai_api_key").value = "";

    $("testResults").hidden = true;
    $("settingsError").textContent = "";

    updateModelPlaceholders();
    updateModelBadge();
}

function updateModelBadge() {
    const effective = state.settings?.effective;
    if (!effective) return;
    $("modelBadge").textContent = `${effective.llm_provider === "openai" ? "OpenAI" : "Ollama"} · ${effective.llm_model}`;
}

function settingsPayload() {
    const payload = {
        llm_provider: radioValue("llm_provider"),
        llm_model: field("llm_model").value.trim(),
        embedding_provider: radioValue("embedding_provider"),
        embedding_model: field("embedding_model").value.trim(),
        vision_enabled: field("vision_enabled").checked,
        vision_model: field("vision_model").value.trim(),
        openai_base_url: field("openai_base_url").value.trim()
    };

    const key = field("openai_api_key").value.trim();
    if (key) payload.openai_api_key = key;

    return payload;
}

settingsForm.addEventListener("change", event => {
    if (["llm_provider", "embedding_provider"].includes(event.target.name)) {
        // A model name typed for one provider rarely exists on the other.
        const target = event.target.name === "llm_provider" ? ["llm_model", "vision_model"] : ["embedding_model"];
        target.forEach(name => { field(name).value = ""; });
        updateModelPlaceholders();
    }
});

$("settingsButton").addEventListener("click", async () => {
    try {
        fillSettings(await api("/api/settings"));
        openModal("settingsModal");
    } catch (error) {
        toast(error.message, "error");
    }
});

settingsForm.addEventListener("submit", async event => {

    event.preventDefault();

    $("saveSettings").disabled = true;
    $("settingsError").textContent = "";

    try {
        fillSettings(await api("/api/settings", { method: "PUT", json: settingsPayload() }));
        closeModal("settingsModal");
        toast("Settings saved", "success");
        await loadSources();
    } catch (error) {
        $("settingsError").textContent = error.message;
    } finally {
        $("saveSettings").disabled = false;
    }
});

$("testSettings").addEventListener("click", async () => {

    const button = $("testSettings");
    const results = $("testResults");

    button.disabled = true;
    button.textContent = "Testing…";
    results.hidden = true;
    $("settingsError").textContent = "";

    try {
        const data = await api("/api/settings/test", { method: "POST", json: settingsPayload() });

        results.innerHTML = Object.entries({ llm: "Answer model", embedding: "Embeddings" })
            .map(([key, label]) => `
                <div class="test-row ${data[key].ok ? "ok" : "fail"}">
                    <strong>${label}</strong><span>${escapeHtml(data[key].detail)}</span>
                </div>`)
            .join("");
        results.hidden = false;

    } catch (error) {
        $("settingsError").textContent = error.message;
    } finally {
        button.disabled = false;
        button.textContent = "Test connection";
    }
});

$("removeKey").addEventListener("click", async () => {
    try {
        fillSettings(await api("/api/settings", { method: "PUT", json: { openai_api_key: "" } }));
        toast("Saved API key removed", "success");
    } catch (error) {
        toast(error.message, "error");
    }
});


// ----------------------------------------
// Mobile sidebar
// ----------------------------------------

function setSidebar(open) {
    $("sidebar").classList.toggle("open", open);
    $("sidebarScrim").hidden = !open;
}

$("sidebarOpen").addEventListener("click", () => setSidebar(true));
$("sidebarClose").addEventListener("click", () => setSidebar(false));
$("sidebarScrim").addEventListener("click", () => setSidebar(false));


// ----------------------------------------
// Start
// ----------------------------------------

async function enterApp(user) {

    state.user = user;

    $("authView").hidden = true;
    $("appView").hidden = false;
    $("userName").textContent = user.username;
    $("userAvatar").textContent = user.username.slice(0, 2);

    newChat();
    showTab(storage("get", "rag_tab") === "library" ? "library" : "chats");

    const results = await Promise.allSettled([
        loadSources(),
        loadConversations(),
        api("/api/settings").then(data => {
            state.settings = data;
            updateModelBadge();
        })
    ]);

    const failed = results.find(result => result.status === "rejected");
    if (failed && $("authView").hidden) toast(failed.reason.message, "error");

    // First visit: nothing to chat about yet, so show where to add sources.
    if (!state.sources.length && !state.conversations.length) showTab("library");

    questionInput.focus();
}

async function start() {

    setIcons();
    setAuthMode(false);
    bindSuggestions();

    if (!storage("get", TOKEN_KEY)) {
        showAuth();
        return;
    }

    try {
        await enterApp(await api("/api/auth/me"));
    } catch (error) {
        // A 401 has already shown the sign-in screen.
        if ($("authView").hidden) showAuth(error.message);
    }
}

start();
