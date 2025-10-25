(function () {
  function ready(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback, { once: true });
    } else {
      callback();
    }
  }

  ready(() => {
    const toolbar = document.querySelector('[data-content-toolbar]');
    if (!toolbar) {
      return;
    }

    const panelsContainer = toolbar.querySelector('[data-toolbar-panels]');
    if (!panelsContainer) {
      return;
    }

    const panels = Array.from(panelsContainer.querySelectorAll('[data-content-editor]'));
    if (!panels.length) {
      return;
    }

    const panelMap = new Map();
    panels.forEach((panel) => {
      const key = panel.dataset.contentEditor;
      if (key) {
        panelMap.set(key, panel);
      }
    });

    const hidePanel = (panel) => {
      if (!panel) return;
      if (panel.classList.contains('d-none')) {
        return;
      }
      panel.classList.add('d-none');
      panel.dispatchEvent(new CustomEvent('content-toolbar:hide', { bubbles: true }));
    };

    const showPanel = (panel) => {
      if (!panel) return;
      if (!panel.classList.contains('d-none')) {
        return;
      }
      panels.forEach((other) => {
        if (other !== panel) {
          hidePanel(other);
        }
      });
      panel.classList.remove('d-none');
      panel.dispatchEvent(new CustomEvent('content-toolbar:show', { bubbles: true }));
    };

    const togglePanel = (key) => {
      if (!key) return;
      const panel = panelMap.get(key);
      if (!panel) return;
      if (panel.classList.contains('d-none')) {
        showPanel(panel);
      } else {
        hidePanel(panel);
      }
    };

    toolbar.addEventListener('click', (event) => {
      const button = event.target.closest('[data-toolbar-button]');
      if (button) {
        event.preventDefault();
        togglePanel(button.dataset.toolbarButton);
      }
      const dismiss = event.target.closest('[data-toolbar-dismiss]');
      if (dismiss) {
        event.preventDefault();
        togglePanel(dismiss.dataset.toolbarDismiss);
      }
    });
  });
}());
