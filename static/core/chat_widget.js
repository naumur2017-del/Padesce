(function() {
  const root = document.getElementById("chatWidget");
  if (!root) {
    return;
  }

  const currentUser = root.dataset.user || "anonymous";
  const storageKey = `padesce.chat.threads.${currentUser}`;
  const legacyStorageKey = `padesce.chat.history.${currentUser}`;
  const historyLimit = 60;
  const conversationLimit = 18;

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === `${name}=`) {
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
  const newConversationBtn = document.getElementById("chatNewConversation");
  const sidebarNewBtn = document.getElementById("chatSidebarNew");
  const sidebarToggle = document.getElementById("chatSidebarToggle");
  const sidebar = document.getElementById("chatSidebar");
  const sidebarList = document.getElementById("chatSidebarList");
  const threadCount = document.getElementById("chatThreadCount");
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
    sidebarOpen: true,
    activeId: null,
    conversations: [],
    toastTimer: null,
  };

  function uid() {
    return `chat-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  }

  function makeConversation(messages) {
    const now = new Date().toISOString();
    return {
      id: uid(),
      title: deriveTitle(messages || []),
      createdAt: now,
      updatedAt: now,
      messages: (messages || []).slice(-historyLimit),
    };
  }

  function getActiveConversation() {
    let conversation = state.conversations.find((item) => item.id === state.activeId);
    if (!conversation) {
      conversation = createConversation({ activate: true, save: false, render: false });
    }
    return conversation;
  }

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
            body.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("") +
            "</tbody></table>"
          );
        }
        return `<p>${escapeHtml(block).replace(/\n/g, "<br>")}</p>`;
      })
      .join("");
  }

  function decorateCodeBlocks(container) {
    container.querySelectorAll("pre").forEach((pre) => {
      const code = pre.querySelector("code");
      const languageClass = code ? Array.from(code.classList).find((name) => name.startsWith("language-")) : "";
      const language = languageClass ? languageClass.replace("language-", "").toUpperCase() : "SQL";
      const wrap = document.createElement("div");
      wrap.className = "chat-code-card";
      const bar = document.createElement("div");
      bar.className = "chat-code-head";
      bar.innerHTML = `<span>${escapeHtml(language || "SQL")}</span><span>Requête générée</span>`;
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(bar);
      wrap.appendChild(pre);
    });
  }

  function renderMarkdown(text) {
    const wrapper = document.createElement("div");
    if (typeof window.marked !== "undefined") {
      window.marked.setOptions({ breaks: true, gfm: true });
      wrapper.innerHTML = window.marked.parse(text || "");
    } else {
      wrapper.innerHTML = renderFallbackMarkdown(text);
    }
    decorateCodeBlocks(wrapper);
    return wrapper.innerHTML;
  }

  function normalizeMessage(entry) {
    return {
      type: entry.type,
      text: String(entry.text || ""),
      markdown: Boolean(entry.markdown),
      filename: entry.filename || null,
      downloadUrl: entry.downloadUrl || entry.download_url || null,
      at: entry.at || new Date().toISOString(),
    };
  }

  function deriveTitle(messages) {
    const userMessage = (messages || []).find((item) => item.type === "user" && item.text);
    if (!userMessage) {
      return "Nouvelle discussion";
    }
    const title = userMessage.text.replace(/\s+/g, " ").trim();
    return title.length > 42 ? `${title.slice(0, 39)}...` : title;
  }

  function parseLegacyHistory() {
    try {
      const raw = localStorage.getItem(legacyStorageKey);
      const parsed = JSON.parse(raw || "[]");
      if (!Array.isArray(parsed)) {
        return [];
      }
      return parsed
        .filter((item) => item && (item.type === "user" || item.type === "bot") && item.text)
        .map(normalizeMessage)
        .slice(-historyLimit);
    } catch (error) {
      return [];
    }
  }

  function parseConversations() {
    try {
      const raw = localStorage.getItem(storageKey);
      const parsed = JSON.parse(raw || "{}");
      if (!parsed || !Array.isArray(parsed.conversations)) {
        const legacyMessages = parseLegacyHistory();
        return {
          activeId: null,
          conversations: legacyMessages.length ? [makeConversation(legacyMessages)] : [],
        };
      }
      return {
        activeId: parsed.activeId || null,
        conversations: parsed.conversations
          .filter((item) => item && Array.isArray(item.messages))
          .map((item) => ({
            id: item.id || uid(),
            title: item.title || deriveTitle(item.messages),
            createdAt: item.createdAt || new Date().toISOString(),
            updatedAt: item.updatedAt || item.createdAt || new Date().toISOString(),
            messages: item.messages
              .filter((message) => message && (message.type === "user" || message.type === "bot") && message.text)
              .map(normalizeMessage)
              .slice(-historyLimit),
          }))
          .slice(-conversationLimit),
      };
    } catch (error) {
      return { activeId: null, conversations: [] };
    }
  }

  function saveConversations() {
    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify({
          activeId: state.activeId,
          conversations: state.conversations.slice(-conversationLimit),
        })
      );
    } catch (error) {
      // Ignore storage quota failures.
    }
  }

  function formatTime(isoString) {
    const parsed = isoString ? new Date(isoString) : new Date();
    return parsed.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  }

  function formatThreadTime(isoString) {
    const parsed = isoString ? new Date(isoString) : new Date();
    return parsed.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });
  }

  function syncPromptVisibility() {
    const conversation = getActiveConversation();
    const hasHistory = conversation.messages.length > 0;
    const hasUserMessage = conversation.messages.some((item) => item.type === "user");
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

  function renderSidebar() {
    if (!sidebarList) {
      return;
    }
    const ordered = [...state.conversations].sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)));
    sidebarList.innerHTML = "";
    if (threadCount) {
      threadCount.textContent = `${state.conversations.length} discussion${state.conversations.length > 1 ? "s" : ""}`;
    }
    if (!ordered.length) {
      sidebarList.innerHTML = '<div class="chat-sidebar-empty">Aucune discussion pour le moment.</div>';
      return;
    }

    ordered.forEach((conversation) => {
      const last = conversation.messages[conversation.messages.length - 1];
      const button = document.createElement("button");
      button.type = "button";
      button.className = `chat-thread${conversation.id === state.activeId ? " is-active" : ""}`;
      button.dataset.threadId = conversation.id;
      button.innerHTML = `
        <span class="chat-thread-title">${escapeHtml(conversation.title || "Nouvelle discussion")}</span>
        <span class="chat-thread-preview">${escapeHtml(last ? last.text : "Prête à démarrer")}</span>
        <span class="chat-thread-meta">${escapeHtml(formatThreadTime(conversation.updatedAt))}</span>
      `;
      sidebarList.appendChild(button);
    });
  }

  function renderConversation() {
    const conversation = getActiveConversation();
    msgContainer.innerHTML = "";
    if (!conversation.messages.length) {
      msgContainer.appendChild(welcome);
      welcome.hidden = false;
    }
    conversation.messages.forEach((message) => appendMessage(message, { persist: false, scroll: false }));
    syncPromptVisibility();
    renderSidebar();
    scrollMessages();
  }

  function createConversation(options = {}) {
    const conversation = makeConversation([]);
    state.conversations.push(conversation);
    state.conversations = state.conversations.slice(-conversationLimit);
    if (options.activate !== false) {
      state.activeId = conversation.id;
    }
    if (options.save !== false) {
      saveConversations();
    }
    if (options.render !== false) {
      renderConversation();
      input.focus();
    }
    return conversation;
  }

  function switchConversation(id) {
    if (!id || id === state.activeId) {
      return;
    }
    state.activeId = id;
    saveConversations();
    renderConversation();
    if (window.matchMedia("(max-width: 720px)").matches) {
      setSidebarOpen(false);
    }
  }

  function updateConversationAfterMessage(conversation) {
    conversation.updatedAt = new Date().toISOString();
    conversation.title = deriveTitle(conversation.messages);
    state.conversations = state.conversations
      .filter((item) => item.id !== conversation.id)
      .concat(conversation)
      .slice(-conversationLimit);
    state.activeId = conversation.id;
    saveConversations();
    renderSidebar();
  }

  function appendMessage(entry, options = {}) {
    const persist = options.persist !== false;
    const scroll = options.scroll !== false;
    const message = normalizeMessage(entry);

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

    if (message.filename || message.downloadUrl) {
      const fileBox = document.createElement("div");
      fileBox.className = "chat-file-card";
      const fileName = message.filename || "fichier généré";
      fileBox.innerHTML = `
        <div class="chat-file-icon"><i class="fa-solid fa-file-arrow-down" aria-hidden="true"></i></div>
        <div class="chat-file-copy">
          <strong>${escapeHtml(fileName)}</strong>
          <span>Fichier généré par NAUMUR</span>
        </div>
      `;
      const downloadLink = document.createElement("a");
      downloadLink.className = "chat-download-btn";
      downloadLink.href = message.downloadUrl || `/api/chat/download/${encodeURIComponent(message.filename)}/`;
      downloadLink.innerHTML = '<i class="fa-solid fa-download" aria-hidden="true"></i><span>Télécharger</span>';
      if (message.downloadUrl) {
        downloadLink.target = "_blank";
        downloadLink.rel = "noopener noreferrer";
      } else {
        downloadLink.download = message.filename;
      }
      fileBox.appendChild(downloadLink);
      bubble.appendChild(fileBox);
    }

    const time = document.createElement("div");
    time.className = "chat-msg-time";
    time.textContent = formatTime(message.at);

    msgDiv.appendChild(bubble);
    msgDiv.appendChild(time);
    msgContainer.appendChild(msgDiv);

    if (persist) {
      const conversation = getActiveConversation();
      conversation.messages.push(message);
      conversation.messages = conversation.messages.slice(-historyLimit);
      updateConversationAfterMessage(conversation);
    }

    syncPromptVisibility();
    if (scroll) {
      scrollMessages();
    }
  }

  function restoreConversations() {
    const parsed = parseConversations();
    state.conversations = parsed.conversations;
    state.activeId = parsed.activeId || (state.conversations[state.conversations.length - 1] || {}).id || null;
    if (!state.activeId) {
      createConversation({ activate: true, save: true, render: false });
    }
    renderConversation();
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

  function setSidebarOpen(nextState) {
    state.sidebarOpen = nextState;
    if (sidebar) {
      sidebar.classList.toggle("is-collapsed", !nextState);
    }
    if (sidebarToggle) {
      sidebarToggle.classList.toggle("is-active", nextState);
      sidebarToggle.setAttribute("aria-label", nextState ? "Masquer les discussions" : "Afficher les discussions");
      sidebarToggle.title = nextState ? "Masquer les discussions" : "Discussions";
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
          "X-CSRFToken": getCookie("csrftoken") || "",
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
        downloadUrl: data.download_url || null,
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
  newConversationBtn.addEventListener("click", () => createConversation());
  sidebarNewBtn.addEventListener("click", () => createConversation());
  sidebarToggle.addEventListener("click", () => setSidebarOpen(!state.sidebarOpen));
  sidebarList.addEventListener("click", (event) => {
    const button = event.target.closest(".chat-thread");
    if (button) {
      switchConversation(button.dataset.threadId);
    }
  });

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

  restoreConversations();
  setSidebarOpen(!window.matchMedia("(max-width: 720px)").matches);
  updateNetworkStatus();
})();
