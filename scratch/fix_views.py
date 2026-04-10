path = r"d:\Documents\NAUMUR\Projet PADESCE Call\Padesce\App_PADESCE\core\views.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

target = '            elif (getattr(answers, "commentaire", "") or "RAS").strip().upper() == "RAS":\n        Appel.objects.filter(is_active=True)'
replacement = """            elif (getattr(answers, "commentaire", "") or "RAS").strip().upper() == "RAS":
                status_display = "Formulaire RAS"
            else:
                status_display = "Formulaire rempli"
        app.consultant_status_display = status_display

        if app.code in priorities:
            app.priority_avg = priorities[app.code]["avg_satisfaction"]

        app.consultant_display_name = app.nom
        app.consultant_reference = app.apprenant_id or "-"
        app.consultant_scope_label = app.consultant_class_display
        app.consultant_telephone = app.telephone1 or app.telephone2 or "-"

        rows.append(app)

    rows.sort(key=_consultant_row_sort_key)

    # Unfiltered snapshot for card counts (must match satisfaction analysis page)
    _all_eligible_qs = (
        Appel.objects.filter(is_active=True)"""

if target in content:
    new_content = content.replace(target, replacement)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Success")
else:
    # Try with different line endings or slightly different whitespace
    print("Target not found exactly. Trying alternative...")
    # Escape some stuff
    import re

    # We want to find the elif line followed immediately by Appel.objects.filter
    pattern = (
        re.escape('elif (getattr(answers, "commentaire", "") or "RAS").strip().upper() == "RAS":')
        + r"\s*"
        + re.escape("Appel.objects.filter(is_active=True)")
    )
    if re.search(pattern, content):
        new_content = re.sub(pattern, replacement, content)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Success with regex")
    else:
        print("Pattern NOT found at all.")
        # Print a slice of content to see what's there
        idx = content.find('elif (getattr(answers, "commentaire", "") or "RAS")')
        if idx != -1:
            print("Found elif line start. Next 200 chars:")
            print(repr(content[idx : idx + 200]))
        else:
            print("Even elif line start NOT found.")
