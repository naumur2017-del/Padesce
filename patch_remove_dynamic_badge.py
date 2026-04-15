PATH = (
    r"F:\NAUMUR\NAUMUR - TRAVAUX EN COURS\Utlisateurs\EYOUM ATOCK\CALL APP"
    r"\App_PADESCE-main\App_PADESCE-main\templates\appels\index.html"
)

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove the standalone badge div
content = content.replace(
    '<div id="js-class-threshold-badge" style="display:inline-block; margin-left:5px;"></div>', ""
)

# 2. Update the JS to remove updateFilterBadge but keep the select enrichment update
# Actually, the logic in updateFilterBadge was updating BOTH.
# I will just remove the line that updates the badgeContainer.

content = content.replace("badgeContainer.innerHTML = '';", "")
content = content.replace(
    'badgeContainer.innerHTML = \'<span class="badge status-badge badge-success" '
    'style="font-size:0.85rem; padding:4px 8px;">Objectif Atteint ✅</span>\';',
    "",
)
content = content.replace(
    'badgeContainer.innerHTML = `<span class="badge status-badge badge-warning" '
    'style="font-size:0.85rem; padding:4px 8px;">${prog.termines}/${prog.total} '
    "(${prog.pct}%)</span>`;",
    "",
)

# Also for the real-time v2 logic
content = content.replace(
    """            // Also update the standalone badge if this class is currently selected
            if (select.value === info.label) {
                const badgeContainer = document.getElementById('js-class-threshold-badge');
                if (badgeContainer) {
                    if (info.reached) {
                        badgeContainer.innerHTML = '<span class="badge status-badge badge-success" '
                        'style="font-size:0.85rem; padding:4px 8px;">Objectif Atteint ✅</span>';
                    } else {
                        badgeContainer.innerHTML = (
                            `<span class="badge status-badge badge-warning" `
                            `style="font-size:0.85rem; padding:4px 8px;">`
                            `${info.termines}/${info.total} (${info.pct}%)</span>`
                        );
                    }
                }
            }""",
    "",
)

# Cleanup unused badgeContainer constant
content = content.replace(
    "const badgeContainer = document.getElementById('js-class-threshold-badge');", ""
)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch remove dynamic badge complete.")
