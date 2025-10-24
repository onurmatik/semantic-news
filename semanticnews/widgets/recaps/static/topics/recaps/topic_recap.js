document.addEventListener('DOMContentLoaded', () => {
  const controller = typeof setupGenerationButton === 'function'
    ? setupGenerationButton({
        buttonId: 'recapButton',
        spinnerId: 'recapSpinner',
        errorIconId: 'recapErrorIcon',
        successIconId: 'recapSuccessIcon',
      })
    : null;

  const sanitize = (text) => (text || '')
    .replace(/\r\n/g, '\n')
    .replace(/[\t\u00a0]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  const collectModuleText = (moduleEl) => {
    if (!(moduleEl instanceof Element)) return '';
    const moduleKey = (moduleEl.dataset.module || '').toLowerCase();
    if (moduleKey === 'recap') {
      return '';
    }

    const parts = [];

    const textareaEls = moduleEl.querySelectorAll('textarea');
    textareaEls.forEach((textarea) => {
      const value = typeof textarea.value === 'string' ? sanitize(textarea.value) : '';
      if (value) {
        parts.push(value);
      }
    });

    const editableEls = moduleEl.querySelectorAll('[contenteditable="true"]');
    editableEls.forEach((editable) => {
      const value = sanitize(editable.textContent);
      if (value) {
        parts.push(value);
      }
    });

    const clone = moduleEl.cloneNode(true);
    clone.querySelectorAll('button, .btn, [data-topic-module-header-actions], .visually-hidden, script, style').forEach((el) => {
      el.remove();
    });
    const textContent = sanitize(clone.textContent);
    if (textContent) {
      parts.push(textContent);
    }

    if (!parts.length) {
      return '';
    }

    const headingEl = moduleEl.querySelector('h6, h5, h4');
    const heading = sanitize(headingEl ? headingEl.textContent : moduleKey.replace(/[-_]/g, ' '));
    if (heading) {
      return `## ${heading}\n${parts.join('\n\n')}`;
    }
    return parts.join('\n\n');
  };

  const collectTopicContext = () => {
    const sections = [];
    const titleEl = document.getElementById('topicTitleInput');
    const title = sanitize(titleEl ? titleEl.textContent : '');
    if (title) {
      sections.push(`# ${title}`);
    }

    const layout = document.querySelector('[data-topic-layout]');
    if (!layout) {
      return sections.join('\n\n');
    }

    const moduleSections = [];
    layout.querySelectorAll('.topic-module-wrapper').forEach((moduleEl) => {
      const text = collectModuleText(moduleEl);
      if (text) {
        moduleSections.push(text);
      }
    });

    if (moduleSections.length) {
      sections.push(moduleSections.join('\n\n'));
    }

    return sections.join('\n\n').trim();
  };

  const renderMarkdownLite = (md) => {
    if (!md) return '';
    let html = md.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html
      .split(/\n{2,}/)
      .map(p => `<p class="mb-2">${p.replace(/\n/g, '<br>')}</p>`)
      .join('');
    return html;
  };

  setupTopicHistory({
    key: 'recap',
    field: 'recap',
    listUrl: (uuid) => `/api/topics/recap/${uuid}/list`,
    createUrl: '/api/topics/recap/create',
    deleteUrl: (id) => `/api/topics/recap/${id}`,
    renderItem: (item, el) => { if (el) el.innerHTML = renderMarkdownLite(item.recap || ''); },
    parseInput: (text) => ({ recap: text }),
    autoSave: {
      enabled: true,
      inactivityMs: 5000,
      statusContainerId: 'recapSaveStatus',
      statusTextId: 'recapSaveStatusText',
      statusSpinnerId: 'recapSaveStatusSpinner',
    },
    buildSuggestionPayload: ({ topicUuid }) => {
      const payload = { topic_uuid: topicUuid };
      const context = collectTopicContext();
      if (context) {
        payload.context = context;
      }
      return payload;
    },
    controller,
    useMarkdown: true,
    messages: {
      suggestionError: 'Unable to fetch recap suggestions. Please try again.',
      updateError: 'Unable to update the recap. Please try again.',
      deleteConfirm: 'Are you sure you want to delete this recap?',
    },
  });
});
