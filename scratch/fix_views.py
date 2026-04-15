path = r"d:\Documents\NAUMUR\Projet PADESCE Call\Padesce\App_PADESCE\core\views.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

target = (
    '            elif (getattr(answers, "commentaire", "") or "RAS").strip().upper() == "RAS":\n'
    "        Appel.objects.filter(is_active=True)"
)
replacement = (
    """            elif (getattr(answers, "commentaire", "") or "RAS").strip().upper() == "RAS":"""
    """\n                status_display = "Formulaire RAS"""
    """\n            else:"""
    """\n                status_display = "Formulaire rempli"""
    """\n        app.consultant_status_display = status_display"""
)

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
