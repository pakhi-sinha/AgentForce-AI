const API_BASE = window.location.origin;
const TOKEN_KEY = "agentforce.token";
const APP_STATE_KEY = "agentforce.app-state";

const MODE_META = {
  general: {
    title: "General Chat",
    description: "Ask anything, keep your conversations tidy, and work with a clean chat layout.",
    placeholder: "Message AgentForce AI...",
    suggestions: ["Outline a plan for learning Python.", "Draft a polite client reply.", "Explain this error simply."],
  },
  study: {
    title: "Study Mode",
    description: "Get concept breakdowns, clear steps, and learning-friendly explanations.",
    placeholder: "Ask a study question...",
    suggestions: ["Teach me normalization in DBMS.", "Explain recursion with examples.", "Quiz me on operating systems."],
  },
  research: {
    title: "Research Mode",
    description: "Get structured findings, tradeoffs, and grounded answers from your uploaded material.",
    placeholder: "Ask a research question...",
    suggestions: ["Compare REST and GraphQL.", "Summarize the main findings.", "What are the key limitations here?"],
  },
  summarizer: {
    title: "Summarizer",
    description: "Upload notes or documents and turn them into crisp summaries and takeaways.",
    placeholder: "Ask for a summary or upload a file...",
    suggestions: ["Summarize this document in plain English.", "Extract the action items.", "Give me a short executive summary."],
  },
};

const $ = (selector) => document.querySelector(selector);
const els = {
  landingPage: $("#landingPage"),
  authPage: $("#authPage"),
  appPage: $("#appPage"),
  authForm: $("#authForm"),
  authTitle: $("#authTitle"),
  authKicker: $("#authKicker"),
  authDescription: $("#authDescription"),
  authSwitch: $("#authSwitch"),
  authSubmit: $("#authSubmit"),
  usernameWrap: $("#usernameWrap"),
  usernameInput: $("#usernameInput"),
  emailInput: $("#emailInput"),
  passwordInput: $("#passwordInput"),
  sidebar: $("#sidebar"),
  newChatBtn: $("#newChatBtn"),
  modeSelector: $("#modeSelector"),
  refreshHistoryBtn: $("#refreshHistoryBtn"),
  historyList: $("#historyList"),
  usageMessages: $("#usageMessages"),
  usageTokens: $("#usageTokens"),
  usageChats: $("#usageChats"),
  profileName: $("#profileName"),
  profileEmail: $("#profileEmail"),
  settingsBtn: $("#settingsBtn"),
  logoutBtn: $("#logoutBtn"),
  menuBtn: $("#menuBtn"),
  workspaceTitle: $("#workspaceTitle"),
  statusText: $("#statusText"),
  errorBanner: $("#errorBanner"),
  modeHeading: $("#modeHeading"),
  modeDescription: $("#modeDescription"),
  demoBtn: $("#demoBtn"),
  ragToggle: $("#ragToggle"),
  messages: $("#messages"),
  uploadStatus: $("#uploadStatus"),
  uploadBtn: $("#uploadBtn"),
  exportBtn: $("#exportBtn"),
  chatForm: $("#chatForm"),
  fileInput: $("#fileInput"),
  micBtn: $("#micBtn"),
  messageInput: $("#messageInput"),
  sendBtn: $("#sendBtn"),
  settingsBackdrop: $("#settingsBackdrop"),
  closeSettingsBtn: $("#closeSettingsBtn"),
  settingsModel: $("#settingsModel"),
  temperature: $("#temperature"),
  temperatureValue: $("#temperatureValue"),
  ragSettingsToggle: $("#ragSettingsToggle"),
  clearCurrentChatBtn: $("#clearCurrentChatBtn"),
  toast: $("#toast"),
};

const state = {
  route: "/",
  token: localStorage.getItem(TOKEN_KEY),
  currentUser: null,
  currentChat: null,
  selectedMode: "general",
  messages: [],
  busy: false,
  useRag: false,
  capabilities: null,
  availableModels: [],
  recorder: null,
  chunks: [],
};

const settings = {
  model: "deepseek/deepseek-chat",
  temperature: 0.7,
  rag_enabled: false,
};

