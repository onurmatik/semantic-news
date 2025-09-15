document.addEventListener('DOMContentLoaded', () => {
  const controller = setupGenerationButton({
    buttonId: 'recapButton',
    spinnerId: 'recapSpinner',
    errorIconId: 'recapErrorIcon',
    successIconId: 'recapSuccessIcon',
  });

  const form = document.getElementById('recapForm');
  const suggestionBtn = document.getElementById('fetchRecapSuggestion');
  const recapTextarea = document.getElementById('recapText');
  const recapMDE = recapTextarea && window.EasyMDE ? new EasyMDE({ element: recapTextarea }) : null;
  // expose the MDE instance on the textarea so status checker can find it
  if (recapTextarea && recapMDE) recapTextarea._easyMDE = recapMDE;
  const getRecapValue = () => recapMDE ? recapMDE.value() : (recapTextarea ? recapTextarea.value : '');
  const recapCardContainer = document.getElementById('topicRecapContainer');
  const recapCardText = document.getElementById('topicRecapText');

  // Edit-only controls (exist only in EDIT mode template)
  const pagerEl = document.getElementById('recapPager');
  const prevBtn = document.getElementById('recapPrev');
  const nextBtn = document.getElementById('recapNext');
  const pagerLabel = document.getElementById('recapPagerLabel');
  const createdAtEl = document.getElementById('recapCreatedAt');
  const deleteBtn = document.getElementById('recapDeleteBtn');

  const confirmDeleteModalEl = document.getElementById('confirmDeleteRecapModal');
  const confirmDeleteBtn = document.getElementById('confirmDeleteRecapBtn');
  const deleteSpinner = document.getElementById('confirmDeleteSpinner');
  const confirmDeleteModal = confirmDeleteModalEl && window.bootstrap
    ? bootstrap.Modal.getOrCreateInstance(confirmDeleteModalEl)
    : null;

  const container = document.querySelector('[data-topic-uuid]');
  const topicUuid = container ? container.getAttribute('data-topic-uuid') : null;

   // External hook so status_checker can apply a newly finished recap and reset baseline like success flow
   window.__recapExternalApply = (text, createdAtIso) => {
     // Update card (same lite render you use)
     const card = document.getElementById('topicRecapContainer');
     const cardText = document.getElementById('topicRecapText');
     if (card && cardText) {
       card.style.display = '';
       const renderMarkdownLite = (md) => {
         if (!md) return '';
         let html = md.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
         html = html.split(/\n{2,}/).map(p => `<p class="mb-2">${p.replace(/\n/g, '<br>')}</p>`).join('');
         return html;
       };
       cardText.innerHTML = renderMarkdownLite(text || '');
     }

     // Update editor
     if (recapMDE) recapMDE.value(text || '');
     else if (recapTextarea) recapTextarea.value = text || '';

     // Reset baseline & disable Update button
     latestRecapBaseline = norm(getRecapValue());
     updateSubmitButtonState();

     // Update created_at label if present (edit page)
     const createdAtEl = document.getElementById('recapCreatedAt');
     if (createdAtEl && createdAtIso) {
       const d = new Date(createdAtIso);
       createdAtEl.textContent = d.toLocaleString(undefined, {
         year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit'
       });
     }
   };

  // ---- Helper: normalize text for equality checks
  const norm = (s) => (s || '')
    .replace(/\r\n/g, '\n')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  // ---- Keep a baseline = "current recap shown"
  let latestRecapBaseline = recapTextarea ? norm(getRecapValue()) : '';

  // ---- Update button enable/disable based on textarea vs baseline
  const submitBtn = form ? form.querySelector('button[type="submit"]') : null;
  const updateSubmitButtonState = () => {
    if (!submitBtn || !recapTextarea) return;
    submitBtn.disabled = norm(getRecapValue()) === latestRecapBaseline;
  };
  if (recapMDE) {
    recapMDE.codemirror.on('change', updateSubmitButtonState);
  } else {
    recapTextarea && recapTextarea.addEventListener('input', updateSubmitButtonState);
  }
  updateSubmitButtonState();

  // ---- Very light Markdown-to-HTML for bold + newlines
  const renderMarkdownLite = (md) => {
    if (!md) return '';
    let html = md.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html
      .split(/\n{2,}/)
      .map(p => `<p class="mb-2">${p.replace(/\n/g, '<br>')}</p>`)
      .join('');
    return html;
  };

  const showRecapCard = (text) => {
    if (!recapCardContainer || !recapCardText) return;
    recapCardContainer.style.display = '';
    recapCardText.innerHTML = renderMarkdownLite(text);
  };

  // ====== Pager/Delete state (only wired if edit controls exist) ======
  let recaps = [];         // [{id, recap, created_at}, ...] (finished only)
  let currentIndex = -1;   // 0-based
  const current = () => (currentIndex >= 0 ? recaps[currentIndex] : null);

  // date formatting for created_at
  const formatDateTime = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const applyIndex = (i) => {
    if (!recaps.length) {
      if (pagerEl) pagerEl.style.display = 'none';
      return;
    }
    currentIndex = Math.max(0, Math.min(i, recaps.length - 1));
    const item = recaps[currentIndex];

    // Fill textarea & card
    if (recapMDE) {
      recapMDE.value(item.recap || '');
    } else if (recapTextarea) {
      recapTextarea.value = item.recap || '';
    }
    showRecapCard(item.recap || '');

    // Baseline for Update button
    latestRecapBaseline = norm(getRecapValue());
    updateSubmitButtonState();

    // Pager UI + created_at
    if (pagerEl) pagerEl.style.display = '';
    if (pagerLabel) pagerLabel.textContent = `${currentIndex + 1}/${recaps.length}`;
    if (prevBtn) prevBtn.disabled = currentIndex <= 0;
    if (nextBtn) nextBtn.disabled = currentIndex >= recaps.length - 1;
    if (createdAtEl) createdAtEl.textContent = formatDateTime(item.created_at);
  };

  // define as no-op; will be replaced in edit mode
  let reloadRecapsAndJumpToLatest = async () => {};

  if (pagerEl) {
    reloadRecapsAndJumpToLatest = async () => {
      if (!topicUuid) return;
      try {
        const res = await fetch(`/api/topics/recap/${topicUuid}/list`);
        if (!res.ok) throw new Error('Failed to load recaps');
        const data = await res.json();
        recaps = data.items || [];
        if (!recaps.length) {
          if (pagerEl) pagerEl.style.display = 'none';
          return;
        }
        applyIndex(recaps.length - 1); // latest
      } catch (e) {
        console.error(e);
      }
    };

    // Expose a safe reload hook so status_checker can refresh list, counts, and baseline.
    window.__recapReloadAndJump = reloadRecapsAndJumpToLatest;

    prevBtn && prevBtn.addEventListener('click', () => applyIndex(currentIndex - 1));
    nextBtn && nextBtn.addEventListener('click', () => applyIndex(currentIndex + 1));

    deleteBtn && deleteBtn.addEventListener('click', () => {
      if (!current()) return;
      confirmDeleteModal && confirmDeleteModal.show();
    });

    confirmDeleteBtn && confirmDeleteBtn.addEventListener('click', async () => {
      const item = current();
      if (!item) return;

      // Loading state on confirm delete
      confirmDeleteBtn.disabled = true;
      deleteSpinner && deleteSpinner.classList.remove('d-none');

      try {
        const res = await fetch(`/api/topics/recap/${item.id}`, { method: 'DELETE' });
        if (!res.ok && res.status !== 204) throw new Error('Delete failed');
        window.location.reload(); // per requirement
      } catch (e) {
        console.error(e);
        confirmDeleteModal && confirmDeleteModal.hide();
      } finally {
        // In case we didn't reload due to error:
        confirmDeleteBtn.disabled = false;
        deleteSpinner && deleteSpinner.classList.add('d-none');
      }
    });

    // Initial load (only in edit mode)
    reloadRecapsAndJumpToLatest();
  }

  // ====== Suggest + Update flows ======
  const recapModalEl = document.getElementById('recapModal');
  const recapModal = recapModalEl && window.bootstrap
    ? bootstrap.Modal.getOrCreateInstance(recapModalEl)
    : null;

  if (recapModalEl && recapMDE) {
    recapModalEl.addEventListener('shown.bs.modal', () => {
      recapMDE.codemirror.refresh();
    });
  }

  const afterPersistedChange = async () => {
    // After AI suggestion or manual Update, ensure pager/card/textarea/baseline are correct
    await reloadRecapsAndJumpToLatest();
  };

  if (suggestionBtn && recapTextarea && form) {
    suggestionBtn.addEventListener('click', async () => {
      controller.showLoading();
      recapModal && recapModal.hide();
      suggestionBtn.disabled = true;

      try {
        const res = await fetch('/api/topics/recap/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid })
        });
        if (!res.ok) throw new Error('Request failed');
        await res.json();

        controller.showSuccess();
        await afterPersistedChange();
      } catch (err) {
        console.error(err);
        controller.showError();
      } finally {
        suggestionBtn.disabled = false;
      }
    });
  }

  if (form && recapTextarea) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      submitBtn && (submitBtn.disabled = true);
      controller.showLoading();
      recapModal && recapModal.hide();

      try {
        const res = await fetch('/api/topics/recap/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid, recap: getRecapValue() })
        });
        if (!res.ok) throw new Error('Request failed');
        await res.json();

        controller.reset();
        await afterPersistedChange();
      } catch (err) {
        console.error(err);
        controller.showError();
      } finally {
        // keep button disabled if no diff from baseline
        submitBtn && (submitBtn.disabled = norm(getRecapValue()) === latestRecapBaseline);
      }
    });
  }
});
