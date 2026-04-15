import re

PATH = (
    r"F:\NAUMUR\NAUMUR - TRAVAUX EN COURS\Utlisateurs\EYOUM ATOCK\CALL APP"
    r"\App_PADESCE-main\App_PADESCE-main\templates\appels\index.html"
)

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove the old class summary section

# The section starts with <div class="class-summary-container"> and ends with </div>
# plus some spacing
content = re.sub(
    r'<div class="class-summary-container">.*?</div>\s*</div>', "", content, flags=re.DOTALL
)

# 2. Update the class select to use enriched classes
# Old:
# <select name="classe" class="input">
#   <option value="">Classe</option>
#   {% for p in filters.classes %}
#     <option value="{{ p }}" {% if filters.classe == p %}selected{% endif %}>{{ p }}</option>
#   {% endfor %}
# </select>

OLD_SELECT = """    <select name="classe" class="input">
      <option value="">Classe</option>
      {% for p in filters.classes %}
        <option value="{{ p }}" {% if filters.classe == p %}selected{% endif %}>{{ p }}</option>
      {% endfor %}
    </select>"""

NEW_SELECT = """    <select name="classe" class="input" id="js-classe-filter">
      <option value="">Classe</option>
      {% for p in filters.classes_enriched %}
        <option value="{{ p.value }}" 
                {% if filters.classe == p.value %}selected{% endif %}>{{ p.label }}</option>
      {% endfor %}
    </select>
    <div id="js-class-threshold-badge" style="display:inline-block; margin-left:5px;"></div>"""

content = content.replace(OLD_SELECT, NEW_SELECT)

# 3. Add JS logic to show a prominent badge next to the filter
JS_LOGIC = """
    const classeFilter = document.getElementById('js-classe-filter');
    const badgeContainer = document.getElementById('js-class-threshold-badge');
    const classeProgress = {{ classe_progress_json|safe }};

    function updateFilterBadge() {
        const val = classeFilter.value;
        badgeContainer.innerHTML = '';
        if (!val) return;
        
        const prog = classeProgress.find(p => p.classe === val);
        if (prog) {
            if (prog.reached) {
                badgeContainer.innerHTML = '<span class="badge status-badge badge-success" '
                'style="font-size:0.85rem; padding:4px 8px;">Objectif Atteint ✅</span>';
            } else {
                badgeContainer.innerHTML = (
                    `<span class="badge status-badge badge-warning" `
                    `style="font-size:0.85rem; padding:4px 8px;">`
                    `${prog.termines}/${prog.total} (${prog.pct}%)</span>`
                );
            }
        }
    }

    classeFilter.addEventListener('change', updateFilterBadge);
    updateFilterBadge(); // init
"""

# Append this logic to the bottom of the script section
# We'll look for the end of the script before extra logic we added earlier
if "updateFilterBadge" not in content:
    content = content.replace("</script>", JS_LOGIC + "\n</script>")

with open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch refine threshold complete.")
