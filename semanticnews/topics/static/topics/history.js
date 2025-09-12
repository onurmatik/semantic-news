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
  const getValue = () => easyMDE ? easyMDE.value() : (textarea ? textarea.value : '');
  const setValue = (v) => { if (easyMDE) easyMDE.value(v); else if (textarea) textarea.value = v; };
  const cardContainer = document.getElementById(`topic${capitalize(key)}Container`);
  const cardContent = document.getElementById(`topic${capitalize(key)}${cardSuffix}`);

  const pagerEl = document.getElementById(`${key}Pager`);
  const prevBtn = document.getElementById(`${key}Prev`);
  const nextBtn = document.getElementById(`${key}Next`);
  const pagerLabel = document.getElementById(`${key}PagerLabel`);
  const createdAtEl = document.getElementById(`${key}CreatedAt`);
  const deleteBtn = document.getElementById(`${key}DeleteBtn`);

  const confirmModalEl = document.getElementById(`confirmDelete${capitalize(key)}Modal`);
  const confirmBtn = document.getElementById(`confirmDelete${capitalize(key)}Btn`);
  const deleteSpinner = document.getElementById(`confirmDelete${capitalize(key)}Spinner`);
  const confirmModal = confirmModalEl && window.bootstrap ? bootstrap.Modal.getOrCreateInstance(confirmModalEl) : null;

  const container = document.querySelector('[data-topic-uuid]');
  const topicUuid = container ? container.getAttribute('data-topic-uuid') : null;

  const norm = (s) => (s || '').replace(/\r\n/g, '\n').replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
  let baseline = textarea ? norm(getValue()) : '';

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

    if (textarea) setValue(getItemText(item));
    cardContainer && (cardContainer.style.display = '');
    renderItem && renderItem(item, cardContent);
    baseline = norm(getValue());
    updateSubmitButtonState();

    pagerEl && (pagerEl.style.display = '');
    pagerLabel && (pagerLabel.textContent = `${currentIndex + 1}/${recs.length}`);
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

    prevBtn && prevBtn.addEventListener('click', () => applyIndex(currentIndex - 1));
    nextBtn && nextBtn.addEventListener('click', () => applyIndex(currentIndex + 1));

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
        window.location.reload();
      } catch (e) {
        console.error(e);
        confirmModal && confirmModal.hide();
      } finally {
        confirmBtn.disabled = false;
        deleteSpinner && deleteSpinner.classList.add('d-none');
      }
    });

    reload();
  }

  const afterPersistedChange = async () => {
    await reload();
  };

  if (suggestionBtn && textarea && form) {
    suggestionBtn.addEventListener('click', async () => {
      suggestionBtn.disabled = true;
      controller && controller.showLoading();
      try {
        const res = await fetch(createUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid })
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

  if (form && textarea) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      submitBtn && (submitBtn.disabled = true);
      controller && controller.showLoading();
      try {
        const payload = { topic_uuid: topicUuid };
        Object.assign(payload, parseInput(getValue()));
        const res = await fetch(createUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error('Request failed');
        await res.json();
        controller && controller.reset();
        await afterPersistedChange();
      } catch (err) {
        console.error(err);
        controller && controller.showError();
      } finally {
        submitBtn && (submitBtn.disabled = norm(getValue()) === baseline);
      }
    });
  }
};

function capitalize(s){return s.charAt(0).toUpperCase()+s.slice(1);} 