const DEFAULT_OPENROUTER_MODELS = [
  "deepseek/deepseek-chat",
  "google/gemini-pro",
  "mistralai/mistral-7b-instruct",
  "openrouter/auto",
];

function loadPersistedState() {
  try {
    const saved = JSON.parse(localStorage.getItem(APP_STATE_KEY) || "{}");
    state.selectedMode = saved.selectedMode || "general";
    state.currentChat = saved.currentChat || null;
  } catch (_) {
    localStorage.removeItem(APP_STATE_KEY);
  }
}

function persistState() {
  localStorage.setItem(
    APP_STATE_KEY,
    JSON.stringify({
      currentChat: state.currentChat,
      selectedMode: state.selectedMode,
    }),
  );
}

function authHeaders(json = true) {
  const headers = {};
  if (json) headers["Content-Type"] = "application/json";
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  return headers;
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      ...(options.auth === false ? {} : authHeaders(options.json !== false)),
    },
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) logout(true);
    throw new Error(normalizeErrorPayload(payload));
  }
  return payload;
}

async function route() {
  loadPersistedState();
  state.route = window.location.pathname.replace(/\/$/, "") || "/";
  document.body.classList.toggle("app-route", state.route === "/app");
  if (state.route === "/chat") {
    go("/app", true);
    return;
  }
  els.landingPage.hidden = state.route !== "/";
  els.authPage.hidden = !["/login", "/signup"].includes(state.route);
  els.appPage.hidden = state.route !== "/app";

  if (!els.authPage.hidden) renderAuthPage();
  if (state.route === "/app") {
    if (!state.token) {
      go("/login");
      return;
    }
    await bootApp();
  }
}

function go(path, replace = false) {
  if (replace) history.replaceState({}, "", path);
  else history.pushState({}, "", path);
  route().catch((error) => toast(readableError(error.message), true));
}

function renderAuthPage() {
  const signup = state.route === "/signup";
  els.authTitle.textContent = signup ? "Create Your Account" : "Welcome Back";
  els.authKicker.textContent = signup ? "Start your workspace" : "Continue where you left off";
  els.authDescription.textContent = signup
    ? "Create an account to save chats, settings, and usage."
    : "Sign in to access your chats, tools, and AI workspace.";
  els.authSubmit.textContent = signup ? "Create Account" : "Login";
  els.usernameWrap.hidden = !signup;
  els.passwordInput.autocomplete = signup ? "new-password" : "current-password";
  els.authSwitch.innerHTML = signup
    ? `Already have an account? <a href="/login">Login</a>`
    : `Need an account? <a href="/signup">Create one</a>`;
}

async function submitAuth(event) {
  event.preventDefault();
  const signup = state.route === "/signup";
  const body = signup
    ? {
        username: els.usernameInput.value.trim(),
        email: els.emailInput.value.trim(),
        password: els.passwordInput.value,
      }
    : {
        email: els.emailInput.value.trim(),
        password: els.passwordInput.value,
      };
  if (signup && !body.username) {
    toast("Username is required.", true);
    return;
  }
  const data = await api(signup ? "/auth/signup" : "/auth/login", {
    method: "POST",
    auth: false,
    body: JSON.stringify(body),
  });
  state.token = data.access_token;
  localStorage.setItem(TOKEN_KEY, state.token);
  state.currentUser = data.user;
  toast(signup ? "Account created." : "Logged in.");
  go("/app");
}

function logout(silent = false) {
  state.token = null;
  state.currentUser = null;
  state.currentChat = null;
  state.messages = [];
  localStorage.removeItem(TOKEN_KEY);
  persistState();
  if (!silent) toast("Logged out.");
  go("/login");
}

let booted = false;
async function bootApp() {
  bindEvents();
  if (!booted) {
    await Promise.all([loadCurrentUser(), loadCapabilities(), loadModels(), loadSettings()]);
    booted = true;
  } else {
    await Promise.all([loadCurrentUser(), loadModels(), loadSettings()]);
  }
  syncModeUi();
  renderEmptyState();
  await Promise.all([loadHistory(), loadUsage()]);
  if (state.currentChat) {
    try {
      await openChat(state.currentChat);
    } catch (_) {
      state.currentChat = null;
      persistState();
      renderEmptyState();
    }
  }
}

