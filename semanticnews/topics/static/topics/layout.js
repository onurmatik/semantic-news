(function () {
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
        align-items: center;
        gap: 0.5rem;
      }
      .topic-module-controls .btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.25rem;
        line-height: 1;
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
    let lastKnownLayoutSignature = null;

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
            display_order: index,
          });
        });
      });
      return payload;
    }

    async function saveLayout() {
      saveTimeout = null;
      const modules = collectLayout();
      const signature = JSON.stringify(modules);
      if (lastKnownLayoutSignature !== signature) {
        lastKnownLayoutSignature = signature;
        const changeEvent = new CustomEvent('topic:changed', { bubbles: true });
        layoutRoot.dispatchEvent(changeEvent);
        if (changeEvent.bubbles) {
          document.dispatchEvent(new CustomEvent('topic:changed'));
        }
      }
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
      updatePlacementButtons(draggedModule);
    }

    function handleColumnDrop(event) {
      event.preventDefault();
      if (!draggedModule) {
        return;
      }
      const column = event.currentTarget;
      column.appendChild(draggedModule);
      draggedModule.dataset.placement = column.dataset.layoutColumn || 'primary';
      updatePlacementButtons(draggedModule);
    }

    function moveModule(moduleEl, direction) {
      const column = moduleEl.closest('[data-layout-column]');
      if (!column) {
        return;
      }
      const modules = Array.from(column.querySelectorAll('[data-module]'));
      const index = modules.indexOf(moduleEl);
      if (index === -1) {
        return;
      }
      if (direction === 'up' && index > 0) {
        column.insertBefore(moduleEl, modules[index - 1]);
        scheduleSave();
      } else if (direction === 'down' && index < modules.length - 1) {
        const next = modules[index + 1].nextSibling;
        column.insertBefore(moduleEl, next);
        scheduleSave();
      }
    }

    function updatePlacementButtons(moduleEl) {
      const placement = moduleEl.dataset.placement || moduleEl.closest('[data-layout-column]')?.dataset.layoutColumn || 'primary';
      const controls = moduleEl.querySelector('.topic-module-controls');
      if (!controls) {
        return;
      }
      const moveLeftButton = controls.querySelector('.topic-module-move-left');
      const moveRightButton = controls.querySelector('.topic-module-move-right');
      if (!moveLeftButton || !moveRightButton) {
        return;
      }

      if (placement === 'primary') {
        moveLeftButton.classList.add('d-none');
        moveRightButton.classList.remove('d-none');
      } else {
        moveLeftButton.classList.remove('d-none');
        moveRightButton.classList.add('d-none');
      }
    }

    function moveModuleToPlacement(moduleEl, targetPlacement) {
      const targetColumn = columns.find((column) => column.dataset.layoutColumn === targetPlacement);
      if (!targetColumn) {
        return;
      }
      const currentPlacement = moduleEl.dataset.placement || moduleEl.closest('[data-layout-column]')?.dataset.layoutColumn;
      if (currentPlacement === targetPlacement) {
        return;
      }
      targetColumn.appendChild(moduleEl);
      moduleEl.dataset.placement = targetPlacement;
      updatePlacementButtons(moduleEl);
      scheduleSave();
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

      const moveUpButton = document.createElement('button');
      moveUpButton.type = 'button';
      moveUpButton.className = 'btn btn-outline-secondary btn-sm topic-module-move-up';
      moveUpButton.innerHTML = '<span class="bi bi-arrow-up"></span>';
      moveUpButton.title = 'Move up';
      moveUpButton.addEventListener('click', (event) => {
        event.preventDefault();
        moveModule(moduleEl, 'up');
      });
      controls.appendChild(moveUpButton);

      const moveDownButton = document.createElement('button');
      moveDownButton.type = 'button';
      moveDownButton.className = 'btn btn-outline-secondary btn-sm topic-module-move-down';
      moveDownButton.innerHTML = '<span class="bi bi-arrow-down"></span>';
      moveDownButton.title = 'Move down';
      moveDownButton.addEventListener('click', (event) => {
        event.preventDefault();
        moveModule(moduleEl, 'down');
      });
      controls.appendChild(moveDownButton);

      const moveLeftButton = document.createElement('button');
      moveLeftButton.type = 'button';
      moveLeftButton.className = 'btn btn-outline-secondary btn-sm topic-module-move-left';
      moveLeftButton.innerHTML = '<span class="bi bi-arrow-left"></span>';
      moveLeftButton.title = 'Move to primary column';
      moveLeftButton.addEventListener('click', (event) => {
        event.preventDefault();
        moveModuleToPlacement(moduleEl, 'primary');
      });
      controls.appendChild(moveLeftButton);

      const moveRightButton = document.createElement('button');
      moveRightButton.type = 'button';
      moveRightButton.className = 'btn btn-outline-secondary btn-sm topic-module-move-right';
      moveRightButton.innerHTML = '<span class="bi bi-arrow-right"></span>';
      moveRightButton.title = 'Move to sidebar';
      moveRightButton.addEventListener('click', (event) => {
        event.preventDefault();
        moveModuleToPlacement(moduleEl, 'sidebar');
      });
      controls.appendChild(moveRightButton);

      const headerActionsContainer =
        moduleEl.querySelector('[data-topic-module-header-actions]') ||
        (() => {
          const header = moduleEl.querySelector('.card-header');
          if (!header) {
            return null;
          }
          const container = document.createElement('div');
          container.className = 'd-flex align-items-center gap-2 ms-auto';
          container.dataset.topicModuleHeaderActions = 'true';
          header.appendChild(container);
          return container;
        })();

      if (headerActionsContainer) {
        headerActionsContainer.appendChild(controls);
      } else {
        moduleEl.insertBefore(controls, moduleEl.firstChild);
      }
      updatePlacementButtons(moduleEl);
    }

    function initModule(moduleEl) {
      moduleEl.setAttribute('draggable', 'true');
      moduleEl.addEventListener('dragstart', handleDragStart);
      moduleEl.addEventListener('dragend', handleDragEnd);
      moduleEl.addEventListener('dragover', handleDragOver);
      moduleEl.addEventListener('dragleave', handleDragLeave);
      moduleEl.addEventListener('drop', handleDrop);
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
    lastKnownLayoutSignature = JSON.stringify(collectLayout());

    layoutRoot.addEventListener('topicLayout:save', () => {
      scheduleSave();
    });
  });
})();
