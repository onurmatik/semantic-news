(function () {
  const CATALOG_SCRIPT_ID = 'widget-catalog-data';
  const DEFINITIONS_ENDPOINT = '/api/topics/widgets/definitions';
  const DEFAULT_SECTIONS_ENDPOINT = '/api/topics/widgets/sections';
  const registry = () => window.TopicWidgetRegistry;
  const shared = () => window.TopicWidgetShared;

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
      if (Array.isArray(payload)) {
        return payload;
      }
      if (payload && Array.isArray(payload.items)) {
        return payload.items;
      }
      if (payload && Array.isArray(payload.results)) {
        return payload.results;
      }
      if (payload && payload.data && Array.isArray(payload.data)) {
        return payload.data;
      }
      return [];
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
      // eslint-disable-next-line no-console
      console.warn('[TopicWidgets][Toolbar] Unable to create entry: missing template or widget list', {
        hasTemplate: Boolean(template),
        hasWidgetList: Boolean(widgetList),
      });
      return null;
    }

    const fragment = template.content.cloneNode(true);
    if (!fragment) {
      // eslint-disable-next-line no-console
      console.warn('[TopicWidgets][Toolbar] Unable to create entry: template fragment missing');
      return null;
    }

    const card = fragment.querySelector('[data-topic-widget]');
    if (!card) {
      // eslint-disable-next-line no-console
      console.warn('[TopicWidgets][Toolbar] Unable to create entry: no [data-topic-widget] found in template', {
        templateHtml: template.innerHTML ? template.innerHTML.slice(0, 200) : null,
      });
      return null;
    }

    const entry = document.createElement('div');
    entry.className = 'topic-widget-entry';
    entry.dataset.topicWidgetEntry = '';
    entry.dataset.topicWidgetKey = deriveKey(widget);
    entry.dataset.widgetDefinitionId = widget.id ? String(widget.id) : '';

    const actions = card.querySelector('[data-topic-module-header-actions]');
    if (actions) {
      const createActionButtons = () => {
        const buttons = [];
       const availableActions = Array.isArray(widget.actions) ? [...widget.actions] : [];

        const appendDefaultParagraphActions = () => {
          const normalizedKey = (widget.key || '').toLowerCase();
          if (normalizedKey !== 'paragraph') {
            return;
          }

          const existingActions = new Set(
            availableActions
              .map((action) => action && (action.id || action.name))
              .filter(Boolean)
              .map((identifier) => String(identifier).trim().toLowerCase()),
          );

          [
            { id: 'summarize', name: 'summarize', icon: 'bi bi-sort-down' },
            { id: 'expand', name: 'expand', icon: 'bi bi-sort-up' },
          ].forEach((fallback) => {
            const identifier = (fallback.id || fallback.name || '').trim().toLowerCase();
            if (!identifier || existingActions.has(identifier)) {
              return;
            }
            availableActions.push(fallback);
            existingActions.add(identifier);
          });
        };

        appendDefaultParagraphActions();
        availableActions.forEach((action) => {
          if (!action) {
            return;
          }
          const label = typeof action.name === 'string' ? action.name.trim() : '';
          const actionIdentifier = (() => {
            if (action.id != null) {
              const raw = String(action.id).trim();
              if (raw) {
                return raw;
              }
            }
            if (label) {
              return label;
            }
            return '';
          })();
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'btn btn-outline-primary btn-sm';
          if (action.id != null) {
            button.dataset.widgetActionId = String(action.id);
          }
          if (actionIdentifier) {
            button.dataset.widgetAction = actionIdentifier;
          }
          if (label) {
            button.dataset.widgetActionName = label;
          }
          if (label) {
            button.title = label;
            button.setAttribute('aria-label', label);
          } else {
            button.setAttribute('aria-label', 'Widget action');
          }

          const iconClass = typeof action.icon === 'string' && action.icon.trim()
            ? action.icon.trim()
            : 'bi bi-stars';
          const icon = document.createElement('i');
          icon.className = iconClass;
          icon.setAttribute('aria-hidden', 'true');
          button.appendChild(icon);

          if (label) {
            const srText = document.createElement('span');
            srText.className = 'visually-hidden';
            srText.textContent = label;
            button.appendChild(srText);
          }

          const normalizedKey = (widget.key || '').toLowerCase();
          const normalizedAction = actionIdentifier.toLowerCase();
          if (normalizedKey === 'paragraph') {
            if (normalizedAction === 'generate') {
              button.dataset.widgetVisibility = 'draft';
            } else if (normalizedAction === 'summarize' || normalizedAction === 'expand') {
              button.dataset.widgetVisibility = 'saved-with-text';
              button.classList.add('d-none');
            }
          } else if (normalizedKey === 'image') {
            if (normalizedAction === 'generate') {
              button.dataset.widgetVisibility = 'needs-image';
            } else if (normalizedAction === 'variate') {
              button.dataset.widgetVisibility = 'saved-with-image';
              button.classList.add('d-none');
            }
          }

          buttons.push(button);
        });
        return buttons;
      };

      const actionButtons = createActionButtons();
      actionButtons.forEach((button) => {
        actions.appendChild(button);
      });

      const closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.className = 'btn btn-outline-secondary btn-sm';
      closeBtn.title = 'Close editor';
      closeBtn.setAttribute('aria-label', 'Close editor');
      closeBtn.dataset.widgetVisibility = 'draft';
      closeBtn.dataset.widgetClose = 'true';

      const closeIcon = document.createElement('i');
      closeIcon.className = 'bi bi-x';
      closeIcon.setAttribute('aria-hidden', 'true');
      closeBtn.appendChild(closeIcon);

      const closeText = document.createElement('span');
      closeText.className = 'visually-hidden';
      closeText.textContent = 'Close editor';
      closeBtn.appendChild(closeText);

      closeBtn.addEventListener('click', () => {
        entry.dispatchEvent(new CustomEvent('widget-editor:destroy', { detail: { widget }, bubbles: true }));
        entry.remove();
      });

      actions.appendChild(closeBtn);

      const deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.className = 'btn btn-outline-danger btn-sm d-none';
      deleteBtn.dataset.widgetDeleteSectionId = '';
      deleteBtn.dataset.widgetVisibility = 'saved';
      deleteBtn.dataset.widgetDeleteLabel = widget.key === 'image' ? 'image' : 'paragraph';
      deleteBtn.title = `Delete ${deleteBtn.dataset.widgetDeleteLabel}`;
      deleteBtn.setAttribute('aria-label', deleteBtn.title);

      const deleteIcon = document.createElement('i');
      deleteIcon.className = 'bi bi-trash';
      deleteIcon.setAttribute('aria-hidden', 'true');
      deleteBtn.appendChild(deleteIcon);

      const deleteText = document.createElement('span');
      deleteText.className = 'visually-hidden';
      deleteText.textContent = deleteBtn.title;
      deleteBtn.appendChild(deleteText);

      actions.appendChild(deleteBtn);
    }

    entry.appendChild(fragment);
    widgetList.appendChild(entry);
    // eslint-disable-next-line no-console
    console.info('[TopicWidgets][Toolbar] Created widget entry', {
      widgetKey: entry.dataset.topicWidgetKey,
      definitionId: entry.dataset.widgetDefinitionId,
    });
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

  function resolveSectionsEndpoint(definition) {
    if (!definition) {
      return DEFAULT_SECTIONS_ENDPOINT;
    }
    const identifier = definition.key || definition.id;
    if (identifier) {
      const encoded = encodeURIComponent(String(identifier));
      return `/api/topics/widgets/${encoded}/sections`;
    }
    return DEFAULT_SECTIONS_ENDPOINT;
  }

  async function requestServerSection(definition, topicUuid) {
    if (!definition || !topicUuid) {
      return null;
    }

    const { getCsrfToken } = shared() || {};
    const endpoint = resolveSectionsEndpoint(definition);
    const payload = {
      topic_uuid: topicUuid,
      widget_id: definition.key || definition.id || null,
    };

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': typeof getCsrfToken === 'function' ? getCsrfToken() : '',
      },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Unable to create widget section (status ${response.status})`);
    }

    const data = await response.json();
    return data && data.shell ? String(data.shell) : '';
  }

  function buildEntryFromShell(shell) {
    if (!shell) {
      return null;
    }
    const container = document.createElement('div');
    container.innerHTML = shell;
    const entry = container.querySelector('[data-topic-widget-entry]') || container.firstElementChild;
    if (entry) {
      entry.dataset.topicWidgetEntry = entry.dataset.topicWidgetEntry || '';
    }
    return entry || null;
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
    // eslint-disable-next-line no-console
    console.info('[TopicWidgets][Toolbar] Initialised template map', {
      keys: Array.from(templateMap.keys()),
      panelCount: templateMap.size,
    });
    const buttonsContainer = toolbar.querySelector('[data-toolbar-buttons]');
    if (!buttonsContainer) {
      return;
    }

    const buttons = Array.from(buttonsContainer.querySelectorAll('[data-toolbar-button]'));
    // eslint-disable-next-line no-console
    console.info('[TopicWidgets][Toolbar] Discovered widget toolbar buttons', {
      total: buttons.length,
      disabled: buttons.filter((button) => button.disabled).map((button) => button.getAttribute('data-toolbar-button')),
      keys: buttons.map((button) => button.getAttribute('data-toolbar-button')),
    });

    const topicUuid = resolveTopicUuid();
    const catalog = await fetchCatalog();
    // eslint-disable-next-line no-console
    console.info('[TopicWidgets][Toolbar] Loaded widget catalog', {
      fromBootstrap: Boolean(parseCatalogScript()),
      count: Array.isArray(catalog) ? catalog.length : 0,
    });
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

    // eslint-disable-next-line no-console
    console.info('[TopicWidgets][Toolbar] Catalog map ready', {
      keys: Array.from(catalogMap.keys()),
    });
    buttonsContainer.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-toolbar-button]');
      if (!button) {
        return;
      }
      // eslint-disable-next-line no-console
      console.info('[TopicWidgets][Toolbar] Widget toolbar button click', {
        buttonKey: button.getAttribute('data-toolbar-button'),
        buttonDisabled: button.disabled,
      });
      const key = button.getAttribute('data-toolbar-button');
      if (!key) {
        // eslint-disable-next-line no-console
        console.warn('[TopicWidgets][Toolbar] Clicked widget button without key', { button });
        return;
      }
      let definition = catalogMap.get(key);
      if (!definition) {
        const name = button.textContent ? button.textContent.trim() : '';
        const idAttr = button.getAttribute('data-widget-definition-id');
        const rawId = idAttr && idAttr.trim();

        definition = {
          // prefer an explicit ID from markup; otherwise fall back to the key
          id: rawId || key,
          key,
          name,
        };
        catalogMap.set(key, definition);
      }
      const template = templateMap.get(key);
      // eslint-disable-next-line no-console
      console.info('[TopicWidgets][Toolbar] Resolved widget definition', {
        key,
        hasDefinition: Boolean(definition),
        hasTemplate: Boolean(template),
        definition,
      });
      if (!definition) {
        // eslint-disable-next-line no-console
        console.warn('[TopicWidgets][Toolbar] Missing definition for key', {
          key,
          hasDefinition: Boolean(definition),
          hasTemplate: Boolean(template),
        });
        return;
      }
      event.preventDefault();

      let entry = null;
      const resetButtonState = () => {
        button.removeAttribute('aria-busy');
      };

      button.setAttribute('aria-busy', 'true');

      try {
        const shell = await requestServerSection(definition, topicUuid);
        entry = buildEntryFromShell(shell);

        if (!entry) {
          // eslint-disable-next-line no-console
          console.warn('[TopicWidgets][Toolbar] Server did not provide widget shell, falling back to template render');
          entry = createEntry(definition, template, widgetList);
        }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[TopicWidgets][Toolbar] Failed to create widget section', error);
        entry = createEntry(definition, template, widgetList);
      } finally {
        resetButtonState();
      }

      // eslint-disable-next-line no-console
      console.info('[TopicWidgets][Toolbar] Entry creation result', {
        key,
        entryCreated: Boolean(entry),
        widgetDefinitionId: definition.id,
        widgetKey: definition.key,
      });

      if (entry) {
        if (!entry.dataset.widgetDefinitionId && definition.id != null) {
          entry.dataset.widgetDefinitionId = String(definition.id);
        }
        if (entry.parentNode !== widgetList) {
          widgetList.appendChild(entry);
        }
        notifyInit(entry, definition, topicUuid);
        if (typeof entry.scrollIntoView === 'function') {
          entry.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }
    });
  });
}());
