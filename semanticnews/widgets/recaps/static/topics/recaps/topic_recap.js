document.addEventListener('DOMContentLoaded', () => {
  const controller = typeof setupGenerationButton === 'function'
    ? setupGenerationButton({
        buttonId: 'recapButton',
        spinnerId: 'recapSpinner',
        errorIconId: 'recapErrorIcon',
        successIconId: 'recapSuccessIcon',
      })
    : null;

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
    buildSuggestionPayload: ({ topicUuid }) => {
      const payload = { topic_uuid: topicUuid };
      const instructionsEl = document.getElementById('recapInstructions');
      if (instructionsEl && typeof instructionsEl.value === 'string') {
        const instructions = instructionsEl.value.trim();
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
      deleteConfirm: 'Are you sure you want to delete this recap?',
    },
  });
});
