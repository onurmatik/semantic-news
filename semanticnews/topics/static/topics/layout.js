(function () {
  const SIZE_OPTIONS = [
    { value: 'default', label: 'Default' },
    { value: 'compact', label: 'Compact' },
    { value: 'expanded', label: 'Expanded' },
  ];
  const PLACEMENTS = ['primary', 'sidebar'];
  const SAVE_DEBOUNCE_MS = 600;

  function ready(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback, { once: true });
    } else {
      callback();
    }
  }

  function getCsrfToken() {
    const name = 'csrftoken=';
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (let i = 0; i < cookies.length; i += 1) {
      const cookie = cookies[i].trim();
      if (cookie.startsWith(name)) {
        return decodeURIComponent(cookie.substring(name.length));
      }
    }
    return '';
  }

  function injectStyles() {
    if (document.getElementById('topic-layout-style')) {
      return;
    }
    const style = document.createElement('style');
    style.id = 'topic-layout-style';
    style.textContent = `
      [data-topic-layout] {
        position: relative;
      }
      .topic-module-wrapper {
        position: relative;
        border: 1px dashed transparent;
      }
      .topic-module-wrapper.topic-module--dragging {
        opacity: 0.5;
      }
      .topic-module-controls {
        display: flex;
        justify-content: flex-end;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
      }
      .topic-module-controls .form-select {
        width: auto;
      }
      .topic-module-handle {
        cursor: grab;
      }
      .topic-module-handle:active {
        cursor: grabbing;
      }
      .topic-layout-column--active {
        outline: 2px dashed var(--bs-primary, #0d6efd);
        outline-offset: 4px;
        border-radius: 0.5rem;
      }
    `;
    document.head.appendChild(style);
  }

  ready(() => {
    const layoutRoot = document.querySelector('[data-topic-layout]');
    if (!layoutRoot) {
      return;
    }
    if (layoutRoot.dataset.layoutEditable !== 'true') {
      return;
    }

    injectStyles();

    const topicUuid = layoutRoot.dataset.topicUuid;
    if (!topicUuid) {
      return;
    }

    const apiUrl = layoutRoot.dataset.layoutApiUrl || `/api/topics/${topicUuid}/layout`;
    const columns = Array.from(layoutRoot.querySelectorAll('[data-layout-column]'));
    if (!columns.length) {
      return;
    }

    let draggedModule = null;
    let saveTimeout = null;

    function scheduleSave() {
      if (saveTimeout) {
        window.clearTimeout(saveTimeout);
      }
      saveTimeout = window.setTimeout(saveLayout, SAVE_DEBOUNCE_MS);
    }

    function collectLayout() {
      const payload = [];
      columns.forEach((column) => {
        const placement = column.dataset.layoutColumn;
        Array.from(column.querySelectorAll('[data-module]')).forEach((moduleEl, index) => {
          moduleEl.dataset.displayOrder = String(index);
          payload.push({
            module_key: moduleEl.dataset.module,
            placement,
            size_variant: moduleEl.dataset.sizeVariant || 'default',
            display_order: index,
          });
        });
      });
      return payload;
    }

    async function saveLayout() {
      saveTimeout = null;
      const modules = collectLayout();
      if (!modules.length) {
        return;
      }
      try {
        await fetch(apiUrl, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          credentials: 'same-origin',
          body: JSON.stringify({ modules }),
        });
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Failed to save topic layout', error);
      }
    }

    function handleDragStart(event) {
      const target = event.currentTarget;
      draggedModule = target;
      target.classList.add('topic-module--dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', target.dataset.module || '');
    }

    function handleDragEnd() {
      if (draggedModule) {
        draggedModule.classList.remove('topic-module--dragging');
      }
      columns.forEach((column) => column.classList.remove('topic-layout-column--active'));
      draggedModule = null;
      scheduleSave();
    }

    function handleDragOver(event) {
      event.preventDefault();
      const column = event.currentTarget.closest('[data-layout-column]');
      if (column) {
        column.classList.add('topic-layout-column--active');
      }
      event.dataTransfer.dropEffect = 'move';
    }

    function handleDragLeave(event) {
      const column = event.currentTarget.closest('[data-layout-column]');
      if (column && !column.contains(event.relatedTarget)) {
        column.classList.remove('topic-layout-column--active');
      }
    }

    function handleDrop(event) {
      event.preventDefault();
      const column = event.currentTarget.closest('[data-layout-column]');
      if (!column || !draggedModule) {
        return;
      }

      const dropTarget = event.currentTarget.closest('[data-module]');
      if (dropTarget && dropTarget !== draggedModule) {
        const rect = dropTarget.getBoundingClientRect();
        const offset = event.clientY - rect.top;
        if (offset > rect.height / 2) {
          dropTarget.after(draggedModule);
        } else {
          dropTarget.before(draggedModule);
        }
      } else if (!dropTarget) {
        column.appendChild(draggedModule);
      }

      draggedModule.dataset.placement = column.dataset.layoutColumn || 'primary';
    }

    function handleColumnDrop(event) {
      event.preventDefault();
      if (!draggedModule) {
        return;
      }
      const column = event.currentTarget;
      column.appendChild(draggedModule);
      draggedModule.dataset.placement = column.dataset.layoutColumn || 'primary';
    }

    function addControls(moduleEl) {
      if (moduleEl.querySelector('.topic-module-controls')) {
        return;
      }
      if (moduleEl.dataset.hasContent !== 'true') {
        return;
      }

      const controls = document.createElement('div');
      controls.className = 'topic-module-controls';

      const handle = document.createElement('span');
      handle.className = 'topic-module-handle bi bi-grip-vertical';
      handle.title = 'Drag to reorder';
      controls.appendChild(handle);

      const placementSelect = document.createElement('select');
      placementSelect.className = 'form-select form-select-sm topic-module-placement';
      PLACEMENTS.forEach((placement) => {
        const option = document.createElement('option');
        option.value = placement;
        option.textContent = placement === 'primary' ? 'Primary column' : 'Sidebar';
        placementSelect.appendChild(option);
      });
      placementSelect.value = moduleEl.dataset.placement || moduleEl.closest('[data-layout-column]')?.dataset.layoutColumn || 'primary';
      placementSelect.addEventListener('change', () => {
        const targetPlacement = placementSelect.value;
        const targetColumn = columns.find((column) => column.dataset.layoutColumn === targetPlacement);
        if (!targetColumn) {
          return;
        }
        targetColumn.appendChild(moduleEl);
        moduleEl.dataset.placement = targetPlacement;
        scheduleSave();
      });
      controls.appendChild(placementSelect);

      const sizeSelect = document.createElement('select');
      sizeSelect.className = 'form-select form-select-sm topic-module-size';
      SIZE_OPTIONS.forEach((option) => {
        const opt = document.createElement('option');
        opt.value = option.value;
        opt.textContent = option.label;
        sizeSelect.appendChild(opt);
      });
      sizeSelect.value = moduleEl.dataset.sizeVariant || 'default';
      sizeSelect.addEventListener('change', () => {
        moduleEl.dataset.sizeVariant = sizeSelect.value;
        scheduleSave();
      });
      controls.appendChild(sizeSelect);

      moduleEl.insertBefore(controls, moduleEl.firstChild);
    }

    function initModule(moduleEl) {
      moduleEl.setAttribute('draggable', 'true');
      moduleEl.addEventListener('dragstart', handleDragStart);
      moduleEl.addEventListener('dragend', handleDragEnd);
      moduleEl.addEventListener('dragover', handleDragOver);
      moduleEl.addEventListener('dragleave', handleDragLeave);
      moduleEl.addEventListener('drop', handleDrop);
      if (!moduleEl.dataset.sizeVariant) {
        moduleEl.dataset.sizeVariant = 'default';
      }
      if (!moduleEl.dataset.placement) {
        const column = moduleEl.closest('[data-layout-column]');
        moduleEl.dataset.placement = column ? column.dataset.layoutColumn : 'primary';
      }
      addControls(moduleEl);
    }

    columns.forEach((column) => {
      column.classList.add('topic-layout-column');
      column.addEventListener('dragover', handleDragOver);
      column.addEventListener('drop', (event) => {
        handleColumnDrop(event);
        scheduleSave();
      });
      column.addEventListener('dragleave', handleDragLeave);
    });

    Array.from(layoutRoot.querySelectorAll('[data-module]')).forEach(initModule);

    layoutRoot.addEventListener('topicLayout:save', () => {
      scheduleSave();
    });
  });
})();
