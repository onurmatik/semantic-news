document.addEventListener('DOMContentLoaded', () => {
  const container = document.querySelector('[data-topic-uuid]');
  if (!container) return;
  const topicUuid = container.getAttribute('data-topic-uuid');

  const KEYS_TO_CHECK = ['recap', 'narrative', 'relation', 'image'];

  const mapping = {
    recap: 'recapButton',
    narrative: 'narrativeButton',
    relation: 'relationButton',
    image: 'imageButton',
  };

  const INPROGRESS_TIMEOUT_MS = 5 * 60 * 1000;
  let intervalId = null;

  const seenInProgress = Object.create(null);

  // --- prevent spinner flash on initial paint for stale "in_progress"
  const neutralizeStaleInitial = () => {
    for (const key of KEYS_TO_CHECK) {
      const buttonId = mapping[key];
      if (!buttonId) continue;
      const btn = document.getElementById(buttonId);
      if (btn && btn.dataset.status === 'in_progress') {
        const ctrl = window.generationControllers && window.generationControllers[buttonId];
        if (ctrl && ctrl.setState) ctrl.setState({ status: 'finished' }); // neutral
      }
    }
  };

  const renderMarkdownLite = (md) => {
    if (!md) return '';
    let html = md.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.split(/\n{2,}/).map(p => `<p class="mb-2">${p.replace(/\n/g, '<br>')}</p>`).join('');
    return html;
  };

  // Fallback applier for text-based keys (recap, narrative)
  const applyTextFallback = (key, text, createdAtIso) => {
    const Cap = key.charAt(0).toUpperCase() + key.slice(1);
    const card = document.getElementById(`topic${Cap}Container`);
    const cardText = document.getElementById(`topic${Cap}Text`);
    if (card && cardText) {
      card.style.display = '';
      cardText.innerHTML = renderMarkdownLite(text || '');
    }
    const textarea = document.getElementById(`${key}Text`);
    if (textarea) {
      const mde = textarea._easyMDE;
      if (mde && mde.value) mde.value(text || '');
      else textarea.value = text || '';
      const form = document.getElementById(`${key}Form`);
      const submitBtn = form ? form.querySelector('button[type="submit"]') : null;
      if (submitBtn) submitBtn.disabled = true;
      const createdAtEl = document.getElementById(`${key}CreatedAt`);
      if (createdAtEl && createdAtIso) {
        const d = new Date(createdAtIso);
        createdAtEl.textContent = d.toLocaleString(undefined, {
          year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit'
        });
      }
    }
  };

  // Fallback applier for relation (graph)
  const applyRelationFallback = (relations, createdAtIso) => {
    const graph = document.getElementById('topicRelationGraph');
    const container = document.getElementById('topicRelationContainer');
    if (container) container.style.display = '';
    if (graph && window.renderRelationGraph) {
      window.renderRelationGraph(graph, relations || []);
    }
    const textarea = document.getElementById('relationText');
    if (textarea) {
      // keep textarea JSON in sync
      textarea.value = JSON.stringify(relations || [], null, 2);
      const form = document.getElementById('relationForm');
      const submitBtn = form ? form.querySelector('button[type="submit"]') : null;
      if (submitBtn) submitBtn.disabled = true;
      const createdAtEl = document.getElementById('relationCreatedAt');
      if (createdAtEl && createdAtIso) {
        const d = new Date(createdAtIso);
        createdAtEl.textContent = d.toLocaleString(undefined, {
          year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit'
        });
      }
    }
  };

  // Pull latest list for a given key and apply via hook or fallback
  const updateFromServer = async (key) => {
    const listUrl =
      key === 'recap'      ? `/api/topics/recap/${topicUuid}/list` :
      key === 'narrative'  ? `/api/topics/narrative/${topicUuid}/list` :
      key === 'relation'   ? `/api/topics/relation/${topicUuid}/list` :
                             `/api/topics/image/${topicUuid}/list`;

    try {
      const res = await fetch(listUrl);
      if (!res.ok) return;
      const data = await res.json();
      const items = data.items || [];
      if (!items.length) return;
      const latest = items[items.length - 1];

      const hookName = `__${key}ExternalApply`;
      if (typeof window[hookName] === 'function') {
        // For text keys, pass the text. For relation, pass the array.
        if (key === 'relation') {
          window[hookName](latest.relations, latest.created_at);
        } else {
          window[hookName](latest[key], latest.created_at);
        }
      } else {
        // Fallback paint
        if (key === 'relation') {
          applyRelationFallback(latest.relations, latest.created_at);
        } else {
          applyTextFallback(key, latest[key], latest.created_at);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const setController = (buttonId, status) => {
    const ctrl = window.generationControllers && window.generationControllers[buttonId];
    if (ctrl && ctrl.setState) ctrl.setState({ status });
  };

  const fetchStatus = async () => {
    try {
      const res = await fetch(`/api/topics/${topicUuid}/generation-status`);
      if (!res.ok) return;

      const data = await res.json();
      let anyStillInProgress = false;

      const now = data.current ? new Date(data.current) : new Date();

      for (const key of KEYS_TO_CHECK) {
        const info = data[key];
        const buttonId = mapping[key];
        if (!info || !buttonId) continue;

        const status = info.status; // "in_progress" | "finished" | "error"
        const createdAt = info.created_at ? new Date(info.created_at) : null;

        if (status === 'in_progress') {
          seenInProgress[key] = true;
          if (createdAt && (now - createdAt) > INPROGRESS_TIMEOUT_MS) {
            setController(buttonId, 'finished'); // neutralize too-old spinners
            // TODO change status to error in db
          } else {
            setController(buttonId, 'in_progress');
            anyStillInProgress = true;
          }
          continue;
        }

        if (status === 'finished') {
          if (seenInProgress[key]) setController(buttonId, 'success');
          else setController(buttonId, 'finished'); // neutral (no green if we didn't see it running)

          // Always refresh content AND counts/pager
          const reloadHook = window[`__${key}ReloadAndJump`];
          if (typeof reloadHook === 'function') {
            await reloadHook(); // updates list, counts, baseline, and card via renderItem
          } else {
            await updateFromServer(key); // fallback: apply latest only
          }
          continue;
        }

        if (status === 'error') {
          setController(buttonId, 'error');
          continue;
        }

        setController(buttonId, 'finished'); // neutral/default
      }

      if (!anyStillInProgress && intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    } catch (err) {
      console.error(err);
    }
  };

  neutralizeStaleInitial();
  fetchStatus();
  intervalId = setInterval(fetchStatus, 3000);
});