async function loadCurrentUser() {
  state.currentUser = await api("/auth/me");
  els.profileName.textContent = state.currentUser.username;
  els.profileEmail.textContent = state.currentUser.email;
}

async function loadCapabilities() {
  try {
    state.capabilities = await api("/capabilities", { auth: false });
    const warnings = [];
    if (!state.capabilities.chat?.available) {
      warnings.push(state.capabilities.chat?.message || "No model is currently reachable.");
    }
    if (!state.capabilities.voice?.available) {
      els.micBtn.disabled = true;
      warnings.push(state.capabilities.voice?.message || "Voice is unavailable.");
    }
    if (!state.capabilities.rag?.available) {
      els.uploadBtn.disabled = true;
      els.ragToggle.disabled = true;
      warnings.push(state.capabilities.rag?.message || "RAG is unavailable.");
    }
    showBanner(warnings.join(" "));
  } catch {
    showBanner("Could not verify model capabilities. Check OLLAMA_BASE_URL or OPENAI_API_KEY.");
  }
}

async function loadSettings() {
  const serverSettings = await api("/settings");
  settings.model = serverSettings.model;
  settings.temperature = serverSettings.temperature;
  settings.rag_enabled = serverSettings.rag_enabled;
  state.useRag = Boolean(serverSettings.rag_enabled);
  if (MODE_META[serverSettings.mode]) state.selectedMode = serverSettings.mode;
  syncModelSelection();
  els.temperature.value = String(settings.temperature);
  els.temperatureValue.textContent = String(settings.temperature);
  els.ragSettingsToggle.checked = state.useRag;
  persistState();
}

async function loadModels() {
  try {
    const data = await api("/models", { auth: false });
    const models = (data.models || []).map((entry) => entry.id || entry.name || entry.model).filter(Boolean);
    state.availableModels = [...new Set(models)];
  } catch {
    state.availableModels = [];
  }
  renderModelOptions();
}

function renderModelOptions() {
  const models = state.availableModels.length ? state.availableModels : DEFAULT_OPENROUTER_MODELS;
  els.settingsModel.innerHTML = models
    .map((model) => `<option value="${escapeHtml(model)}">${escapeHtml(model)}</option>`)
    .join("");
  syncModelSelection();
}

function syncModelSelection() {
  if (state.availableModels.length && !state.availableModels.includes(settings.model)) {
    settings.model = state.availableModels[0];
  }
  const hasOption = Array.from(els.settingsModel.options).some((option) => option.value === settings.model);
  if (!hasOption) {
    const option = document.createElement("option");
    option.value = settings.model;
    option.textContent = settings.model;
    els.settingsModel.appendChild(option);
  }
  els.settingsModel.value = settings.model;
}

async function saveSettings() {
  await api("/settings", {
    method: "PUT",
    body: JSON.stringify({
      model: settings.model,
      mode: state.selectedMode,
      temperature: settings.temperature,
      rag_enabled: state.useRag,
    }),
  });
}

async function loadUsage() {
  const usage = await api("/usage");
  els.usageMessages.textContent = usage.messages;
  els.usageTokens.textContent = usage.tokens;
  els.usageChats.textContent = usage.chats;
}

async function loadHistory() {
  const data = await api("/history");
  els.historyList.innerHTML = "";
  if (!data.chats?.length) {
    els.historyList.innerHTML = `<p class="muted-text">No chats yet.</p>`;
    return;
  }
  data.chats.forEach((chat) => {
    const item = document.createElement("article");
    item.className = `history-item ${chat.id === state.currentChat ? "active" : ""}`;
    item.innerHTML = `
      <button class="history-open" type="button">
        <strong>${escapeHtml(chat.title)}</strong>
        <span>${escapeHtml(chat.mode)}</span>
      </button>
      <button class="mini-button rename-chat" type="button">Rename</button>
      <button class="mini-button delete-chat" type="button">Delete</button>
    `;
    item.querySelector(".history-open").onclick = () => openChat(chat.id);
    item.querySelector(".rename-chat").onclick = () => renameChat(chat.id, chat.title);
    item.querySelector(".delete-chat").onclick = () => deleteChat(chat.id);
    els.historyList.appendChild(item);
  });
}

