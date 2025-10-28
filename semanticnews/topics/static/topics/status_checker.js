document.addEventListener('DOMContentLoaded', () => {
  const container = document.querySelector('[data-topic-uuid]');
  if (!container) return;
  const topicUuid = container.getAttribute('data-topic-uuid');

  const KEYS_TO_CHECK = ['recap', 'relation', 'image'];

  const mapping = {
    recap: 'recapButton',
    relation: 'relationButton',
    image: 'imageButton',
    data: 'dataButton',
  };

  const updateButtonDataset = (buttonId, info) => {
    if (!buttonId) return;
    const btn = document.getElementById(buttonId);
    if (!btn) return;
    const status = info && typeof info.status === 'string' ? info.status : 'finished';
    btn.dataset.status = status;
    const message = info && typeof info.error_message === 'string' ? info.error_message.trim() : '';
    if (message) {
      btn.dataset.error = message;
    } else if (btn.dataset.error) {
      delete btn.dataset.error;
    }
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

  // Fallback applier for text-based keys (e.g., recap)
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
  const applyRelationFallback = (entities) => {
    const container = document.getElementById('topicRelationContainer');
    const listEl = document.getElementById('topicRelatedEntities');
    if (container) container.style.display = '';
    if (listEl) {
      const event = new CustomEvent('topics:relations:fallback', {
        detail: { entities: entities || [] },
      });
      listEl.dispatchEvent(event);
    }
    const textarea = document.getElementById('relationText');
    if (textarea) {
      try {
        const payload = Array.isArray(entities) ? entities : [];
        textarea.value = JSON.stringify(payload, null, 2);
      } catch (err) {
        // ignore invalid data
      }
      const form = document.getElementById('relationForm');
      const submitBtn = form ? form.querySelector('button[type="submit"]') : null;
      if (submitBtn) submitBtn.disabled = true;
    }
  };

  // Pull latest list for a given key and apply via hook or fallback
  const updateFromServer = async (key) => {
    const listUrl =
      key === 'recap'      ? `/api/topics/recap/${topicUuid}/list` :
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

      const payload = await res.json();
      let anyStillInProgress = false;

      const now = payload.current ? new Date(payload.current) : new Date();

      for (const key of KEYS_TO_CHECK) {
        const info = payload[key];
        const buttonId = mapping[key];
        if (buttonId) {
          updateButtonDataset(buttonId, info || null);
        }
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

      const dataInfo = payload.data;
      const dataButtonId = mapping.data;
      if (dataButtonId && dataInfo) {
        const entries = Object.values(dataInfo).filter(Boolean);
        if (entries.length) {
          let hasFreshInProgress = false;
          let hasError = false;
          let hasFinished = false;

          for (const entry of entries) {
            const entryStatus = entry.status;
            if (!entryStatus) continue;

            if (entryStatus === 'in_progress') {
              const createdAt = entry.created_at ? new Date(entry.created_at) : null;
              const isFresh = !createdAt || (now - createdAt) <= INPROGRESS_TIMEOUT_MS;
              if (isFresh) {
                hasFreshInProgress = true;
              }
              continue;
            }

            if (entryStatus === 'error') {
              hasError = true;
            } else if (entryStatus === 'finished') {
              hasFinished = true;
            }
          }

          let nextState = 'finished';
          let datasetInfo = { status: 'finished' };

          if (hasFreshInProgress) {
            seenInProgress.data = true;
            nextState = 'in_progress';
            const inProgressEntry = entries.find((entry) => entry.status === 'in_progress');
            datasetInfo = inProgressEntry ? { ...inProgressEntry, status: 'in_progress' } : { status: 'in_progress' };
            anyStillInProgress = true;
          } else if (hasError) {
            nextState = 'error';
            const errorEntry = entries.find((entry) => entry.status === 'error');
            datasetInfo = errorEntry ? { ...errorEntry, status: 'error' } : { status: 'error' };
          } else if (hasFinished) {
            nextState = 'success';
            const finishedEntry = entries.find((entry) => entry.status === 'finished');
            if (finishedEntry) {
              datasetInfo = { ...finishedEntry, status: 'success' };
            } else {
              datasetInfo = { status: 'success' };
            }
          } else if (seenInProgress.data) {
            datasetInfo = { status: 'finished' };
          } else {
            datasetInfo = { status: 'finished' };
          }

          setController(dataButtonId, nextState);
          updateButtonDataset(dataButtonId, datasetInfo);
        } else {
          setController(dataButtonId, 'finished');
          updateButtonDataset(dataButtonId, { status: 'finished' });
        }
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
