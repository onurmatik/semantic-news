(function () {
  function ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  ready(() => {
    const topicContainer = document.querySelector('[data-topic-uuid]');
    if (!topicContainer) return;
    const topicUuid = topicContainer.getAttribute('data-topic-uuid');
    if (!topicUuid) return;

    const container = document.getElementById('topicRelationContainer');
    const listEl = document.getElementById('topicRelatedEntities');
    if (!listEl) return;
    const form = document.getElementById('relationForm');
    const textarea = document.getElementById('relationText');
    const statusMessageEl = document.getElementById('relationStatusMessage');
    const suggestionBtn = document.getElementById('fetchRelationSuggestion');
    const modalEl = document.getElementById('relationModal');
    const modal = modalEl && window.bootstrap
      ? window.bootstrap.Modal.getOrCreateInstance(modalEl)
      : null;
    const confirmModalEl = document.getElementById('confirmDeleteRelationModal');
    const confirmModal = confirmModalEl && window.bootstrap
      ? window.bootstrap.Modal.getOrCreateInstance(confirmModalEl)
      : null;
    const confirmBtn = document.getElementById('confirmDeleteRelationBtn');
    const confirmSpinner = document.getElementById('confirmDeleteRelationSpinner');

    const editMode = listEl && listEl.dataset.editMode === 'true';
    let pendingDeleteId = null;

    const showStatusMessage = (type, message) => {
      if (!statusMessageEl) return;
      statusMessageEl.classList.remove('d-none', 'alert-info', 'alert-success', 'alert-danger');
      const className = type === 'error' ? 'alert-danger' : type === 'success' ? 'alert-success' : 'alert-info';
      statusMessageEl.classList.add(className);
      statusMessageEl.textContent = message || '';
    };

    const clearStatusMessage = () => {
      if (!statusMessageEl) return;
      statusMessageEl.classList.add('d-none');
      statusMessageEl.classList.remove('alert-info', 'alert-success', 'alert-danger');
      statusMessageEl.textContent = '';
    };

    const setContainerVisibility = (hasItems) => {
      if (!container) return;
      if (editMode) {
        container.classList.remove('d-none');
        container.dataset.empty = hasItems ? 'false' : 'true';
      } else {
        if (hasItems) {
          container.style.display = '';
        } else {
          container.style.display = 'none';
        }
      }
    };

    const entityForTextarea = (entity) => ({
      name: entity.entity_name || '',
      role: entity.role || null,
      disambiguation: entity.entity_disambiguation || null,
    });

    const prettyPrintEntities = (entities) => {
      return JSON.stringify(entities.map(entityForTextarea), null, 2);
    };

    const emptyMessage = listEl ? (listEl.dataset.emptyMessage || 'No related entities yet.') : 'No related entities yet.';

    const renderEntities = (entities) => {
      if (!listEl) return;
      listEl.innerHTML = '';

      if (!entities || !entities.length) {
        const empty = document.createElement('p');
        empty.className = 'text-secondary small mb-0';
        empty.dataset.emptyState = 'true';
        empty.textContent = emptyMessage;
        listEl.appendChild(empty);
        setContainerVisibility(false);
        return;
      }

      for (const entity of entities) {
        const wrapper = document.createElement('div');
        wrapper.className = 'border rounded px-3 py-2 d-flex align-items-start justify-content-between';
        wrapper.dataset.relatedEntityId = entity.id;

        const info = document.createElement('div');
        info.className = 'me-3';
        const title = document.createElement('div');
        title.className = 'fw-semibold';
        title.textContent = entity.entity_name || '';
        info.appendChild(title);

        if (entity.entity_disambiguation) {
          const detail = document.createElement('div');
          detail.className = 'text-secondary small';
          detail.textContent = entity.entity_disambiguation;
          info.appendChild(detail);
        }

        if (entity.role) {
          const role = document.createElement('div');
          role.className = 'text-secondary small';
          role.textContent = entity.role;
          info.appendChild(role);
        }

        wrapper.appendChild(info);

        if (editMode) {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'btn btn-link text-danger p-0';
          btn.setAttribute('data-remove-related-entity', entity.id);
          btn.setAttribute('aria-label', 'Remove entity');
          btn.innerHTML = '<i class="bi bi-trash"></i>';
          wrapper.appendChild(btn);
        }

        listEl.appendChild(wrapper);
      }

      setContainerVisibility(true);

      if (textarea) {
        textarea.value = prettyPrintEntities(entities);
      }
    };

    const fetchEntities = async () => {
      try {
        const res = await fetch(`/api/topics/relation/${topicUuid}/list`);
        if (!res.ok) return;
        const data = await res.json();
        const items = Array.isArray(data.items) ? data.items : [];
        renderEntities(items);
      } catch (err) {
        console.error(err);
      }
    };

    const parseTextarea = () => {
      if (!textarea) return [];
      const text = textarea.value.trim();
      if (!text) return [];
      try {
        const parsed = JSON.parse(text);
        if (!Array.isArray(parsed)) {
          throw new Error('JSON must be an array.');
        }
        return parsed.map((item) => ({
          name: typeof item.name === 'string' ? item.name : '',
          role: item.role || null,
          disambiguation: item.disambiguation || null,
        })).filter((item) => item.name);
      } catch (err) {
        throw new Error('Invalid JSON');
      }
    };

    const submitEntities = async (entities, sourceMessage) => {
      try {
        const res = await fetch('/api/topics/relation/extract', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid, entities }),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => null);
          const message = data && (data.detail || data.error || data.message);
          throw new Error(message || 'Unable to save the entities. Please try again.');
        }
        const data = await res.json();
        const items = Array.isArray(data.entities) ? data.entities : [];
        renderEntities(items);
        if (sourceMessage) {
          showStatusMessage('success', sourceMessage);
        } else {
          clearStatusMessage();
        }
        if (!editMode && modal) {
          modal.hide();
        }
      } catch (err) {
        showStatusMessage('error', err.message || 'Unable to save the entities. Please try again.');
      }
    };

    if (form && textarea) {
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        clearStatusMessage();
        let entities;
        try {
          entities = parseTextarea();
        } catch (err) {
          showStatusMessage('error', err.message || 'Enter valid JSON before saving.');
          return;
        }
        await submitEntities(entities);
      });
    }

    if (modalEl) {
      modalEl.addEventListener('show.bs.modal', () => {
        clearStatusMessage();
      });
    }

    if (suggestionBtn) {
      suggestionBtn.addEventListener('click', async () => {
        clearStatusMessage();
        try {
          const res = await fetch('/api/topics/relation/extract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic_uuid: topicUuid }),
          });
          if (!res.ok) {
            const data = await res.json().catch(() => null);
            const message = data && (data.detail || data.error || data.message);
            throw new Error(message || 'Unable to fetch entity suggestions.');
          }
          const data = await res.json();
          const items = Array.isArray(data.entities) ? data.entities : [];
          renderEntities(items);
          showStatusMessage('success', 'Suggestions applied successfully.');
        } catch (err) {
          showStatusMessage('error', err.message || 'Unable to fetch entity suggestions.');
        }
      });
    }

    if (listEl && editMode) {
      listEl.addEventListener('click', (event) => {
        const target = event.target.closest('[data-remove-related-entity]');
        if (!target) return;
        event.preventDefault();
        const id = target.getAttribute('data-remove-related-entity');
        if (!id) return;
        pendingDeleteId = id;
        if (confirmModal) confirmModal.show();
      });
    }

    if (listEl) {
      listEl.addEventListener('topics:relations:fallback', (event) => {
        const detail = event.detail && Array.isArray(event.detail.entities)
          ? event.detail.entities
          : [];
        renderEntities(detail);
      });
    }

    if (confirmBtn) {
      confirmBtn.addEventListener('click', async () => {
        if (!pendingDeleteId) return;
        confirmBtn.disabled = true;
        if (confirmSpinner) confirmSpinner.classList.remove('d-none');
        try {
          const res = await fetch(`/api/topics/relation/${pendingDeleteId}`, {
            method: 'DELETE',
          });
          if (!res.ok && res.status !== 204) {
            throw new Error('Unable to remove the entity. Please try again.');
          }
          pendingDeleteId = null;
          if (confirmModal) confirmModal.hide();
          await fetchEntities();
        } catch (err) {
          alert(err.message || 'Unable to remove the entity.');
        } finally {
          confirmBtn.disabled = false;
          if (confirmSpinner) confirmSpinner.classList.add('d-none');
        }
      });
    }

    // Initial render uses pre-rendered textarea value if available
    if (textarea) {
      try {
        const initial = parseTextarea();
        if (initial && initial.length) {
          // no-op, server rendering already visible
        } else if (!editMode && container) {
          container.style.display = 'none';
        }
      } catch (err) {
        // Ignore invalid server-side value
      }
    }

    // Ensure container visibility matches server data on load
    if (listEl) {
      const hasItems = listEl.querySelectorAll('[data-related-entity-id]').length > 0;
      setContainerVisibility(hasItems);
    }

    // Refresh list from the API when editing to ensure data is current
    if (form) {
      fetchEntities();
    }
  });
})();