async function newChat() {
  const title = MODE_META[state.selectedMode].title;
  const chat = await api("/chat/new", {
    method: "POST",
    body: JSON.stringify({
      title,
      mode: state.selectedMode,
      model: settings.model,
    }),
  });
  state.currentChat = chat.id;
  state.messages = [];
  persistState();
  renderEmptyState();
  await Promise.all([loadHistory(), loadUsage()]);
}

async function openChat(chatId) {
  const data = await api(`/history?chat_id=${encodeURIComponent(chatId)}`);
  state.currentChat = chatId;
  state.messages = (data.messages || []).map((message) => ({
    role: message.role === "assistant" ? "assistant" : "user",
    content: message.content,
    model: message.model || settings.model,
    created_at: message.created_at,
  }));
  persistState();
  renderMessages();
  await loadHistory();
  els.sidebar.classList.remove("open");
}

async function renameChat(chatId, title) {
  const next = window.prompt("Rename chat", title);
  if (!next?.trim()) return;
  await api(`/chat/${chatId}`, {
    method: "PATCH",
    body: JSON.stringify({ title: next.trim() }),
  });
  await loadHistory();
  toast("Chat renamed.");
}

async function deleteChat(chatId) {
  if (!window.confirm("Delete this chat?")) return;
  await api(`/chat/${chatId}`, { method: "DELETE" });
  if (state.currentChat === chatId) {
    state.currentChat = null;
    state.messages = [];
    persistState();
    renderEmptyState();
  }
  await Promise.all([loadHistory(), loadUsage()]);
}

async function clearCurrentChat() {
  if (!state.currentChat) {
    state.messages = [];
    renderEmptyState();
    return;
  }
  await deleteChat(state.currentChat);
}

function syncModeUi() {
  const meta = MODE_META[state.selectedMode];
  els.workspaceTitle.textContent = meta.title;
  els.modeHeading.textContent = meta.title;
  els.modeDescription.textContent = meta.description;
  els.messageInput.placeholder = meta.placeholder;
  els.modeSelector.querySelectorAll("button").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === state.selectedMode);
  });
  updateRagButton();
}

async function setMode(mode) {
  if (!MODE_META[mode]) return;
  state.selectedMode = mode;
  syncModeUi();
  persistState();
  await saveSettings();
  if (!state.messages.length) renderEmptyState();
}

function renderEmptyState() {
  const meta = MODE_META[state.selectedMode];
  els.messages.innerHTML = `
    <section class="empty-state">
      <div class="empty-mark">AF</div>
      <p class="empty-title">Start a conversation</p>
      <h2>${escapeHtml(meta.title)}</h2>
      <p>${escapeHtml(meta.description)}</p>
      <div class="suggestion-grid">
        ${meta.suggestions.map((item) => `<button type="button">${escapeHtml(item)}</button>`).join("")}
      </div>
    </section>
  `;
  els.messages.querySelectorAll(".suggestion-grid button").forEach((button) => {
    button.onclick = () => {
      els.messageInput.value = button.textContent;
      resizeComposer();
      updateSendButton();
      els.messageInput.focus();
    };
  });
}

function renderMessages() {
  els.messages.innerHTML = "";
  if (!state.messages.length) {
    renderEmptyState();
    return;
  }
  state.messages.forEach((message, index) => renderMessage(message, index));
  scrollToBottom();
}

function renderMessage(message, index, isThinking = false) {
  els.messages.querySelector(".empty-state")?.remove();
  const article = document.createElement("article");
  article.className = `message-row ${message.role}`;
  const time = message.created_at ? new Date(message.created_at) : new Date();
  article.innerHTML = `
    <div class="message-avatar">${message.role === "user" ? "You" : "AI"}</div>
    <div class="message-card">
      <div class="message-meta">
        <strong>${message.role === "user" ? "You" : "AgentForce AI"}</strong>
        <span>${time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
      </div>
      <div class="message-content">${isThinking ? thinkingMarkup() : renderMarkdown(message.content || "")}</div>
    </div>
  `;
  els.messages.appendChild(article);
  if (!isThinking) addMessageActions(article.querySelector(".message-content"), message, index);
  scrollToBottom();
  return article;
}

