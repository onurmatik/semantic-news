window.setupTopicHistory = function (options) {
  const {
    key,            // e.g. 'recap', 'narrative', 'relation'
    field,          // field name in item (e.g. 'recap', 'narrative', 'relations')
    cardSuffix = 'Text', // suffix for card content element (Text or Graph)
    listUrl,        // function(topicUuid) -> url
    createUrl,      // string url for POST create
    deleteUrl,      // function(id) -> url
    renderItem,     // function(item, cardContent)
    parseInput,     // function(text) -> data for create
    controller,     // generation button controller
    useMarkdown = false, // whether to enhance textarea with EasyMDE
  } = options;

  const form = document.getElementById(`${key}Form`);
  const suggestionBtn = document.getElementById(`fetch${capitalize(key)}Suggestion`);
  const textarea = document.getElementById(`${key}Text`);
  const easyMDE = useMarkdown && textarea && window.EasyMDE ? new EasyMDE({ element: textarea }) : null;
  // expose MDE handle so other scripts can access it (status checker / fallbacks)
  if (textarea && easyMDE) textarea._easyMDE = easyMDE;

  const getValue = () => easyMDE ? easyMDE.value() : (textarea ? textarea.value : '');
  const setValue = (v) => { if (easyMDE) easyMDE.value(v); else if (textarea) textarea.value = v; };
  const cardContainer = document.getElementById(`topic${capitalize(key)}Container`);
  const cardContent = document.getElementById(`topic${capitalize(key)}${cardSuffix}`);
  const modalEl = document.getElementById(`${key}Modal`);
  const modal = modalEl && window.bootstrap ? bootstrap.Modal.getOrCreateInstance(modalEl) : null;

  if (easyMDE && modalEl) {
    modalEl.addEventListener('shown.bs.modal', () => {
      easyMDE.codemirror.refresh();
    });
  }

  const pagerEl = document.getElementById(`${key}Pager`);
  const prevBtn = document.getElementById(`${key}Prev`);
  const nextBtn = document.getElementById(`${key}Next`);
  const pagerLabel = document.getElementById(`${key}PagerLabel`);
  const createdAtEl = document.getElementById(`${key}CreatedAt`);
  const deleteBtn = document.getElementById(`${key}DeleteBtn`);
  const showWhenMultipleEls = pagerEl ? Array.from(pagerEl.querySelectorAll('[data-show-when-multiple]')) : [];

  const confirmModalEl = document.getElementById(`confirmDelete${capitalize(key)}Modal`);
  const confirmBtn = document.getElementById(`confirmDelete${capitalize(key)}Btn`);
  const deleteSpinner = document.getElementById(`confirmDelete${capitalize(key)}Spinner`);
  const confirmModal = confirmModalEl && window.bootstrap ? bootstrap.Modal.getOrCreateInstance(confirmModalEl) : null;

  const container = document.querySelector('[data-topic-uuid]');
  const topicUuid = container ? container.getAttribute('data-topic-uuid') : null;
  const buildSuggestionPayload = typeof options.buildSuggestionPayload === 'function'
    ? () => options.buildSuggestionPayload({
      topicUuid,
      getValue,
      textarea,
      easyMDE,
    })
    : () => ({ topic_uuid: topicUuid });

  const norm = (s) => (s || '').replace(/\r\n/g, '\n').replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
  let baseline = textarea ? norm(getValue()) : '';

  // Submit button enable/disable based on diff from baseline
  const submitBtn = form ? form.querySelector('button[type="submit"]') : null;
  const updateSubmitButtonState = () => {
    if (!submitBtn || !textarea) return;
    submitBtn.disabled = norm(getValue()) === baseline;
  };
  if (easyMDE) {
    easyMDE.codemirror.on('change', updateSubmitButtonState);
  } else {
    textarea && textarea.addEventListener('input', updateSubmitButtonState);
  }
  updateSubmitButtonState();

  // list + pager
  const recs = [];
  let currentIndex = -1;
  const current = () => (currentIndex >= 0 ? recs[currentIndex] : null);

  const formatDateTime = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit'
    });
  };

  const applyIndex = (i) => {
    if (!recs.length) {
      pagerEl && (pagerEl.style.display = 'none');
      return;
    }
    currentIndex = Math.max(0, Math.min(i, recs.length - 1));
    const item = recs[currentIndex];

    // Fill editor
    setValue(getItemText(item));
    // Show card
    if (cardContainer) cardContainer.style.display = '';
    renderItem && cardContent && renderItem(item, cardContent);

    // Reset baseline & update submit disabled
    baseline = norm(getValue());
    updateSubmitButtonState();

    // Pager/UI
    pagerEl && (pagerEl.style.display = '');
    pagerLabel && (pagerLabel.textContent = `${currentIndex + 1}/${recs.length}`);
    const hasMultiple = recs.length > 1;
    showWhenMultipleEls.forEach((el) => {
      if (hasMultiple) {
        el.classList.remove('d-none');
      } else {
        el.classList.add('d-none');
      }
    });
    prevBtn && (prevBtn.disabled = currentIndex <= 0);
    nextBtn && (nextBtn.disabled = currentIndex >= recs.length - 1);
    createdAtEl && (createdAtEl.textContent = formatDateTime(item.created_at));
  };

  const getItemText = (item) => {
    const v = item && item[field];
    if (typeof v === 'string') return v;
    return JSON.stringify(v, null, 2);
  };

  let reload = async () => {};
  if (pagerEl) {
    reload = async () => {
      if (!topicUuid) return;
      try {
        const res = await fetch(listUrl(topicUuid));
        if (!res.ok) throw new Error('Failed to load');
        const data = await res.json();
        recs.length = 0;
        data.items && data.items.forEach(r => recs.push(r));
        if (recs.length) {
          applyIndex(recs.length - 1);
        } else {
          pagerEl.style.display = 'none';
        }
      } catch (e) {
        console.error(e);
      }
    };

    // expose generic hooks for status checker (e.g., __narrativeReloadAndJump / __narrativeExternalApply)
    try {
      const lower = key;
      window[`__${lower}ReloadAndJump`] = reload;
      window[`__${lower}ExternalApply`] = (text, createdAtIso) => {
        // card
        if (cardContainer) cardContainer.style.display = '';
        if (renderItem && cardContent) {
          const fakeItem = { [field]: text || '', created_at: createdAtIso || null, id: -1 };
          renderItem(fakeItem, cardContent);
        } else if (cardContent) {
          cardContent.textContent = text || '';
        }
        // editor
        setValue(text || '');
        // reset baseline & disable Update
        baseline = norm(getValue());
        updateSubmitButtonState();
        // created at label
        if (createdAtEl && createdAtIso) {
          const d = new Date(createdAtIso);
          createdAtEl.textContent = d.toLocaleString(undefined, {
            year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit'
          });
        }
      };
    } catch (err) {
      console.error('history hooks expose failed:', err);
    }

    // initial load (only when pager exists = edit mode)
    reload();

    // pager controls
    prevBtn && prevBtn.addEventListener('click', () => applyIndex(currentIndex - 1));
    nextBtn && nextBtn.addEventListener('click', () => applyIndex(currentIndex + 1));

    // delete flow
    deleteBtn && deleteBtn.addEventListener('click', () => {
      if (!current()) return;
      confirmModal && confirmModal.show();
    });

    confirmBtn && confirmBtn.addEventListener('click', async () => {
      const item = current();
      if (!item) return;
      confirmBtn.disabled = true;
      deleteSpinner && deleteSpinner.classList.remove('d-none');
      try {
        const res = await fetch(deleteUrl(item.id), { method: 'DELETE' });
        if (!res.ok && res.status !== 204) throw new Error('Delete failed');
        window.location.reload(); // per requirement
      } catch (e) {
        console.error(e);
        confirmModal && confirmModal.hide();
      } finally {
        confirmBtn.disabled = false;
        deleteSpinner && deleteSpinner.classList.add('d-none');
      }
    });
  }

  // ----- Suggest + Update flows (modal behavior unified for all keys) -----

  const afterPersistedChange = async () => {
    // After AI suggestion or manual Update, ensure list/card/editor/baseline are correct
    await reload();
  };

  // Suggest flow
  if (suggestionBtn && textarea && form) {
    suggestionBtn.addEventListener('click', async () => {
      controller && controller.showLoading();
      modal && modal.hide();
      suggestionBtn.disabled = true;

      try {
        const payload = buildSuggestionPayload() || {};
        if (!payload.topic_uuid) {
          payload.topic_uuid = topicUuid;
        }
        const res = await fetch(createUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error('Request failed');
        await res.json();

        controller && controller.showSuccess();
        await afterPersistedChange();
      } catch (err) {
        console.error(err);
        controller && controller.showError();
      } finally {
        suggestionBtn.disabled = false;
      }
    });
  }

  // Manual update flow
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      submitBtn && (submitBtn.disabled = true);
      controller && controller.showLoading();
      // Close modal if present
      const modalEl = document.getElementById(`${key}Modal`);
      const modal = modalEl && window.bootstrap ? bootstrap.Modal.getOrCreateInstance(modalEl) : null;
      modal && modal.hide();

      try {
        const payload = { topic_uuid: topicUuid };
        // Pass current text if textarea exists; otherwise an empty string
        const currentText = textarea ? getValue() : '';
        Object.assign(payload, parseInput(currentText));
        const res = await fetch(createUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error('Request failed');
        await res.json();

        // Manual update -> neutral (same as recap flow)
        controller && controller.reset();
        await afterPersistedChange();
      } catch (err) {
        console.error(err);
        controller && controller.showError();
      } finally {
        if (textarea) {
          submitBtn && (submitBtn.disabled = norm(getValue()) === baseline);
        } else {
          submitBtn && (submitBtn.disabled = false);
        }
      }
    });
  }
};

function capitalize(s){return s.charAt(0).toUpperCase()+s.slice(1);}
