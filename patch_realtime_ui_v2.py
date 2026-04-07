PATH = r"F:\NAUMUR\NAUMUR - TRAVAUX EN COURS\Utlisateurs\EYOUM ATOCK\CALL APP\App_PADESCE-main\App_PADESCE-main\templates\appels\index.html"

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

# The old real-time logic (if any) was looking for .class-summary-card
# Let's replace the JS_UPDATE_LOGIC I added earlier with one that updates the select options and the badge.

OLD_RT_LOGIC = """    // Update class badges globally if info is provided
    if (data.class_progress) {
        const info = data.class_progress;
        // Find the card for this class
        document.querySelectorAll('.class-summary-card .class-name').forEach(el => {
            if (el.textContent.trim() === info.label) {
                const card = el.closest('.class-summary-card');
                const badgeContainer = card.querySelector('.mt-2');
                if (badgeContainer) {
                    if (info.reached) {
                        badgeContainer.innerHTML = '<div class="badge status-badge badge-success">Objectif Atteint ✅</div>';
                    } else {
                        badgeContainer.innerHTML = `<div class="badge status-badge badge-warning">${info.termines} / ${info.total} (${info.pct}%)</div>`;
                    }
                }
            }
        });
    }"""

NEW_RT_LOGIC = """    // Update class badges globally in the filter dropdown
    if (data.class_progress) {
        const info = data.class_progress;
        const select = document.getElementById('js-classe-filter');
        if (select) {
            for (let opt of select.options) {
                if (opt.value === info.label) {
                    if (info.reached) {
                        opt.textContent = `${info.label} (Objectif Atteint ✅)`;
                    } else {
                        opt.textContent = `${info.label} (${info.termines}/${info.total} - ${info.pct}%)`;
                    }
                    break;
                }
            }
            // Also update the standalone badge if this class is currently selected
            if (select.value === info.label) {
                const badgeContainer = document.getElementById('js-class-threshold-badge');
                if (badgeContainer) {
                    if (info.reached) {
                        badgeContainer.innerHTML = '<span class="badge status-badge badge-success" style="font-size:0.85rem; padding:4px 8px;">Objectif Atteint ✅</span>';
                    } else {
                        badgeContainer.innerHTML = `<span class="badge status-badge badge-warning" style="font-size:0.85rem; padding:4px 8px;">${info.termines}/${info.total} (${info.pct}%)</span>`;
                    }
                }
            }
        }
        // Update local classeProgress variable for future filter changes
        if (typeof classeProgress !== 'undefined') {
            const idx = classeProgress.findIndex(p => p.classe === info.label);
            if (idx !== -1) {
                classeProgress[idx] = {
                    classe: info.label,
                    total: info.total,
                    termines: info.termines,
                    reached: info.reached,
                    pct: info.pct
                };
            } else {
                classeProgress.push({
                    classe: info.label,
                    total: info.total,
                    termines: info.termines,
                    reached: info.reached,
                    pct: info.pct
                });
            }
        }
    }"""

# Use a safer string replacement or regex if the old logic was escaped
content = content.replace(OLD_RT_LOGIC, NEW_RT_LOGIC)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch real-time UI v2 complete.")
