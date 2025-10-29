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

    const widgetList = document.querySelector('[data-topic-primary-widgets]');
    if (!widgetList) {
      return;
    }

    const panelMap = new Map();
    const entryMap = new Map();

    panels.forEach((panel) => {
      const key = panel.dataset.contentEditor;
      if (!key) {
        return;
      }
      panelMap.set(key, panel);
      panel.classList.add('d-none');
    });

    const createEntryForPanel = (panel) => {
      if (!panel) return;
      if (entryMap.has(panel)) {
        const existingEntry = entryMap.get(panel);
        if (existingEntry && typeof existingEntry.scrollIntoView === 'function') {
          existingEntry.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        panel.dispatchEvent(new CustomEvent('content-toolbar:show', { bubbles: true }));
        return;
      }

      const entry = document.createElement('div');
      entry.className = 'topic-widget-entry';
      entry.dataset.topicWidgetEntry = '';
      entry.dataset.topicWidget = panel.dataset.contentEditor || '';
      entry.dataset.topicWidgetKey = '';

      panel.classList.remove('d-none');
      entry.appendChild(panel);
      widgetList.appendChild(entry);
      entryMap.set(panel, entry);

      panel.dispatchEvent(new CustomEvent('content-toolbar:show', { bubbles: true }));

      if (typeof entry.scrollIntoView === 'function') {
        entry.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    };

    const dismissPanel = (panel) => {
      if (!panel) return;
      const entry = entryMap.get(panel);
      if (!entry) {
        return;
      }
      panel.dispatchEvent(new CustomEvent('content-toolbar:hide', { bubbles: true }));
      panel.classList.add('d-none');
      panelsContainer.appendChild(panel);
      entry.remove();
      entryMap.delete(panel);
    };

    toolbar.addEventListener('click', (event) => {
      const button = event.target.closest('[data-toolbar-button]');
      if (button) {
        const key = button.dataset.toolbarButton;
        if (key && panelMap.has(key)) {
          event.preventDefault();
          createEntryForPanel(panelMap.get(key));
        }
      }
    });

    document.addEventListener('click', (event) => {
      const dismiss = event.target.closest('[data-toolbar-dismiss]');
      if (!dismiss) {
        return;
      }
      const key = dismiss.dataset.toolbarDismiss;
      if (!key) {
        return;
      }
      const panel = panelMap.get(key);
      if (!panel) {
        return;
      }
      event.preventDefault();
      dismissPanel(panel);
    });
  });
}());
