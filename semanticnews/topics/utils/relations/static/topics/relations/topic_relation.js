document.addEventListener('DOMContentLoaded', () => {
  const controller = setupGenerationButton({
    buttonId: 'relationButton',
    spinnerId: 'relationSpinner',
    errorIconId: 'relationErrorIcon',
    successIconId: 'relationSuccessIcon',
  });

  setupTopicHistory({
    key: 'relation',
    field: 'relations',
    cardSuffix: 'Graph',
    listUrl: (uuid) => `/api/topics/relation/${uuid}/list`,
    createUrl: '/api/topics/relation/extract',
    deleteUrl: (id) => `/api/topics/relation/${id}`,
    renderItem: (item, el) => { if (el) renderRelationGraph(el, item.relations || []); },
    parseInput: (text) => {
      try {
        return { relations: JSON.parse(text || '[]') };
      } catch (e) {
        throw new Error('Invalid JSON');
      }
    },
    controller,
    messages: {
      suggestionError: 'Unable to fetch relation suggestions. Please try again.',
      updateError: 'Unable to save the relations. Please try again.',
      parseError: 'Enter valid JSON before saving your relations.',
    },
  });
});
