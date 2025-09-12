document.addEventListener('DOMContentLoaded', () => {
  const controller = setupGenerationButton({
    buttonId: 'narrativeButton',
    spinnerId: 'narrativeSpinner',
    errorIconId: 'narrativeErrorIcon',
    successIconId: 'narrativeSuccessIcon',
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
    key: 'narrative',
    field: 'narrative',
    listUrl: (uuid) => `/api/topics/narrative/${uuid}/list`,
    createUrl: '/api/topics/narrative/create',
    deleteUrl: (id) => `/api/topics/narrative/${id}`,
    renderItem: (item, el) => { if (el) el.innerHTML = renderMarkdownLite(item.narrative || ''); },
    parseInput: (text) => ({ narrative: text }),
    controller,
  });
});
