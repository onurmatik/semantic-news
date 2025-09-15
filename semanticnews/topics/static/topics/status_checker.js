document.addEventListener('DOMContentLoaded', () => {
  const container = document.querySelector('[data-topic-uuid]');
  if (!container) return;
  const topicUuid = container.getAttribute('data-topic-uuid');

  const KEYS_TO_CHECK = ['recap'];

  const mapping = {
    recap: 'recapButton',
  };

  const INPROGRESS_TIMEOUT_MS = 5 * 60 * 1000;
  let intervalId = null;

  const seenInProgress = Object.create(null);

  const neutralizeStaleInitial = () => {
    for (const key of KEYS_TO_CHECK) {
      const buttonId = mapping[key];
      if (!buttonId) continue;
      const btn = document.getElementById(buttonId);
      if (btn && btn.dataset.status === 'in_progress') {
        const ctrl = window.generationControllers && window.generationControllers[buttonId];
        if (ctrl && ctrl.setState) ctrl.setState({status: 'finished'}); // neutral
      }
    }
  };

  const renderMarkdownLite = (md) => {
    if (!md) return '';
    let html = md.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.split(/\n{2,}/).map(p => `<p class="mb-2">${p.replace(/\n/g, '<br>')}</p>`).join('');
    return html;
  };

  const applyRecapFallback = (text, createdAtIso) => {
    const card = document.getElementById('topicRecapContainer');
    const cardText = document.getElementById('topicRecapText');
    if (card && cardText) {
      card.style.display = '';
      cardText.innerHTML = renderMarkdownLite(text || '');
    }
    const textarea = document.getElementById('recapText');
    if (textarea) {
      const mde = textarea._easyMDE;
      if (mde && mde.value) mde.value(text || '');
      else textarea.value = text || '';
      const form = document.getElementById('recapForm');
      const submitBtn = form ? form.querySelector('button[type="submit"]') : null;
      if (submitBtn) submitBtn.disabled = true;
      const createdAtEl = document.getElementById('recapCreatedAt');
      if (createdAtEl && createdAtIso) {
        const d = new Date(createdAtIso);
        createdAtEl.textContent = d.toLocaleString(undefined, {
          year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit'
        });
      }
    }
  };

  const updateRecapFromServer = async () => {
    try {
      const res = await fetch(`/api/topics/recap/${topicUuid}/list`);
      if (!res.ok) return;
      const data = await res.json();
      const items = data.items || [];
      if (!items.length) return;
      const latest = items[items.length - 1];
      if (typeof window.__recapExternalApply === 'function') {
        window.__recapExternalApply(latest.recap, latest.created_at);
      } else {
        applyRecapFallback(latest.recap, latest.created_at);
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
          seenInProgress[key] = true; // mark that we saw it running in this session
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
          if (seenInProgress[key]) {
            setController(buttonId, 'success');
          } else {
            setController(buttonId, 'finished'); // neutral (no icon/color)
          }

          if (key === 'recap') {
            // Always refresh content AND counts/pager.
            if (typeof window.__recapReloadAndJump === 'function') {
              await window.__recapReloadAndJump();     // updates list, counts, baseline
            } else {
              await updateRecapFromServer();           // fallback: updates content only
            }
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
