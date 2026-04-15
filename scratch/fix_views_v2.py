import re

path = r"d:\Documents\NAUMUR\Projet PADESCE Call\Padesce\App_PADESCE\core\views.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Refined fix for formateurs part
formateur_iter_block = """    for row in rows:
        row.consultant_display_name = _consultant_formateur_display_name(row)
        row.consultant_reference = row.reference_code or "-"
        row.consultant_scope_label = row.formation or "-"
        row.consultant_telephone = row.telephone or "-"
        row.consultant_has_audio = formateur_has_any_audio(row)
        row.consultant_has_form = formateur_has_any_form_data(row)
        # Mocking fields for template compatibility
        row.nom = row.consultant_display_name
        row.apprenant_id = row.consultant_reference
        row.classe_label = row.consultant_scope_label
        row.telephone1 = row.consultant_telephone
        row.telephone2 = None
        row.consultant_class_display = row.consultant_scope_label
        row.classe = None"""

# Find the formateur loop and replace it

formateur_pattern = (
    re.escape("    for row in rows:")
    + r".*?"
    + re.escape("row.consultant_has_form = formateur_has_any_form_data(row)")
    + r".*?row\.telephone1 = row\.consultant_telephone"
)
# Note: we need to be careful with dots and newlines
if re.search(formateur_pattern, content, re.DOTALL):
    content = re.sub(formateur_pattern, formateur_iter_block, content, flags=re.DOTALL)
    print("Success replacing formateur block")
else:
    print("Formateur pattern not found exactly. Checking current state...")
    # Just replace the smaller known part
    small_target = "        row.telephone1 = row.consultant_telephone"
    small_replacement = (
        "        row.telephone1 = row.consultant_telephone\n"
        "        row.telephone2 = None\n"
        "        row.consultant_class_display = row.consultant_scope_label\n"
        "        row.classe = None"
    )
    if small_target in content:
        content = content.replace(small_target, small_replacement)
        print("Success with small replacement")
    else:
        print("Small target not found either.")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
