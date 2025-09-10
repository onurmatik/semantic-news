document.addEventListener('DOMContentLoaded', () => {
  const controller = setupGenerationButton({
    buttonId: 'relationButton',
    spinnerId: 'relationSpinner',
    errorId: 'relationError',
  });

  const form = document.getElementById('relationForm');
  const suggestionBtn = document.getElementById('fetchRelationSuggestion');
  const relationTextarea = document.getElementById('relationText');

  if (suggestionBtn && relationTextarea && form) {
    suggestionBtn.addEventListener('click', async () => {
      suggestionBtn.disabled = true;
      const topicUuid = form.querySelector('input[name="topic_uuid"]').value;
      try {
        const res = await fetch('/api/topics/relation/extract', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid })
        });
        if (!res.ok) throw new Error('Request failed');
        const data = await res.json();
        relationTextarea.value = JSON.stringify(data.relations, null, 2);
      } catch (err) {
        console.error(err);
      } finally {
        suggestionBtn.disabled = false;
      }
    });
  }

  if (form && relationTextarea) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      let relations;
      try {
        relations = JSON.parse(relationTextarea.value || '[]');
      } catch (err) {
        alert('Invalid JSON');
        return;
      }
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      controller.showLoading();
      const relationModal = document.getElementById('relationModal');
      if (relationModal && window.bootstrap) {
        const modal = window.bootstrap.Modal.getInstance(relationModal);
        if (modal) modal.hide();
      }
      const topicUuid = form.querySelector('input[name="topic_uuid"]').value;
      try {
        const res = await fetch('/api/topics/relation/extract', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid, relations })
        });
        if (!res.ok) throw new Error('Request failed');
        await res.json();
        window.location.reload();
      } catch (err) {
        console.error(err);
        submitBtn.disabled = false;
        controller.hideLoading();
      }
    });
  }
});

