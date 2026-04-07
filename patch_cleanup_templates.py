import re

# Cleanup home.html
HOME_PATH = r"F:\NAUMUR\NAUMUR - TRAVAUX EN COURS\Utlisateurs\EYOUM ATOCK\CALL APP\App_PADESCE-main\App_PADESCE-main\templates\home.html"

with open(HOME_PATH, "r", encoding="utf-8") as f:
    home_content = f.read()

# Remove the transcription card/section
home_content = re.sub(
    r'<div class="card".*?Transcrire tous les audios.*?</div>\s*</div>',
    "",
    home_content,
    flags=re.DOTALL,
)

# Remove the JS logic for transcription in home.html
home_content = re.sub(
    r"// Transcription Logic.*?// End Transcription Logic", "", home_content, flags=re.DOTALL
)

# Also remove specific event listeners if the above didn't catch them
home_content = re.sub(
    r'const startBtn = document\.getElementById\("js-start-transcription"\);.*?}\);?\s*',
    "",
    home_content,
    flags=re.DOTALL,
)

with open(HOME_PATH, "w", encoding="utf-8") as f:
    f.write(home_content)

print("home.html cleaned.")

# Cleanup index.html
INDEX_PATH = r"F:\NAUMUR\NAUMUR - TRAVAUX EN COURS\Utlisateurs\EYOUM ATOCK\CALL APP\App_PADESCE-main\App_PADESCE-main\templates\appels\index.html"

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    index_content = f.read()

# Remove the top selection-bar for transcription
index_content = re.sub(
    r'<div class="selection-bar">.*?Transcription rapide.*?</div>\s*</div>',
    "",
    index_content,
    flags=re.DOTALL,
)

# Remove the progress wrap
index_content = re.sub(
    r'<div id="filtered-transcription-progress-wrap".*?</div>\s*</div>',
    "",
    index_content,
    flags=re.DOTALL,
)

# Remove the "Transcription" button from the table
index_content = index_content.replace(
    '<button type="button" class="btn-small js-transcription" {% if not a.audio_file %}disabled{% endif %}>Transcription</button>',
    "",
)

# Remove the transcription modal
index_content = re.sub(
    r'<div id="js-transcription-modal".*?</div>\s*</div>', "", index_content, flags=re.DOTALL
)

# Remove the JS transcription logic
index_content = re.sub(
    r"// Transcription modal logic.*?// End transcription modal logic",
    "",
    index_content,
    flags=re.DOTALL,
)

index_content = re.sub(
    r"// Start filtered transcription.*?// End filtered transcription",
    "",
    index_content,
    flags=re.DOTALL,
)

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(index_content)

print("index.html cleaned.")
