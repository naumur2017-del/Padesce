import os

PATH = r"F:\NAUMUR\NAUMUR - TRAVAUX EN COURS\Utlisateurs\EYOUM ATOCK\CALL APP\App_PADESCE-main\App_PADESCE-main\templates\appels\index.html"

with open(PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# We need to find the updateRow function or the logic that handles the response from stop recording/termination
# and add the logic to update class badges at the top.

# First, let's identify where the badges are in the HTML
# <div class="badge status-badge badge-success">Objectif Atteint ✅</div>
# or <div class="badge status-badge badge-warning">...</div>
# They are inside <div class="class-summary-card">...</div>

JS_UPDATE_LOGIC = """
    // Update class badges globally if info is provided
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
    }
"""

# Insert this logic into the fetch response handler for 'terminer' and 'upload_audio'
# In the patched index.html, we have:
# fetch(`/appels/${callId}/action/`, { ... }).then(r => r.json()).then(data => { ... })

# We'll look for where 'terminer' is handled
if "if (data.ok && action === 'terminer')" in content:
    content = content.replace(
        "if (data.ok && action === 'terminer') {",
        "if (data.ok && action === 'terminer') {\\n" + JS_UPDATE_LOGIC
    )

# Also for upload_audio response
if "if (data.audio_saved)" in content:
    content = content.replace(
        "if (data.audio_saved) {",
        "if (data.audio_saved) {\\n" + JS_UPDATE_LOGIC
    )

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch real-time UI complete.")
