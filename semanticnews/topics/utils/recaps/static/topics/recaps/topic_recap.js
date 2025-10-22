document.addEventListener('DOMContentLoaded', () => {
  const controller = setupGenerationButton({
    buttonId: 'recapButton',
    spinnerId: 'recapSpinner',
    errorIconId: 'recapErrorIcon',
    successIconId: 'recapSuccessIcon',
  });

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
    buildSuggestionPayload: ({ topicUuid, getValue }) => {
      const payload = { topic_uuid: topicUuid };
      if (typeof getValue === 'function') {
        const instructions = (getValue() || '').trim();
        if (instructions) {
          payload.instructions = instructions;
        }
      }
      return payload;
    },
    controller,
    useMarkdown: true,
    messages: {
      suggestionError: 'Unable to fetch recap suggestions. Please try again.',
      updateError: 'Unable to update the recap. Please try again.',
    },
  });
});
