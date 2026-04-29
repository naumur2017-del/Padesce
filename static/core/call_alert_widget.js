(function () {
  const root = document.getElementById("callAlertWidget");
  if (!root) return;

  const rawPath = window.location.pathname || "/";
  const path = rawPath.replace(/^\/padesce(?=\/|$)/, "") || "/";
  const source =
    path === "/appels/" || path === "/appels"
      ? "padesce"
      : path === "/cga/" || path === "/cga"
        ? "cga"
        : "";
  if (!source) return;

  root.hidden = false;

  const isAdmin = root.dataset.isAdmin === "true";
  const optionsUrl = root.dataset.optionsUrl;
  const createUrl = root.dataset.createUrl;
  const listUrl = root.dataset.listUrl;
  const alertsBaseUrl = listUrl.replace(/list\/?$/, "");
  const sourceLabel = source === "cga" ? "CGA" : "PADESCE";
  const recentActions = [];
  let alertOptions = [];
  let statusOptions = [];
  let currentTab = "report";
  let toastTimer = null;

  const fab = document.getElementById("callAlertFab");
  const panel = document.getElementById("callAlertPanel");
  const closeBtn = document.getElementById("callAlertClose");
  const subtitle = document.getElementById("callAlertSubtitle");
  const typeContainer = document.getElementById("callAlertTypes");
  const detailsInput = document.getElementById("callAlertDetails");
  const contextText = document.getElementById("callAlertContext");
  const submitBtn = document.getElementById("callAlertSubmit");
  const countBadge = document.getElementById("callAlertCount");
  const tabs = Array.from(root.querySelectorAll("[data-alert-tab]"));
  const views = Array.from(root.querySelectorAll("[data-alert-view]"));
  const inboxTab = document.getElementById("callAlertInboxTab");
  const listTitle = document.getElementById("callAlertListTitle");
  const listMeta = document.getElementById("callAlertListMeta");
  const includeDone = document.getElementById("callAlertIncludeDone");
  const listEl = document.getElementById("callAlertList");
  const detailBackdrop = document.getElementById("callAlertDetailBackdrop");
  const detailClose = document.getElementById("callAlertDetailClose");
  const detailTitle = document.getElementById("callAlertDetailTitle");
  const detailKicker = document.getElementById("callAlertDetailKicker");
  const detailBody = document.getElementById("callAlertDetailBody");
  const toast = document.getElementById("callAlertToast");

  if (subtitle) subtitle.textContent = `Alertes ${sourceLabel}`;
  if (inboxTab && isAdmin) inboxTab.textContent = "Recevoir les alertes";
  if (listTitle) listTitle.textContent = isAdmin ? "Alertes recues" : "Mes alertes";

  function csrfToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatDate(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "-";
    return date.toLocaleString();
  }

  function truncate(value, limit) {
    const text = String(value || "").trim();
    if (text.length <= limit) return text;
    return `${text.slice(0, limit - 1)}...`;
  }

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.hidden = true;
    }, 3200);
  }

  function statusClass(status) {
    if (status === "doing") return "doing";
    if (status === "done") return "done";
    return "todo";
  }

  function activeRow() {
    const last = recentActions.find((item) => item.row_id);
    if (last) {
      const escapedId =
        window.CSS && CSS.escape
          ? CSS.escape(String(last.row_id))
          : String(last.row_id).replace(/"/g, '\\"');
      const found = document.querySelector(`tr[data-id="${escapedId}"]`);
      if (found) return found;
    }
    return (
      document.querySelector('tr[data-id][data-status="en_cours"]') ||
      document.querySelector('tr[data-id][data-status="pause"]') ||
      document.querySelector("tr[data-id]")
    );
  }

  function currentContext() {
    const row = activeRow();
    return {
      source,
      source_label: sourceLabel,
      page_path: window.location.pathname + window.location.search,
      page_title: document.title || "",
      call_id: row?.dataset?.id || "",
      call_label: row?.dataset?.name || "",
      call_status: row?.dataset?.status || "",
    };
  }

  function updateContextLine() {
    if (!contextText) return;
    const ctx = currentContext();
    const parts = [`Contexte: ${ctx.source_label}`];
    if (ctx.call_id) parts.push(`ligne #${ctx.call_id}`);
    if (ctx.call_label) parts.push(ctx.call_label);
    if (ctx.call_status) parts.push(`statut ${ctx.call_status}`);
    contextText.textContent = parts.join(" - ");
  }

  function rememberAction(element) {
    const row = element.closest("tr[data-id]");
    if (!row) return;
    const label = (element.getAttribute("aria-label") || element.textContent || "").replace(/\s+/g, " ").trim();
    recentActions.unshift({
      label: label || "Action",
      row_id: row.dataset.id || "",
      row_label: row.dataset.name || "",
      row_status: row.dataset.status || "",
      at: new Date().toISOString(),
      page: window.location.pathname,
    });
    recentActions.splice(8);
    updateContextLine();
  }

  document.addEventListener(
    "click",
    (event) => {
      const element = event.target.closest("button, a");
      if (!element || root.contains(element)) return;
      rememberAction(element);
    },
    true
  );

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.ok === false) {
      throw new Error(data.error || response.statusText || "Erreur");
    }
    return data;
  }

  async function loadOptions() {
    if (alertOptions.length) return;
    const data = await fetchJson(optionsUrl, { headers: { Accept: "application/json" } });
    alertOptions = data.options || [];
    statusOptions = data.statuses || [];
    renderOptions();
  }

  function renderOptions() {
    if (!typeContainer) return;
    typeContainer.innerHTML = alertOptions
      .map(
        (item) => `
          <label class="call-alert-type-option">
            <input type="checkbox" value="${escapeHtml(item.value)}">
            <span>
              <span class="call-alert-type-title">${escapeHtml(item.label)}</span>
              <span class="call-alert-type-desc">${escapeHtml(item.description)}</span>
            </span>
          </label>
        `
      )
      .join("");
  }

  function selectedTypes() {
    return Array.from(typeContainer.querySelectorAll("input[type='checkbox']:checked")).map(
      (input) => input.value
    );
  }

  function resetReportForm() {
    typeContainer.querySelectorAll("input[type='checkbox']").forEach((input) => {
      input.checked = false;
    });
    if (detailsInput) detailsInput.value = "";
    updateContextLine();
  }

  function setTab(tab) {
    currentTab = tab;
    tabs.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.alertTab === tab);
    });
    views.forEach((view) => {
      view.classList.toggle("is-active", view.dataset.alertView === tab);
    });
    if (tab === "inbox") refreshList();
  }

  function openPanel() {
    loadOptions().catch(() => showToast("Impossible de charger les types d'alerte."));
    updateContextLine();
    panel.classList.add("visible");
    panel.setAttribute("aria-hidden", "false");
    document.getElementById("chatWindow")?.classList.remove("visible");
    document.getElementById("chatWindow")?.setAttribute("aria-hidden", "true");
    refreshList({ quiet: true });
  }

  function closePanel() {
    panel.classList.remove("visible");
    panel.setAttribute("aria-hidden", "true");
  }

  async function submitAlert() {
    const alertTypes = selectedTypes();
    const details = detailsInput?.value.trim() || "";
    if (!alertTypes.length && !details) {
      showToast("Selectionnez au moins un type d'alerte.");
      return;
    }
    const ctx = currentContext();
    submitBtn.disabled = true;
    try {
      await fetchJson(createUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
          Accept: "application/json",
        },
        body: JSON.stringify({
          source: ctx.source,
          alert_types: alertTypes,
          details,
          page_path: ctx.page_path,
          page_title: ctx.page_title,
          call_id: ctx.call_id,
          call_label: ctx.call_label,
          call_status: ctx.call_status,
          last_actions: recentActions,
        }),
      });
      resetReportForm();
      showToast("Alerte envoyee.");
      refreshList({ quiet: true });
    } catch (error) {
      showToast("Alerte non envoyee. Verifiez la connexion.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  async function refreshList(options = {}) {
    const scope = isAdmin ? "received" : "mine";
    const includeDoneValue = includeDone?.checked ? "1" : "0";
    const url = `${listUrl}?scope=${encodeURIComponent(scope)}&include_done=${includeDoneValue}`;
    try {
      const data = await fetchJson(url, { headers: { Accept: "application/json" } });
      renderList(data.alerts || []);
      setBadge(data.unread_count || 0);
    } catch (error) {
      if (!options.quiet) showToast("Impossible de charger les alertes.");
    }
  }

  function setBadge(count) {
    if (!countBadge) return;
    const value = Number(count || 0);
    countBadge.hidden = false;
    countBadge.textContent = value > 99 ? "99+" : String(value);
  }

  function renderList(alerts) {
    if (!listEl) return;
    if (listMeta) listMeta.textContent = `${alerts.length} alerte${alerts.length > 1 ? "s" : ""}`;
    if (!alerts.length) {
      listEl.innerHTML = '<div class="call-alert-empty">Aucune alerte a afficher.</div>';
      return;
    }
    listEl.innerHTML = alerts
      .map((alert) => {
        const title = alert.alert_type_labels?.length
          ? alert.alert_type_labels.join(", ")
          : truncate(alert.details, 70) || "Alerte";
        const call = alert.call_label || (alert.call_id ? `Ligne #${alert.call_id}` : "Page courante");
        const reaction = alert.reaction_label ? `Reaction ${alert.reaction_label}` : "Reaction en attente";
        return `
          <button class="call-alert-item" type="button" data-alert-id="${alert.id}">
            <span class="call-alert-item-top">
              <span>
                <span class="call-alert-item-title">${escapeHtml(title)}</span>
                <span class="call-alert-item-meta">
                  ${escapeHtml(alert.reporter_name)} - ${escapeHtml(alert.source_label)} - ${escapeHtml(call)}<br>
                  ${escapeHtml(formatDate(alert.created_at))} - ${escapeHtml(reaction)}
                </span>
              </span>
              <span class="call-alert-status ${statusClass(alert.status)}">${escapeHtml(alert.status_label)}</span>
            </span>
          </button>
        `;
      })
      .join("");
  }

  async function openDetail(id) {
    try {
      const data = await fetchJson(`${alertsBaseUrl}${id}/`, {
        headers: { Accept: "application/json" },
      });
      renderDetail(data.alert, data.is_admin);
      detailBackdrop.hidden = false;
      refreshList({ quiet: true });
    } catch (error) {
      showToast("Impossible d'ouvrir cette alerte.");
    }
  }

  function renderInfo(label, value) {
    return `
      <div class="call-alert-info">
        <span>${escapeHtml(label)}</span>
        <div>${escapeHtml(value || "-")}</div>
      </div>
    `;
  }

  function renderActionList(items) {
    if (!items || !items.length) {
      return '<div class="call-alert-empty">Aucune action recente.</div>';
    }
    return `
      <div class="call-alert-action-list">
        ${items
          .map((item) => {
            const label = item.label || item.target || item.type || "Action";
            const row = item.row_label || item.page || "";
            const at = item.at || "";
            return `<div class="call-alert-action-line">${escapeHtml(label)}${row ? ` - ${escapeHtml(row)}` : ""}${at ? ` - ${escapeHtml(formatDate(at))}` : ""}</div>`;
          })
          .join("")}
      </div>
    `;
  }

  function renderAdminForm(alert) {
    if (!isAdmin) return "";
    const statusSelect = statusOptions
      .map(
        (item) =>
          `<option value="${escapeHtml(item.value)}" ${item.value === alert.status ? "selected" : ""}>${escapeHtml(item.label)}</option>`
      )
      .join("");
    return `
      <div class="call-alert-admin-form">
        <label>
          Statut
          <select id="callAlertAdminStatus">${statusSelect}</select>
        </label>
        <label>
          Message pour l'operateur
          <textarea id="callAlertAdminMessage" rows="3" placeholder="Ex: on regarde le probleme maintenant">${escapeHtml(alert.admin_message || "")}</textarea>
        </label>
        <label>
          Commentaire de resolution
          <textarea id="callAlertResolutionComment" rows="3" placeholder="Obligatoire quand le statut passe a Done">${escapeHtml(alert.resolution_comment || "")}</textarea>
        </label>
        <button class="call-alert-admin-save" type="button" data-alert-save="${alert.id}">
          <i class="fa-solid fa-check" aria-hidden="true"></i>
          <span>Mettre a jour</span>
        </button>
      </div>
    `;
  }

  function renderDetail(alert) {
    const title = alert.alert_type_labels?.length
      ? alert.alert_type_labels.join(", ")
      : "Alerte";
    detailTitle.textContent = title;
    detailKicker.textContent = `${alert.source_label} - ${alert.status_label}`;
    const activity = alert.reporter_activity || {};
    const onlineLabel = activity.is_online ? "En ligne" : "Hors ligne";
    const reaction = alert.reaction_label || "En attente";
    const resolution = alert.resolution_label || "Non resolu";
    const chips = (alert.alert_type_labels || [])
      .map((label) => `<span class="call-alert-chip">${escapeHtml(label)}</span>`)
      .join("");

    detailBody.innerHTML = `
      <div class="call-alert-detail-grid">
        ${renderInfo("Operateur", alert.reporter_name)}
        ${renderInfo("Presence", `${onlineLabel}${activity.current_page ? ` - ${activity.current_page}` : ""}`)}
        ${renderInfo("Page", alert.page_title || alert.page_path)}
        ${renderInfo("Ligne", alert.call_label || alert.call_id || "-")}
        ${renderInfo("Statut appel", alert.call_status || "-")}
        ${renderInfo("Statut alerte", alert.status_label)}
        ${renderInfo("Creee le", formatDate(alert.created_at))}
        ${renderInfo("Temps de reaction", reaction)}
        ${renderInfo("Resolution", resolution)}
        ${renderInfo("Assigne a", alert.assigned_to || "-")}
      </div>

      <div class="call-alert-section-title">Types selectionnes</div>
      <div class="call-alert-chip-row">${chips || '<span class="call-alert-chip">Autre</span>'}</div>

      <div class="call-alert-section-title">Precision operateur</div>
      <div class="call-alert-info"><div>${escapeHtml(alert.details || "Aucune precision.")}</div></div>

      ${alert.admin_message ? `<div class="call-alert-section-title">Message support</div><div class="call-alert-info"><div>${escapeHtml(alert.admin_message)}</div></div>` : ""}
      ${alert.resolution_comment ? `<div class="call-alert-section-title">Commentaire de resolution</div><div class="call-alert-info"><div>${escapeHtml(alert.resolution_comment)}</div></div>` : ""}

      <div class="call-alert-section-title">Dernieres actions capturees</div>
      ${renderActionList(alert.last_actions || [])}

      <div class="call-alert-section-title">Activite recente serveur</div>
      ${renderActionList(alert.recent_activity || [])}

      ${renderAdminForm(alert)}
    `;

    const saveBtn = detailBody.querySelector("[data-alert-save]");
    saveBtn?.addEventListener("click", () => updateAlert(alert.id));
  }

  async function updateAlert(id) {
    const status = document.getElementById("callAlertAdminStatus")?.value || "todo";
    const adminMessage = document.getElementById("callAlertAdminMessage")?.value.trim() || "";
    const resolutionComment =
      document.getElementById("callAlertResolutionComment")?.value.trim() || "";
    if (status === "done" && !resolutionComment) {
      showToast("Le commentaire de resolution est obligatoire pour Done.");
      return;
    }
    try {
      await fetchJson(`${alertsBaseUrl}${id}/update/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
          Accept: "application/json",
        },
        body: JSON.stringify({
          status,
          admin_message: adminMessage,
          resolution_comment: resolutionComment,
        }),
      });
      showToast("Alerte mise a jour.");
      await openDetail(id);
      refreshList({ quiet: true });
    } catch (error) {
      if (String(error.message || "").includes("commentaire")) {
        showToast("Commentaire obligatoire pour Done.");
      } else {
        showToast("Mise a jour impossible.");
      }
    }
  }

  fab?.addEventListener("click", () => {
    if (panel.classList.contains("visible")) {
      closePanel();
    } else {
      openPanel();
    }
  });
  closeBtn?.addEventListener("click", closePanel);
  detailClose?.addEventListener("click", () => {
    detailBackdrop.hidden = true;
  });
  detailBackdrop?.addEventListener("click", (event) => {
    if (event.target === detailBackdrop) detailBackdrop.hidden = true;
  });
  tabs.forEach((button) => {
    button.addEventListener("click", () => setTab(button.dataset.alertTab));
  });
  includeDone?.addEventListener("change", () => refreshList());
  submitBtn?.addEventListener("click", submitAlert);
  listEl?.addEventListener("click", (event) => {
    const item = event.target.closest("[data-alert-id]");
    if (!item) return;
    openDetail(item.dataset.alertId);
  });

  setTab(currentTab);
  loadOptions().catch(() => {});
  refreshList({ quiet: true });
  window.setInterval(() => refreshList({ quiet: true }), 30000);
})();
