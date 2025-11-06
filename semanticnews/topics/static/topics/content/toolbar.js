(function () {
  const CATALOG_SCRIPT_ID = 'widget-catalog-data';
  const DEFINITIONS_ENDPOINT = '/api/widgets/definitions';
  const registry = () => window.TopicWidgetRegistry;

  function ready(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback, { once: true });
    } else {
      callback();
    }
  }

  function parseCatalogScript() {
    const script = document.getElementById(CATALOG_SCRIPT_ID);
    if (!script) {
      return null;
    }
    try {
      const data = JSON.parse(script.textContent || '[]');
      return Array.isArray(data) ? data : null;
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to parse widget catalog bootstrap', error);
    }
    return null;
  }

  async function fetchCatalog() {
    const bootstrap = parseCatalogScript();
    if (bootstrap && bootstrap.length) {
      return bootstrap;
    }

    try {
      const response = await fetch(DEFINITIONS_ENDPOINT, { credentials: 'same-origin' });
      if (!response.ok) {
        throw new Error('Unable to load widget definitions');
      }
      const payload = await response.json();
      const items = payload && Array.isArray(payload.items) ? payload.items : [];
      return items;
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error(error);
      return [];
    }
  }

  function buildTemplateMap(container) {
    const map = new Map();
    if (!container) {
      return map;
    }
    container.querySelectorAll('template[data-widget-panel]').forEach((template) => {
      const key = template.dataset.widgetPanel;
      if (key) {
        map.set(key, template);
      }
    });
    return map;
  }

  function deriveKey(definition) {
    if (!definition) {
      return '';
    }
    if (definition.key) {
      return definition.key;
    }
    const source = definition.name || '';
    const slug = source
      .toString()
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)+/g, '');
    if (slug) {
      return slug;
    }
    if (definition.id) {
      return `widget-${definition.id}`;
    }
    return `widget-${Math.random().toString(36).slice(2, 8)}`;
  }

  function createEntry(widget, template, widgetList) {
    if (!template || !widgetList) {
      return null;
    }

    const fragment = template.content.cloneNode(true);
    if (!fragment) {
      return null;
    }

    const card = fragment.querySelector('[data-topic-widget]');
    if (!card) {
      return null;
    }

    const entry = document.createElement('div');
    entry.className = 'topic-widget-entry';
    entry.dataset.topicWidgetEntry = '';
    entry.dataset.topicWidgetKey = deriveKey(widget);
    entry.dataset.widgetDefinitionId = widget.id ? String(widget.id) : '';

    const actions = card.querySelector('[data-topic-module-header-actions]');
    if (actions) {
      const closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.className = 'btn btn-outline-secondary btn-sm';
      closeBtn.innerHTML = '<span class="visually-hidden">Close</span><i class="bi bi-x" aria-hidden="true"></i>';
      closeBtn.title = 'Close editor';
      closeBtn.setAttribute('aria-label', 'Close editor');
      closeBtn.addEventListener('click', () => {
        entry.dispatchEvent(new CustomEvent('widget-editor:destroy', { detail: { widget }, bubbles: true }));
        entry.remove();
      });
      actions.prepend(closeBtn);
    }

    entry.appendChild(fragment);
    widgetList.appendChild(entry);
    return entry;
  }

  function resolveTopicUuid() {
    const container = document.querySelector('[data-topic-uuid]');
    if (!container) {
      return null;
    }
    return container.getAttribute('data-topic-uuid') || container.dataset.topicUuid || null;
  }

  function notifyInit(entry, widget, topicUuid) {
    if (!entry) {
      return;
    }
    const controller = registry();
    const detail = {
      element: entry.querySelector('[data-topic-widget]'),
      entry,
      definition: Object.assign({}, widget, { key: deriveKey(widget) }),
      topicUuid,
    };
    if (controller) {
      controller.init(widget.key, detail);
    }
    entry.dispatchEvent(new CustomEvent('widget-editor:init', { detail, bubbles: true }));
  }

  ready(async () => {
    const toolbar = document.querySelector('[data-widget-toolbar]');
    if (!toolbar) {
      return;
    }

    const widgetList = document.querySelector('[data-topic-primary-widgets]');
    if (!widgetList) {
      return;
    }

    const panelsContainer = toolbar.querySelector('[data-toolbar-panels]');
    const templateMap = buildTemplateMap(panelsContainer);
    const buttonsContainer = toolbar.querySelector('[data-toolbar-buttons]');
    if (!buttonsContainer) {
      return;
    }

    const topicUuid = resolveTopicUuid();
    const catalog = await fetchCatalog();
    const catalogMap = new Map();
    catalog.forEach((item) => {
      if (!item) {
        return;
      }
      const key = deriveKey(item);
      if (key) {
        const enhanced = Object.assign({}, item, { key });
        catalogMap.set(key, enhanced);
      }
    });

    buttonsContainer.addEventListener('click', (event) => {
      const button = event.target.closest('[data-toolbar-button]');
      if (!button) {
        return;
      }
      const key = button.getAttribute('data-toolbar-button');
      if (!key) {
        return;
      }

      let definition = catalogMap.get(key);
      if (!definition) {
        const name = button.textContent ? button.textContent.trim() : '';
        const idAttr = button.getAttribute('data-widget-definition-id');
        const id = idAttr ? parseInt(idAttr, 10) : null;
        definition = {
          id: Number.isFinite(id) ? id : null,
          key,
          name,
        };
        catalogMap.set(key, definition);
      }
      const template = templateMap.get(key);
      if (!definition || !template) {
        return;
      }

      event.preventDefault();
      const entry = createEntry(definition, template, widgetList);
      if (entry) {
        notifyInit(entry, definition, topicUuid);
        if (typeof entry.scrollIntoView === 'function') {
          entry.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }
    });
  });
}());
