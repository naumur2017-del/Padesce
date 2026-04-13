html_path = "templates/appels/index.html"
with open(html_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add HTML modal
chunk1_target = """    <div class="modal-actions">
      <a id="js-transcription-download" class="btn btn-ghost btn-sm" href="#" download>Telecharger</a>
      <button type="button" class="btn btn-primary btn-sm" data-transcription-close>Fermer</button>
    </div>
  </div>
</div>"""  # noqa: E501
chunk1_replacement = (
    chunk1_target
    + """

<div id="js-satisfaction-modal" class="modal-backdrop" hidden>
  <div class="modal-panel" style="width: 550px; max-height: 90vh; overflow-y: auto;">
    <h2>Enregistrement de l'appel (PADESCE)</h2>
    <div class="modal-detail">
      <span class="modal-label">Nom :</span>
      <span id="js-sat-modal-nom">-</span>
    </div>
    
    <div style="margin: 10px 0; border: 1px solid var(--border); padding: 10px; border-radius: 8px;">
      <h4 style="margin-top:0; margin-bottom: 8px;">Questionnaire de satisfaction (Cochez de 1 à 5)</h4>
      <div id="js-sat-questions">
        <div class="form-inline" style="justify-content:space-between; margin-bottom:4px;">
          <label style="font-size:0.85rem;">1. Clarté des exposés et explications</label>
          <div style="font-size:0.85rem;"><input type="radio" name="q1" value="1"> 1 <input type="radio" name="q1" value="2"> 2 <input type="radio" name="q1" value="3" checked> 3 <input type="radio" name="q1" value="4"> 4 <input type="radio" name="q1" value="5"> 5</div>
        </div>
        <div class="form-inline" style="justify-content:space-between; margin-bottom:4px;">
          <label style="font-size:0.85rem;">2. Interaction avec le formateur</label>
          <div style="font-size:0.85rem;"><input type="radio" name="q2" value="1"> 1 <input type="radio" name="q2" value="2"> 2 <input type="radio" name="q2" value="3" checked> 3 <input type="radio" name="q2" value="4"> 4 <input type="radio" name="q2" value="5"> 5</div>
        </div>
        <div class="form-inline" style="justify-content:space-between; margin-bottom:4px;">
          <label style="font-size:0.85rem;">3. Maîtrise du contenu par le formateur</label>
          <div style="font-size:0.85rem;"><input type="radio" name="q3" value="1"> 1 <input type="radio" name="q3" value="2"> 2 <input type="radio" name="q3" value="3" checked> 3 <input type="radio" name="q3" value="4"> 4 <input type="radio" name="q3" value="5"> 5</div>
        </div>
        <div class="form-inline" style="justify-content:space-between; margin-bottom:4px;">
          <label style="font-size:0.85rem;">4. Adéquation et confort de la salle</label>
          <div style="font-size:0.85rem;"><input type="radio" name="q4" value="1"> 1 <input type="radio" name="q4" value="2"> 2 <input type="radio" name="q4" value="3" checked> 3 <input type="radio" name="q4" value="4"> 4 <input type="radio" name="q4" value="5"> 5</div>
        </div>
        <div class="form-inline" style="justify-content:space-between; margin-bottom:4px;">
          <label style="font-size:0.85rem;">5. Disponibilité du matériel pédagogique</label>
          <div style="font-size:0.85rem;"><input type="radio" name="q5" value="1"> 1 <input type="radio" name="q5" value="2"> 2 <input type="radio" name="q5" value="3" checked> 3 <input type="radio" name="q5" value="4"> 4 <input type="radio" name="q5" value="5"> 5</div>
        </div>
        <div class="form-inline" style="justify-content:space-between; margin-bottom:4px;">
          <label style="font-size:0.85rem;">6. Organisation et gestion du temps</label>
          <div style="font-size:0.85rem;"><input type="radio" name="q6" value="1"> 1 <input type="radio" name="q6" value="2"> 2 <input type="radio" name="q6" value="3" checked> 3 <input type="radio" name="q6" value="4"> 4 <input type="radio" name="q6" value="5"> 5</div>
        </div>
        <div class="form-inline" style="justify-content:space-between; margin-bottom:4px;">
          <label style="font-size:0.85rem;">7. Utilité et applicabilité de la formation</label>
          <div style="font-size:0.85rem;"><input type="radio" name="q7" value="1"> 1 <input type="radio" name="q7" value="2"> 2 <input type="radio" name="q7" value="3" checked> 3 <input type="radio" name="q7" value="4"> 4 <input type="radio" name="q7" value="5"> 5</div>
        </div>
        <div class="form-inline" style="justify-content:space-between; margin-bottom:4px;">
          <label style="font-size:0.85rem;">8. Adéquation du contenu avec les besoins</label>
          <div style="font-size:0.85rem;"><input type="radio" name="q8" value="1"> 1 <input type="radio" name="q8" value="2"> 2 <input type="radio" name="q8" value="3" checked> 3 <input type="radio" name="q8" value="4"> 4 <input type="radio" name="q8" value="5"> 5</div>
        </div>
        <div class="form-inline" style="justify-content:space-between; margin-bottom:10px;">
          <label style="font-size:0.85rem;">9. Satisfaction globale</label>
          <div style="font-size:0.85rem;"><input type="radio" name="q9" value="1"> 1 <input type="radio" name="q9" value="2"> 2 <input type="radio" name="q9" value="3" checked> 3 <input type="radio" name="q9" value="4"> 4 <input type="radio" name="q9" value="5"> 5</div>
        </div>
        <div class="modal-field">
          <label style="font-size:0.85rem;">Commentaire général</label>
          <textarea id="js-sat-commentaire" class="input" style="padding:4px; font-size:0.85rem;" rows="1"></textarea>
        </div>
        <div class="modal-field">
          <label style="font-size:0.85rem;">Recommandations</label>
          <textarea id="js-sat-recommandations" class="input" style="padding:4px; font-size:0.85rem;" rows="1"></textarea>
        </div>
      </div>
    </div>
    
    <div style="border-top: 1px solid var(--border); padding-top: 8px;">
        <label class="modal-field" style="flex-direction:row; align-items:center;">
          <input type="checkbox" id="js-sat-modal-rappel" />
          A rappeler
        </label>
        <label class="modal-field" style="flex-direction:row; align-items:center;">
          <span style="width:60px;">Quand :</span>
          <input type="datetime-local" id="js-sat-modal-rappel-at" disabled placeholder="mm/dd/yyyy --:-- --">
        </label>
        <label class="modal-field" style="flex-direction:row; align-items:center;">
          <input type="checkbox" id="js-sat-modal-deja-forme" />
          Déjà formé
        </label>
    </div>

    <div class="modal-actions">
      <button type="button" class="btn btn-ghost btn-sm" id="js-sat-hide">Masquer (garder l'appel en cours)</button>
      <button type="button" class="btn btn-danger btn-sm" id="js-sat-terminer">Terminer l'appel et Sauvegarder</button>
    </div>
  </div>
</div>"""
)  # noqa: E501

# 2. Add event listeners
chunk2_target = """    transcriptionModal?.addEventListener("click", (event) => {
      if (event.target === transcriptionModal) transcriptionModal.hidden = true;
    });"""
chunk2_replacement = (
    chunk2_target
    + """

    const satModal = document.getElementById("js-satisfaction-modal");
    const satModalRappel = document.getElementById("js-sat-modal-rappel");
    const satModalRappelAt = document.getElementById("js-sat-modal-rappel-at");
    let currentSatFormData = null;

    satModalRappel?.addEventListener("change", () => {
      if (satModalRappelAt) {
        satModalRappelAt.disabled = !satModalRappel.checked;
        if (!satModalRappel.checked) satModalRappelAt.value = "";
      }
    });

    document.getElementById("js-sat-hide")?.addEventListener("click", () => {
      if (satModal) satModal.hidden = true;
    });

    document.getElementById("js-sat-terminer")?.addEventListener("click", async () => {
        const rowId = satModal.dataset.rowId;
        const row = document.querySelector(`tr[data-id="${rowId}"]`);
        if (!row) return;

        const shouldRappeler = satModalRappel?.checked;
        const rappelAt = satModalRappelAt?.value;
        const dejaForme = document.getElementById("js-sat-modal-deja-forme")?.checked;
        
        if (shouldRappeler && !rappelAt) {
            alert("Merci de préciser la date et l'heure du rappel.");
            return;
        }

        currentSatFormData = new FormData();
        for (let i = 1; i <= 9; i++) {
            const checked = document.querySelector(`input[name="q${i}"]:checked`);
            if (checked) currentSatFormData.append(`q${i}`, checked.value);
        }
        currentSatFormData.append("commentaire", document.getElementById("js-sat-commentaire").value);
        currentSatFormData.append("recommandations", document.getElementById("js-sat-recommandations").value);

        satModal.hidden = true;

        try {
            const state = getRecordState(row);
            if (state?.recorder && state.recorder.state !== "inactive") {
                state.recorder.stop();
                state.stream?.getTracks().forEach(t => t.stop());
            }
            const data = await sendAction(row, shouldRappeler ? "rappeler" : "terminer", {
                rappel_at: rappelAt,
                deja_forme: dejaForme,
            });
            updateRow(row, data);
        } catch (err) { alert("Action impossible."); }
    });"""
)  # noqa: E501

# 3. Update startRecording
chunk3_target = """    async function startRecording(row) {
      const id = row.dataset.id;
      let stream;"""
chunk3_replacement = """    async function startRecording(row) {
      const id = row.dataset.id;
      
      const satModal = document.getElementById("js-satisfaction-modal");
      if (satModal) {
          document.querySelectorAll("#js-sat-questions input[type=radio][value='3']").forEach(r => r.checked = true);
          document.getElementById("js-sat-commentaire").value = "";
          document.getElementById("js-sat-recommandations").value = "";
          const smr = document.getElementById("js-sat-modal-rappel");
          if (smr) smr.checked = false;
          const smrat = document.getElementById("js-sat-modal-rappel-at");
          if (smrat) {
              smrat.value = "";
              smrat.disabled = true;
          }
          const satDejaForme = document.getElementById("js-sat-modal-deja-forme");
          if (satDejaForme) satDejaForme.checked = false;
          
          const satNom = document.getElementById("js-sat-modal-nom");
          if (satNom) satNom.textContent = row.dataset.name || "-";
          satModal.dataset.rowId = id;
          satModal.hidden = false;
      }
      
      let stream;"""  # noqa: E501

# 4. Update uploadAudio
chunk4_target = """    async function uploadAudio(row, blob) {
      const id = row.dataset.id;
      const blobType = (blob && blob.type) ? blob.type.toLowerCase() : "";
      const ext = blobType.includes("webm") ? "webm" : "mp3";
      const form = new FormData();
      form.append("audio", blob, `appel-${id}.${ext}`);
      try {"""
chunk4_replacement = """    async function uploadAudio(row, blob) {
      const id = row.dataset.id;
      const blobType = (blob && blob.type) ? blob.type.toLowerCase() : "";
      const ext = blobType.includes("webm") ? "webm" : "mp3";
      const form = new FormData();
      form.append("audio", blob, `appel-${id}.${ext}`);
      
      if (typeof currentSatFormData !== 'undefined' && currentSatFormData) {
          for (let pair of currentSatFormData.entries()) {
              form.append(pair[0], pair[1]);
          }
          currentSatFormData = null;
      }
      
      try {"""

if chunk1_target not in content:
    print("Chunk 1 not found")
if chunk2_target not in content:
    print("Chunk 2 not found")
if chunk3_target not in content:
    print("Chunk 3 not found")
if chunk4_target not in content:
    print("Chunk 4 not found")

content = content.replace(chunk1_target, chunk1_replacement)
content = content.replace(chunk2_target, chunk2_replacement)
content = content.replace(chunk3_target, chunk3_replacement)
content = content.replace(chunk4_target, chunk4_replacement)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched correctly.")
