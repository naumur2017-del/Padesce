path = "App_PADESCE/core/views.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "<<<<<<< Updated upstream" in line:
        skip = True
        continue
    if "=======" in line:
        skip = False
        continue
    if ">>>>>>> Stashed changes" in line:
        continue
    if not skip:
        new_lines.append(line)

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Conflict markers removed, keeping Stashed version.")
