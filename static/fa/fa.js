/* FA: microphone before call start, durable audio retry, explicit final upload. */
(() => {
  'use strict';
  const app = document.querySelector('[data-fa-app]');
  if (!app) return;
  const dialog = document.getElementById('fa-dialog');
  const content = document.getElementById('fa-modal-content');
  let root, form, section = 0, session = null, attempt = null, dirty = false, autosave;
  let database;
  const csrf = () => document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  const feedback = (message, error = false) => {
    const target = document.getElementById('fa-feedback') || document.getElementById('fa-global-feedback');
    target.hidden = false;
    target.textContent = message;
    target.classList.toggle('is-error', error);
    target.classList.toggle('is-success', !error);
  };
  async function post(url, data) {
    const response = await fetch(url, {method: 'POST', body: data, credentials: 'same-origin',
      headers: {'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
      signal: AbortSignal.timeout(90000)});
    const result = await response.json().catch(() => ({error: 'Session expirée ou réponse du serveur indisponible.'}));
    if (!response.ok || result.ok === false) {
      const error = new Error(result.error || 'La sauvegarde a échoué. Réessayez.');
      error.fields = result.errors; error.status = response.status;
      throw error;
    }
    return result;
  }
  function db() {
    if (!database) database = new Promise((resolve, reject) => {
      if (!window.indexedDB) return reject(new Error('Le stockage local audio est indisponible. Utilisez un navigateur compatible.'));
      const request = indexedDB.open('fa-recordings-v1', 1);
      request.onupgradeneeded = () => request.result.createObjectStore('pending', {keyPath: 'key'});
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error('Impossible de protéger l’audio localement. Vérifiez l’espace disque.'));
    });
    return database;
  }
  async function stored(action, value) {
    const database = await db();
    return new Promise((resolve, reject) => {
      const transaction = database.transaction('pending', action === 'getAll' ? 'readonly' : 'readwrite');
      const request = transaction.objectStore('pending')[action](value);
      transaction.oncomplete = () => resolve(request.result);
      transaction.onerror = () => reject(transaction.error || new Error('Sauvegarde locale audio impossible.'));
      transaction.onabort = () => reject(transaction.error || new Error('Sauvegarde locale audio interrompue.'));
    });
  }
  function audioData(item) {
    const data = new FormData();
    data.set('audio', item.blob, `fa-${item.sequence}.${item.blob.type.includes('mp4') ? 'm4a' : 'webm'}`);
    data.set('sequence', item.sequence); data.set('full', '1');
    if (item.final) data.set('final', '1');
    if (item.token) { data.set('client_token', item.token); data.set('recording_ready', 'true'); if (item.phone) data.set('q4_phone', item.phone); }
    return data;
  }
  async function uploadItem(item) {
    const result = await post(item.url, audioData(item));
    await stored('delete', item.key);
    return result;
  }
  function attemptFrom(data) {
    return {id: data.attempt_id, upload: data.upload_url, save: data.save_url,
      finish: data.finish_url, state: data.state_url};
  }
  async function recoverPending(onlyAttempt = null) {
    const items = (await stored('getAll')).filter(item => item.user === app.dataset.userId &&
      (!onlyAttempt || String(item.attemptId) === String(onlyAttempt)));
    items.sort((a, b) => a.created - b.created || a.sequence - b.sequence);
    for (const item of items) {
      if (onlyAttempt && session) session.sequence = Math.max(session.sequence, item.sequence + 1);
      try { await uploadItem(item); }
      catch (error) { feedback('Un audio est conservé sur cet appareil. Reconnectez-vous puis réouvrez ce formulaire pour réessayer la sauvegarde.', true); throw error; }
    }
    return items.length;
  }
  function showSection(next) {
    const sections = [...root.querySelectorAll('.fa-question-section')];
    if (!sections.length) return;
    section = Math.max(0, Math.min(next, sections.length - 1));
    sections.forEach((item, index) => item.hidden = index !== section);
    root.querySelectorAll('[data-fa-section]').forEach((item, index) => {
      item.setAttribute('aria-selected', String(index === section)); item.tabIndex = index === section ? 0 : -1;
    });
    document.getElementById('fa-prev-section').disabled = section === 0;
    document.getElementById('fa-next-section').disabled = section === sections.length - 1;
    document.getElementById('fa-section-position').textContent = `${section + 1} / ${sections.length}`;
  }
  function conditions() {
    const data = new FormData(form);
    const wrappers = new Map([...root.querySelectorAll('[data-fa-field]')].map(item => [item.dataset.faField, item]));
    const applicable = (name, visited = new Set()) => {
      if (visited.has(name)) return false;
      visited.add(name);
      const source = wrappers.get(name)?.querySelector('[data-condition-field]');
      return !source || (data.getAll(source.dataset.conditionField).includes(source.dataset.conditionValue) &&
        applicable(source.dataset.conditionField, visited));
    };
    root.querySelectorAll('[data-condition-field]').forEach(input => {
      const wrapper = input.closest('[data-fa-field]');
      if (!wrapper) return;
      wrapper.hidden = !applicable(wrapper.dataset.faField);
    });
    document.getElementById('fa-callback-field').hidden = document.getElementById('fa-outcome').value !== 'a_rappeler';
  }
  function fieldErrors(error) {
    root.querySelectorAll('[data-error-for]').forEach(item => item.textContent = '');
    root.querySelectorAll('[aria-invalid]').forEach(item => item.removeAttribute('aria-invalid'));
    const fields = error.fields || {};
    for (const [name, messages] of Object.entries(fields)) {
      const target = [...root.querySelectorAll('[data-error-for]')].find(item => item.dataset.errorFor === name);
      if (target) target.textContent = (Array.isArray(messages) ? messages : [messages])
        .map(message => typeof message === 'string' ? message : message.message).join(' ');
      form.querySelectorAll(`[name="${CSS.escape(name)}"]`).forEach(item => item.setAttribute('aria-invalid', 'true'));
    }
    const first = root.querySelector('[aria-invalid]');
    if (first) {
      const panels = [...root.querySelectorAll('.fa-question-section')];
      const panel = first.closest('.fa-question-section');
      if (panel) showSection(panels.indexOf(panel));
      first.focus();
    }
    feedback(error.message, true);
  }
  async function saveDraft(silent = false) {
    if (!attempt?.save || !dirty) return;
    const version = form.dataset.version;
    try {
      await post(attempt.save, new FormData(form));
      if (version === form.dataset.version) dirty = false;
      document.getElementById('fa-save-state').textContent = `Brouillon sauvegardé à ${new Date().toLocaleTimeString('fr-FR')}`;
      if (!silent) feedback('Brouillon sauvegardé.');
    } catch (error) { fieldErrors(error); if (!silent) throw error; }
  }
  function recordingUI(active) {
    document.getElementById('fa-recording-dot').classList.toggle('is-recording', active);
    document.getElementById('fa-start').hidden = active;
    document.getElementById('fa-pause').hidden = !active;
    document.getElementById('fa-audio-settings').hidden = active;
    const dial = document.getElementById('fa-dial-controls');
    dial.hidden = !active;
    dial.replaceChildren();
    if (active) String(new FormData(form).get('q4_phone') || '').split(/[/;,]+/).forEach(phone => {
      const number = phone.replace(/[^\d+]/g, '');
      if (!number) return;
      const link = document.createElement('a'); link.className = 'fa-btn fa-secondary';
      link.href = `tel:${number}`; link.textContent = `Composer ${number}`; dial.append(link);
    });
    document.getElementById('fa-finish').disabled = !attempt;
  }
  async function audioStream() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('L’enregistrement exige HTTPS et un navigateur compatible (Chrome ou Edge, par exemple).');
    const streams = [];
    let context;
    try {
      // Display sharing must be requested from the initiating user gesture.
      if (document.getElementById('fa-share-audio').checked) {
        if (!navigator.mediaDevices.getDisplayMedia) throw new Error('Ce navigateur ne permet pas de partager l’audio de la fenêtre d’appel.');
        const shared = await navigator.mediaDevices.getDisplayMedia({video: true, audio: true, systemAudio: 'include'});
        streams.push(shared);
        if (!shared.getAudioTracks().length) throw new Error('Aucun audio partagé. Choisissez l’onglet d’appel et cochez Partager l’audio.');
      }
      const mic = await navigator.mediaDevices.getUserMedia({audio: true});
      streams.push(mic);
      let stream = mic;
      if (streams.length > 1) {
        context = new AudioContext(); await context.resume();
        const output = context.createMediaStreamDestination();
        streams.forEach(input => context.createMediaStreamSource(new MediaStream(input.getAudioTracks())).connect(output));
        stream = output.stream;
      }
      return {stream, streams, context};
    } catch (error) { streams.forEach(item => item.getTracks().forEach(track => track.stop())); if (context) await context.close(); throw error; }
  }
  async function queueSnapshot(current, blob, final = false) {
    const sequence = current.sequence++;
    const item = {key: `${app.dataset.userId}:${attempt.id}:${sequence}`, user: app.dataset.userId,
      attemptId: attempt.id, sequence, blob, final, url: attempt.upload, created: Date.now()};
    // Commit audio locally before any network request; remove it only after server ACK.
    const persistence = stored('put', item);
    current.queue = current.queue.catch(() => {}).then(async () => {await persistence; return uploadItem(item);});
    current.queue.catch(error => feedback(`Audio conservé sur cet appareil ; sauvegarde réseau à réessayer. ${error.message}`, true));
    return current.queue;
  }
  async function release(current) {
    clearInterval(current.timer); clearInterval(current.snapshots);
    current.streams.forEach(item => item.getTracks().forEach(track => track.stop()));
    if (current.context) await current.context.close();
  }
  async function start() {
    const button = document.getElementById('fa-start');
    button.disabled = true;
    try {
      if (session?.recorder.state === 'recording' && attempt) return;
      // Request access from this click before awaiting storage/network.
      const resources = await audioStream();
      try { await db(); } catch (error) { await release({...resources}); throw error; }
      const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find(type => MediaRecorder.isTypeSupported(type));
      const recorder = new MediaRecorder(resources.stream, {...(mimeType ? {mimeType} : {}), audioBitsPerSecond: 32000});
      const current = {...resources, recorder, chunks: [], sequence: Number(root.dataset.nextSequence || 1),
        queue: Promise.resolve(), started: Date.now(), timer: null, snapshots: null, stopping: false};
      session = current;
      const first = new Promise((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('Aucun son n’a pu être capturé. Vérifiez le microphone.')), 12000);
        recorder.addEventListener('dataavailable', event => {clearTimeout(timeout); event.data.size ? resolve(event.data) : reject(new Error('Enregistrement vide. Vérifiez le microphone.'));}, {once: true});
      });
      recorder.ondataavailable = event => { if (event.data.size) current.chunks.push(event.data); };
      recorder.onerror = () => { feedback('L’enregistrement a été interrompu. Sauvegardez l’audio puis reprenez l’enregistrement avant de poursuivre l’entretien.', true); if (recorder.state !== 'inactive') recorder.stop(); };
      recorder.start();
      setTimeout(() => {if (recorder.state === 'recording') recorder.requestData();}, 1000);
      const initialBlob = await first;
      if (!attempt) {
        const token = crypto.randomUUID();
        const item = {key: `${app.dataset.userId}:start:${token}`, user: app.dataset.userId, sequence: 0,
          blob: initialBlob, url: root.dataset.startUrl, token, phone: new FormData(form).get('q4_phone'), created: Date.now()};
        await stored('put', item);
        let response;
        try {response = await uploadItem(item);} catch (error) {
          // One idempotent retry covers a committed start whose response was lost.
          if (error.status && error.status < 500) {await stored('delete', item.key); throw error;}
          response = await uploadItem(item);
        }
        attempt = attemptFrom(response);
        current.sequence = Math.max(current.sequence, response.next_sequence || 1);
      } else {
        await recoverPending(attempt.id);
        const data = new FormData(); data.set('action', 'resume');
        if (attempt.state) {
          const resumed = await post(attempt.state, data);
          current.sequence = Math.max(current.sequence, resumed.next_sequence || 1);
        }
        await queueSnapshot(current, initialBlob);
      }
      recorder.ondataavailable = event => {
        if (!event.data.size) return;
        current.chunks.push(event.data);
        if (!current.stopping) queueSnapshot(current, new Blob(current.chunks, {type: recorder.mimeType})).catch(() => {});
      };
      current.snapshots = setInterval(() => {if (recorder.state === 'recording') recorder.requestData();}, 15000);
      current.timer = setInterval(() => {
        const seconds = Math.floor((Date.now() - current.started) / 1000);
        document.getElementById('fa-timer').textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
      }, 1000);
      current.streams.forEach(stream => stream.getAudioTracks().forEach(track => track.addEventListener('ended', () => {
        feedback('Une source audio a été déconnectée. Terminez et sauvegardez cet enregistrement avant de poursuivre.', true);
        if (recorder.state !== 'inactive') recorder.stop();
      })));
      recordingUI(true);
      document.getElementById('fa-recording-label').textContent = 'Enregistrement en cours · sauvegarde automatique';
      dirty = true; await saveDraft(true);
      feedback('L’appel est démarré et son premier audio est sauvegardé.');
    } catch (error) {
      if (session) {
        session.stopping = true;
        if (session.recorder.state !== 'inactive') session.recorder.stop();
        await release(session); session = null;
      }
      feedback(error.name === 'NotAllowedError' ? 'Autorisez le microphone pour démarrer l’appel avec son enregistrement obligatoire.' : error.message, true);
    } finally {button.disabled = false;}
  }
  async function pause() {
    if (!session || session.recorder.state === 'inactive') return;
    const button = document.getElementById('fa-pause'); button.disabled = true;
    try {
      const paused = session.recorder.state === 'paused';
      const data = new FormData(); data.set('action', paused ? 'resume' : 'pause');
      await post(attempt.state, data);
      if (paused) session.recorder.resume(); else session.recorder.pause();
      button.textContent = paused ? 'Mettre en pause' : 'Reprendre';
      document.getElementById('fa-dial-controls').hidden = !paused;
      document.getElementById('fa-recording-dot').classList.toggle('is-recording', paused);
      document.getElementById('fa-recording-label').textContent = paused ? 'Enregistrement en cours' : 'Appel et enregistrement en pause';
      await saveDraft(true);
    } catch (error) {feedback(error.message, true);} finally {button.disabled = false;}
  }
  async function finish() {
    const button = document.getElementById('fa-finish'); button.disabled = true;
    try {
      if (!attempt) throw new Error('Démarrez l’appel et son enregistrement avant de le terminer.');
      if (!document.getElementById('fa-outcome').value) throw new Error('Choisissez le résultat de l’appel avant de terminer.');
      if (document.getElementById('fa-outcome').value === 'a_rappeler' && !document.getElementById('fa-callback').value) throw new Error('Choisissez une date et une heure de rappel.');
      if (session) {
        const current = session;
        current.stopping = true;
        if (current.recorder.state !== 'inactive') await new Promise(resolve => {current.recorder.addEventListener('stop', resolve, {once: true}); current.recorder.stop();});
        await current.queue.catch(() => {});
        // Recover older snapshots before the final so final remains the latest sequence.
        await recoverPending(attempt.id);
        await queueSnapshot(current, new Blob(current.chunks, {type: current.recorder.mimeType}), true);
        await release(current); session = null;
        recordingUI(false);
      } else await recoverPending(attempt.id);
      await post(attempt.finish, new FormData(form));
      dirty = false; attempt = null;
      feedback('Appel terminé. Le questionnaire et l’audio sont sauvegardés.');
      window.location.reload();
    } catch (error) {fieldErrors(error);} finally {button.disabled = !attempt;}
  }
  async function open(url, trigger) {
    if (session) return feedback('Terminez et sauvegardez l’appel en cours avant d’ouvrir une autre entreprise.', true);
    content.innerHTML = '<div class="fa-loading" role="status">Ouverture du questionnaire…</div>';
    dialog.showModal();
    try {
      const response = await fetch(url, {credentials: 'same-origin', headers: {'X-Requested-With': 'XMLHttpRequest'}, cache: 'no-store'});
      if (!response.ok || response.redirected) throw new Error('Impossible d’ouvrir le formulaire. Vérifiez votre connexion et votre session.');
      content.innerHTML = await response.text();
      root = content.querySelector('[data-fa-detail-root]');
      if (!root) throw new Error('Le formulaire est indisponible.');
      form = document.getElementById('fa-questionnaire');
      attempt = root.dataset.attemptId ? {id: root.dataset.attemptId, upload: root.dataset.uploadUrl,
        save: root.dataset.saveUrl, finish: root.dataset.finishUrl, state: root.dataset.stateUrl} : null;
      dirty = false; section = 0;
      showSection(0); conditions();
      root.querySelectorAll('[data-required-final="1"]').forEach(input => {
        const wrapper = input.closest('[data-fa-field]');
        const label = wrapper?.querySelector('label');
        if (label && !label.dataset.requiredMarked) {label.append(' *'); label.dataset.requiredMarked = 'true';}
      });
      root.querySelectorAll('[data-fa-section]').forEach(item => item.addEventListener('click', () => showSection(Number(item.dataset.faSection))));
      root.querySelector('[role=tablist]').addEventListener('keydown', event => {
        if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault(); const count = root.querySelectorAll('[data-fa-section]').length;
        showSection(event.key === 'Home' ? 0 : event.key === 'End' ? count - 1 : (section + (event.key === 'ArrowRight' ? 1 : -1) + count) % count);
        root.querySelector(`[data-fa-section="${section}"]`).focus();
      });
      document.getElementById('fa-prev-section').onclick = () => showSection(section - 1);
      document.getElementById('fa-next-section').onclick = () => showSection(section + 1);
      document.getElementById('fa-start').onclick = start;
      document.getElementById('fa-pause').onclick = pause;
      document.getElementById('fa-save').onclick = () => saveDraft().catch(() => {});
      document.getElementById('fa-finish').onclick = finish;
      document.getElementById('fa-discard').onclick = () => {dirty = false; close();};
      root.querySelector('[data-fa-close]').onclick = close;
      form.addEventListener('input', () => {dirty = true; form.dataset.version = String(Date.now()); conditions();});
      form.addEventListener('change', conditions);
      form.addEventListener('submit', event => event.preventDefault());
      clearInterval(autosave); autosave = setInterval(() => {if (dirty && attempt) saveDraft(true);}, 20000);
      if (root.dataset.canEdit === 'false') {
        root.querySelectorAll('input,select,textarea,button:not([data-fa-close])').forEach(item => item.disabled = true);
        feedback('Un autre opérateur gère cet appel. Le formulaire est en lecture seule.');
      }
      if (attempt) recoverPending(attempt.id).catch(() => {});
      root.querySelector('[data-fa-close]').focus();
      dialog.addEventListener('close', () => trigger?.focus(), {once: true});
    } catch (error) {content.innerHTML = '<div class="fa-loading"></div>'; content.firstChild.textContent = error.message; const button = document.createElement('button'); button.className = 'fa-btn'; button.textContent = 'Fermer'; button.onclick = () => dialog.close(); content.firstChild.appendChild(button);}
  }
  async function close() {
    if (session) return feedback('Terminez et sauvegardez l’appel pour conserver son audio avant de fermer le formulaire.', true);
    if (dirty && attempt) {try {await saveDraft();} catch {return;}}
    else if (dirty) {
      document.getElementById('fa-discard').hidden = false;
      return feedback('Ces réponses ne sont pas sauvegardées. Démarrez l’appel pour les conserver, ou abandonnez les réponses pour fermer.', true);
    }
    clearInterval(autosave); dialog.close();
  }
  app.addEventListener('click', event => {const trigger = event.target.closest('[data-fa-detail]'); if (trigger) open(trigger.dataset.faDetail, trigger);});
  dialog.addEventListener('cancel', event => {event.preventDefault(); close();});
  window.addEventListener('beforeunload', event => {if (session || dirty) {event.preventDefault(); event.returnValue = '';}});
  window.addEventListener('online', () => recoverPending().then(count => {if (count) feedback('Les audios en attente ont été sauvegardés.');}).catch(() => {}));
  recoverPending().then(count => {if (count) feedback('Les audios en attente ont été sauvegardés. Réouvrez l’entreprise pour finaliser l’appel.');}).catch(() => {});
})();
