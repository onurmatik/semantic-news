document.addEventListener('DOMContentLoaded', () => {
  const controller = setupGenerationButton({
    buttonId: 'imageButton',
    spinnerId: 'imageSpinner',
    errorIconId: 'imageErrorIcon',
    successIconId: 'imageSuccessIcon',
  });

  window.setupTopicHistory({
    key: 'image',
    field: 'image_url',                       // used only for getItemText; safe when no textarea
    listUrl: (uuid) => `/api/topics/image/${uuid}/list`,
    createUrl: '/api/topics/image/create',
    deleteUrl: (id) => `/api/topics/image/${id}`,
    cardSuffix: 'Container',                  // we will render into the whole container’s image
    renderItem: (item) => {
      const img = document.getElementById('topicImageLatest');
      if (img) img.src = item.image_url || item.thumbnail_url || img.src;
    },
    parseInput: () => {
      const styleSel = document.getElementById('imageStyle');
      return { style: styleSel ? styleSel.value : undefined };
    },
    controller,
    useMarkdown: false,
  });

  // Override/extend the exposed hooks for image so status_checker can paint without reload
  window.__imageExternalApply = (imageUrl, thumbUrl, createdAtIso) => {
    const img = document.getElementById('topicImageLatest');
    if (img) img.src = imageUrl || thumbUrl || img.src;
    const card = document.getElementById('topicImageContainer');
    if (card) card.style.display = '';
    const createdAtEl = document.getElementById('imageCreatedAt');
    if (createdAtEl && createdAtIso) {
      const d = new Date(createdAtIso);
      createdAtEl.textContent = d.toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit'
      });
    }
    document.dispatchEvent(new CustomEvent('topic:changed'));
  };
});
