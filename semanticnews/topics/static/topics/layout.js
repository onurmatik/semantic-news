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
    const moduleList = layoutRoot.querySelector('[data-layout-list]');
    if (!moduleList) {
      return;
    }

    let draggedModule = null;
    let saveTimeout = null;
    let lastKnownLayoutSignature = null;

    const reorderableSelector = '[data-layout-reorderable="true"]';

    function getReorderableModules() {
      return Array.from(moduleList.querySelectorAll(reorderableSelector));
    }

    function scheduleSave() {
      if (saveTimeout) {
        window.clearTimeout(saveTimeout);
      }
      saveTimeout = window.setTimeout(saveLayout, SAVE_DEBOUNCE_MS);
    }

    function collectLayout() {
      const payload = [];
      getReorderableModules().forEach((moduleEl, index) => {
        moduleEl.dataset.displayOrder = String(index);
        payload.push({
          module_key: moduleEl.dataset.module || '',
          placement: moduleEl.dataset.placement || 'primary',
          display_order: index,
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

    function handleDragStart(event, moduleOverride = null) {
      const target = moduleOverride || event.currentTarget;
      if (!(target instanceof Element)) {
        return;
      }
      draggedModule = target;
      target.classList.add('topic-module--dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', target.dataset.module || '');
      if (event.dataTransfer.setDragImage) {
        const rect = target.getBoundingClientRect();
        const offsetX = event.clientX - rect.left;
        const offsetY = event.clientY - rect.top;
        event.dataTransfer.setDragImage(target, offsetX, offsetY);
      }
    }

    function handleDragEnd() {
      if (draggedModule) {
        draggedModule.classList.remove('topic-module--dragging');
      }
      draggedModule = null;
    }

    function handleDragOver(event) {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
    }

    function handleDrop(event) {
      event.preventDefault();
      if (!draggedModule) {
        return;
      }

      const dropTarget = event.currentTarget.closest(reorderableSelector);
      if (dropTarget && dropTarget !== draggedModule) {
        const rect = dropTarget.getBoundingClientRect();
        const offset = event.clientY - rect.top;
        if (offset > rect.height / 2) {
          dropTarget.after(draggedModule);
        } else {
          dropTarget.before(draggedModule);
        }
        scheduleSave();
      }
    }

    function moveModule(moduleEl, direction) {
      const modules = getReorderableModules();
      const index = modules.indexOf(moduleEl);
      if (index === -1) {
        return;
      }
      if (direction === 'up' && index > 0) {
        const previousModule = modules[index - 1];
        moduleEl.parentNode.insertBefore(moduleEl, previousModule);
        scheduleSave();
      } else if (direction === 'down' && index < modules.length - 1) {
        const next = modules[index + 1].nextSibling;
        moduleEl.parentNode.insertBefore(moduleEl, next);
        scheduleSave();
      }
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
      handle.setAttribute('draggable', 'true');
      handle.addEventListener('dragstart', (event) => {
        handleDragStart(event, moduleEl);
      });
      handle.addEventListener('dragend', handleDragEnd);
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
    }

    function initModule(moduleEl) {
      moduleEl.addEventListener('dragover', handleDragOver);
      moduleEl.addEventListener('drop', handleDrop);
      addControls(moduleEl);
    }

    moduleList.addEventListener('dragover', handleDragOver);
    moduleList.addEventListener('drop', (event) => {
      event.preventDefault();
      if (!draggedModule) {
        return;
      }
      moduleList.appendChild(draggedModule);
      scheduleSave();
    });

    getReorderableModules().forEach(initModule);
    lastKnownLayoutSignature = JSON.stringify(collectLayout());

    layoutRoot.addEventListener('topicLayout:save', () => {
      scheduleSave();
    });
  });
})();