function thinkingMarkup() {
  return `<div class="thinking-row"><span>AI is thinking</span><i></i><i></i><i></i></div>`;
}

async function sendMessage(text = els.messageInput.value.trim()) {
  if (!text || state.busy) return;
  state.messages.push({ role: "user", content: text, created_at: new Date().toISOString() });
  els.messageInput.value = "";
  resizeComposer();
  renderMessages();
  await streamReply(text);
}

async function streamReply(prompt) {
  setBusy(true, "Thinking...");
  const thinking = renderMessage({ role: "assistant", content: "" }, state.messages.length, true);
  try {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        message: prompt,
        chat_id: state.currentChat,
        mode: state.selectedMode,
        model: settings.model,
        use_rag: state.useRag,
        use_memory: true,
        temperature: settings.temperature,
      }),
    });
    if (!response.ok || !response.body) throw new Error(await response.text());

    thinking.remove();
    const assistant = {
      role: "assistant",
      content: "",
      model: settings.model,
      sources: [],
      created_at: new Date().toISOString(),
    };
    state.messages.push(assistant);
    const article = renderMessage(assistant, state.messages.length - 1);
    const contentNode = article.querySelector(".message-content");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.replace(/\r\n/g, "\n").split("\n\n");
      buffer = events.pop() || "";
      for (const event of events) {
        const dataLines = event
          .split("\n")
          .filter((entry) => entry.startsWith("data:"))
          .map((entry) => entry.replace(/^data:\s?/, ""));
        if (!dataLines.length) continue;
        const payload = JSON.parse(dataLines.join("\n"));
        if (payload.type === "meta") {
          state.currentChat = payload.chat_id;
          assistant.sources = payload.sources || [];
          persistState();
        }
        if (payload.type === "token" && payload.token) {
          assistant.content += payload.token;
          contentNode.innerHTML = renderMarkdown(assistant.content) + renderSources(assistant.sources);
          scrollToBottom();
        }
        if (payload.type === "done" || payload.done === true) {
          if (payload.message && !assistant.content) {
            assistant.content = payload.message;
            contentNode.innerHTML = renderMarkdown(assistant.content) + renderSources(assistant.sources);
          }
        }
        if (payload.type === "error") throw new Error(payload.error);
      }
    }
    addMessageActions(contentNode, assistant, state.messages.length - 1);
    await Promise.all([loadHistory(), loadUsage()]);
  } catch (error) {
    thinking.remove();
    state.messages.push({
      role: "assistant",
      content: `Error: ${readableError(error.message)}`,
      created_at: new Date().toISOString(),
      model: "system",
    });
    renderMessages();
    toast(readableError(error.message), true);
  } finally {
    setBusy(false);
  }
}

async function runDemo() {
  if (state.busy) return;
  setBusy(true, "Demo Mode: preparing...");
  try {
    await newChat();
    const prompt = "How can AgentForce AI help with research and summaries?";
    els.messageInput.value = prompt;
    resizeComposer();
    await new Promise((resolve) => setTimeout(resolve, 420));
    await sendMessage(prompt);
    toast("Demo completed.");
  } finally {
    setBusy(false);
  }
}

async function uploadDocument() {
  const file = els.fileInput.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("files", file);
  setBusy(true, `Indexing ${file.name}...`);
  try {
    const result = await api("/upload", {
      method: "POST",
      body: form,
      json: false,
    });
    state.useRag = true;
    els.uploadStatus.textContent = result.ingested?.join(", ") || `${file.name} indexed`;
    updateRagButton();
    els.ragSettingsToggle.checked = true;
    await saveSettings();
    toast("Document indexed.");
  } catch (error) {
    toast(readableError(error.message), true);
  } finally {
    els.fileInput.value = "";
    setBusy(false);
  }
}

