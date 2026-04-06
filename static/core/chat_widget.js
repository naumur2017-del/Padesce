(function() {
  const root = document.getElementById("chatWidget");
  if (!root) {
    return;
  }

  const currentUser = root.dataset.user || "anonymous";
  const storageKey = `padesce.chat.history.${currentUser}`;
  const historyLimit = 40;

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  const fab = document.getElementById("chatFab");
  const win = document.getElementById("chatWindow");
  const closeBtn = document.getElementById("chatClose");
  const fullscreenBtn = document.getElementById("chatFullscreen");
  const input = document.getElementById("chatInput");
  const sendBtn = document.getElementById("chatSend");
  const msgContainer = document.getElementById("chatMessages");
  const quickActions = document.getElementById("chatQuickActions");
  const welcome = document.getElementById("chatWelcome");
  const chatStatus = document.getElementById("chatStatus");
  const chatStatusText = document.getElementById("chatStatusText");
  const syncToast = document.getElementById("appSyncToast");
  const syncToastText = document.getElementById("appSyncToastText");

  const state = {
    isOpen: false,
    isFullscreen: false,
    messages: [],
    toastTimer: null,
  };

  function showToast(text, tone) {
    if (!syncToast || !syncToastText) {
      return;
    }
    window.clearTimeout(state.toastTimer);
    syncToast.hidden = false;
    syncToastText.textContent = text;
    syncToast.classList.toggle("is-offline", tone === "offline");
    syncToast.classList.add("is-visible");
    const duration = tone === "offline" ? 5000 : 2800;
    state.toastTimer = window.setTimeout(() => {
      syncToast.classList.remove("is-visible");
    }, duration);
  }

  function updateNetworkStatus() {
    const online = navigator.onLine;
    if (chatStatus) {
      chatStatus.classList.toggle("is-offline", !online);
    }
    if (chatStatusText) {
      chatStatusText.textContent = online ? "En ligne" : "Hors ligne";
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function parseTableRow(line) {
    return line
      .trim()
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => escapeHtml(cell.trim()));
  }

  function renderFallbackMarkdown(text) {
    return String(text || "")
      .split(/\n{2,}/)
      .map((block) => {
        const lines = block.split("\n").filter(Boolean);
        if (
          lines.length >= 2 &&
          lines[0].includes("|") &&
          /^\|?[\s:-]+(\|[\s:-]+)+\|?$/.test(lines[1].trim())
        ) {
          const rows = lines.map(parseTableRow);
          const header = rows[0];
          const body = rows.slice(2);
          return (
            "<table><thead><tr>" +
            header.map((cell) => `<th>${cell}</th>`).join("") +
            "</tr></thead><tbody>" +
            body
              .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
              .join("") +
            "</tbody></table>"
          );
        }
        return `<p>${escapeHtml(block).replace(/\n/g, "<br>")}</p>`;
      })
      .join("");
  }

  function renderMarkdown(text) {
    if (typeof window.marked !== "undefined") {
      window.marked.setOptions({ breaks: true, gfm: true });
      return window.marked.parse(text || "");
    }
    return renderFallbackMarkdown(text);
  }

  function parseHistory() {
    try {
      const raw = localStorage.getItem(storageKey);
      const parsed = JSON.parse(raw || "[]");
      if (!Array.isArray(parsed)) {
        return [];
      }
      return parsed
        .filter((item) => item && (item.type === "user" || item.type === "bot") && item.text)
        .slice(-historyLimit);
    } catch (error) {
      return [];
    }
  }

  function saveHistory() {
    try {
      localStorage.setItem(storageKey, JSON.stringify(state.messages.slice(-historyLimit)));
    } catch (error) {
      // Ignore storage quota failures.
    }
  }

  function syncPromptVisibility() {
    const hasHistory = state.messages.length > 0;
    const hasUserMessage = state.messages.some((item) => item.type === "user");
    if (welcome) {
      welcome.hidden = hasHistory;
    }
    if (quickActions) {
      quickActions.hidden = hasUserMessage;
    }
  }

  function scrollMessages() {
    msgContainer.scrollTop = msgContainer.scrollHeight;
  }

  function formatTime(isoString) {
    const parsed = isoString ? new Date(isoString) : new Date();
    return parsed.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  }

  function appendMessage(entry, options = {}) {
    const persist = options.persist !== false;
    const scroll = options.scroll !== false;
    const message = {
      type: entry.type,
      text: String(entry.text || ""),
      markdown: Boolean(entry.markdown),
      filename: entry.filename || null,
      at: entry.at || new Date().toISOString(),
    };

    const msgDiv = document.createElement("div");
    msgDiv.className = `chat-msg ${message.type}`;

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";
    if (message.markdown) {
      bubble.classList.add("markdown-content");
      bubble.innerHTML = renderMarkdown(message.text);
    } else {
      bubble.textContent = message.text;
    }

    if (message.filename) {
      const downloadLink = document.createElement("a");
      downloadLink.className = "chat-download-btn";
      downloadLink.href = `/api/chat/download/${encodeURIComponent(message.filename)}`;
      downloadLink.download = message.filename;
      downloadLink.textContent = `Télécharger ${message.filename}`;
      bubble.appendChild(downloadLink);
    }

    const time = document.createElement("div");
    time.className = "chat-msg-time";
    time.textContent = formatTime(message.at);

    msgDiv.appendChild(bubble);
    msgDiv.appendChild(time);
    msgContainer.appendChild(msgDiv);

    if (persist) {
      state.messages.push(message);
      state.messages = state.messages.slice(-historyLimit);
      saveHistory();
    }

    syncPromptVisibility();
    if (scroll) {
      scrollMessages();
    }
  }

  function restoreHistory() {
    state.messages = parseHistory();
    if (!state.messages.length) {
      syncPromptVisibility();
      return;
    }
    msgContainer.innerHTML = "";
    state.messages.forEach((message) => appendMessage(message, { persist: false, scroll: false }));
    syncPromptVisibility();
    scrollMessages();
  }

  function showTyping() {
    if (document.getElementById("typingIndicator")) {
      return;
    }
    const typing = document.createElement("div");
    typing.className = "typing-indicator show";
    typing.id = "typingIndicator";
    typing.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
    msgContainer.appendChild(typing);
    scrollMessages();
  }

  function hideTyping() {
    const typing = document.getElementById("typingIndicator");
    if (typing) {
      typing.remove();
    }
  }

  function setOpen(nextState) {
    state.isOpen = nextState;
    win.classList.toggle("visible", nextState);
    win.setAttribute("aria-hidden", nextState ? "false" : "true");
    if (nextState) {
      window.setTimeout(() => input.focus(), 120);
      scrollMessages();
    } else if (state.isFullscreen) {
      toggleFullscreen(false);
    }
  }

  function toggleChat(forceState) {
    const nextState = typeof forceState === "boolean" ? forceState : !state.isOpen;
    setOpen(nextState);
  }

  function toggleFullscreen(forceState) {
    state.isFullscreen = typeof forceState === "boolean" ? forceState : !state.isFullscreen;
    win.classList.toggle("fullscreen", state.isFullscreen);
    fullscreenBtn.textContent = state.isFullscreen ? "⊡" : "⛶";
    fullscreenBtn.title = state.isFullscreen ? "Réduire" : "Plein écran";
    fullscreenBtn.setAttribute("aria-label", state.isFullscreen ? "Réduire" : "Plein écran");
    fab.hidden = state.isFullscreen;
    scrollMessages();
  }

  async function sendMessage(textOverride) {
    const text = (textOverride || input.value || "").trim();
    if (!text) {
      return;
    }

    appendMessage({ type: "user", text });
    input.value = "";
    input.style.height = "auto";

    if (!navigator.onLine) {
      appendMessage({
        type: "bot",
        text: "⚠️ Mode hors ligne. Votre conversation reste enregistrée sur cet appareil. Reconnectez-vous pour envoyer de nouvelles requêtes au serveur.",
        markdown: false,
      });
      showToast("Mode hors ligne. Les données déjà ouvertes restent disponibles.", "offline");
      return;
    }

    showTyping();

    try {
      const response = await fetch("/api/chat/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-CSRFToken": getCookie("csrftoken") || ""
        },
        body: JSON.stringify({ message: text }),
      });

      const raw = await response.text();
      let data = {};
      try {
        data = raw ? JSON.parse(raw) : {};
      } catch (error) {
        data = { error: raw || response.statusText };
      }

      hideTyping();
      if (!response.ok || data.error || !data.response) {
        appendMessage({
          type: "bot",
          text: `⚠️ Le service chat est indisponible pour le moment. ${data.error || response.statusText}`,
          markdown: false,
        });
        return;
      }

      appendMessage({
        type: "bot",
        text: data.response,
        markdown: true,
        filename: data.filename || null,
      });
    } catch (error) {
      hideTyping();
      appendMessage({
        type: "bot",
        text: "⚠️ Je n'arrive pas à joindre le serveur PADESCE pour l'instant. La conversation reste conservée localement et reprendra dès que la connexion ou le service revient.",
        markdown: false,
      });
    }
  }

  fab.addEventListener("click", () => toggleChat());
  closeBtn.addEventListener("click", () => toggleChat(false));
  fullscreenBtn.addEventListener("click", () => toggleFullscreen());
  sendBtn.addEventListener("click", () => sendMessage());

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });

  input.addEventListener("input", function() {
    this.style.height = "auto";
    this.style.height = `${Math.min(this.scrollHeight, 110)}px`;
  });

  quickActions.addEventListener("click", (event) => {
    const button = event.target.closest(".quick-action-btn");
    if (!button) {
      return;
    }
    sendMessage(button.getAttribute("data-msg") || "");
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (state.isFullscreen) {
        toggleFullscreen(false);
        return;
      }
      if (state.isOpen) {
        toggleChat(false);
      }
    }
  });

  window.addEventListener("online", () => {
    updateNetworkStatus();
    showToast("Connexion rétablie. Synchronisation du cache en cours.", "sync");
  });

  window.addEventListener("offline", () => {
    updateNetworkStatus();
    showToast("Mode hors ligne. Les données déjà ouvertes restent disponibles.", "offline");
  });

  restoreHistory();
  updateNetworkStatus();
})();