async function startVoiceCapture() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.onstart = () => els.micBtn.classList.add("recording");
    recognition.onend = () => els.micBtn.classList.remove("recording");
    recognition.onerror = () => toast("Voice recognition failed.", true);
    recognition.onresult = (event) => sendMessage(event.results[0][0].transcript);
    recognition.start();
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    toast("Voice is not supported in this browser.", true);
    return;
  }
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  state.chunks = [];
  state.recorder = new MediaRecorder(stream);
  state.recorder.ondataavailable = (event) => event.data.size && state.chunks.push(event.data);
  state.recorder.onstop = async () => {
    stream.getTracks().forEach((track) => track.stop());
    els.micBtn.classList.remove("recording");
    const form = new FormData();
    form.append("file", new Blob(state.chunks, { type: "audio/webm" }), "recording.webm");
    try {
      const data = await api("/voice-input", { method: "POST", body: form, json: false });
      if (data.text) sendMessage(data.text);
    } catch (error) {
      toast(readableError(error.message), true);
    }
  };
  els.micBtn.classList.add("recording");
  state.recorder.start();
  window.setTimeout(() => {
    if (state.recorder?.state === "recording") state.recorder.stop();
  }, 7000);
}

function renderMarkdown(text) {
  return escapeHtml(text)
    .replace(/```(\w+)?\n([\s\S]*?)```/g, (_, language, code) => {
      return `<pre><div class="code-head"><span>${language || "code"}</span><button type="button" class="copy-code">Copy</button></div><code>${code}</code></pre>`;
    })
    .replace(/^### (.*)$/gm, "<h3>$1</h3>")
    .replace(/^## (.*)$/gm, "<h2>$1</h2>")
    .replace(/^# (.*)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br />");
}

function renderSources(sources = []) {
  if (!sources.length) return "";
  return `<div class="source-row">${sources.map((source) => `<code>${escapeHtml(source)}</code>`).join("")}</div>`;
}

function addMessageActions(container, message, index) {
  container.querySelectorAll(".copy-code").forEach((button) => {
    button.onclick = async () => {
      await navigator.clipboard.writeText(button.closest("pre").querySelector("code").textContent);
      toast("Code copied.");
    };
  });
  const actions = document.createElement("div");
  actions.className = "message-actions";
  actions.innerHTML = `<button type="button">Copy</button>${message.role === "assistant" ? `<button type="button">Regenerate</button>` : ""}`;
  actions.children[0].onclick = async () => {
    await navigator.clipboard.writeText(message.content || "");
    toast("Message copied.");
  };
  if (actions.children[1]) actions.children[1].onclick = () => regenerate(index);
  container.appendChild(actions);
}

async function regenerate(index) {
  const userIndex = findPreviousUserIndex(index);
  if (userIndex < 0) return;
  const prompt = state.messages[userIndex].content;
  state.messages = state.messages.slice(0, index);
  renderMessages();
  await streamReply(prompt);
}

function findPreviousUserIndex(index) {
  for (let i = index - 1; i >= 0; i -= 1) {
    if (state.messages[i]?.role === "user") return i;
  }
  return -1;
}

function exportChat() {
  if (!state.messages.length) {
    toast("Nothing to export.");
    return;
  }
  const content = state.messages.map((message) => `${message.role.toUpperCase()}\n${message.content}`).join("\n\n---\n\n");
  const blob = new Blob([content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `agentforce-chat-${new Date().toISOString().slice(0, 10)}.txt`;
  link.click();
  URL.revokeObjectURL(url);
}

function setBusy(isBusy, status = "Ready") {
  state.busy = isBusy;
  els.statusText.textContent = status;
  updateSendButton();
  els.demoBtn.disabled = isBusy;
}

function updateSendButton() {
  els.sendBtn.disabled = state.busy || !els.messageInput.value.trim();
}

function resizeComposer() {
  els.messageInput.style.height = "auto";
  els.messageInput.style.height = `${Math.min(170, els.messageInput.scrollHeight)}px`;
  updateSendButton();
}

function updateRagButton() {
  els.ragToggle.textContent = state.useRag ? "RAG On" : "RAG Off";
  els.ragToggle.classList.toggle("active", state.useRag);
}

function showBanner(text) {
  els.errorBanner.hidden = !text;
  els.errorBanner.textContent = text || "";
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    els.messages.scrollTop = els.messages.scrollHeight;
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


function normalizeErrorPayload(payload) {
  if (payload == null) return "Request failed.";
  if (typeof payload === "string") return payload;
  const detail = payload.detail ?? payload.message ?? payload.error ?? payload;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0];
    if (typeof first === "string") return first;
    if (first && typeof first === "object") return first.msg || JSON.stringify(first);
    return JSON.stringify(detail);
  }
  if (detail && typeof detail === "object") return detail.msg || JSON.stringify(detail);
  return String(detail);
}

function readableError(message) {
  if (typeof message === "object" && message !== null) return normalizeErrorPayload(message);
  try {
    const parsed = JSON.parse(message);
    return normalizeErrorPayload(parsed);
  } catch {
    if (message === "[object Object]") return "Request failed. Please check your input and try again.";
    return String(message || "Request failed.");
  }
}

function toast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.className = `toast show ${isError ? "error" : ""}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => {
    els.toast.className = "toast";
  }, 2800);
}

let eventsBound = false;
function bindEvents() {
  if (eventsBound) return;
  eventsBound = true;

  els.authForm.addEventListener("submit", (event) => {
    submitAuth(event).catch((error) => toast(readableError(error.message), true));
  });

  els.newChatBtn.onclick = () => newChat().catch((error) => toast(readableError(error.message), true));
  els.refreshHistoryBtn.onclick = () => loadHistory().catch((error) => toast(readableError(error.message), true));
  els.demoBtn.onclick = () => runDemo().catch((error) => toast(readableError(error.message), true));
  els.logoutBtn.onclick = () => logout();
  els.settingsBtn.onclick = () => (els.settingsBackdrop.hidden = false);
  els.closeSettingsBtn.onclick = () => (els.settingsBackdrop.hidden = true);
  els.menuBtn.onclick = () => els.sidebar.classList.toggle("open");
  els.uploadBtn.onclick = () => els.fileInput.click();
  els.fileInput.onchange = () => uploadDocument().catch((error) => toast(readableError(error.message), true));
  els.exportBtn.onclick = exportChat;
  els.micBtn.onclick = () => startVoiceCapture().catch((error) => toast(readableError(error.message), true));
  els.clearCurrentChatBtn.onclick = () => clearCurrentChat().catch((error) => toast(readableError(error.message), true));

  els.chatForm.onsubmit = (event) => {
    event.preventDefault();
    sendMessage().catch((error) => toast(readableError(error.message), true));
  };

  els.messageInput.oninput = resizeComposer;
  els.messageInput.onkeydown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      els.chatForm.requestSubmit();
    }
  };

  els.ragToggle.onclick = async () => {
    state.useRag = !state.useRag;
    els.ragSettingsToggle.checked = state.useRag;
    updateRagButton();
    await saveSettings();
  };

  els.modeSelector.querySelectorAll("button").forEach((button) => {
    button.onclick = () => setMode(button.dataset.mode).catch((error) => toast(readableError(error.message), true));
  });

  els.settingsModel.onchange = async () => {
    settings.model = els.settingsModel.value;
    await saveSettings();
  };

  els.temperature.oninput = async () => {
    settings.temperature = Number(els.temperature.value);
    els.temperatureValue.textContent = els.temperature.value;
    await saveSettings();
  };

  els.ragSettingsToggle.onchange = async () => {
    state.useRag = els.ragSettingsToggle.checked;
    updateRagButton();
    await saveSettings();
  };

  els.settingsBackdrop.onclick = (event) => {
    if (event.target === els.settingsBackdrop) els.settingsBackdrop.hidden = true;
  };

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href^='/']");
    if (!link) return;
    event.preventDefault();
    go(link.getAttribute("href"));
  });
}

window.addEventListener("popstate", () => route().catch((error) => toast(readableError(error.message), true)));
bindEvents();
route().catch((error) => toast(readableError(error.message), true));
