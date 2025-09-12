document.addEventListener('DOMContentLoaded', () => {
  const controller = setupGenerationButton({
    buttonId: 'imageButton',
    spinnerId: 'imageSpinner',
    errorIconId: 'imageErrorIcon',
    successIconId: 'imageSuccessIcon',
  });

  const form = document.getElementById('imageForm');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      controller.showLoading();
      const imageModal = document.getElementById('imageModal');
      if (imageModal && window.bootstrap) {
        const modal = window.bootstrap.Modal.getInstance(imageModal);
        if (modal) modal.hide();
      }
      const formData = new FormData(form);
      const payload = {
        topic_uuid: formData.get('topic_uuid'),
        size: formData.get('size'),
        style: formData.get('style'),
      };
      try {
        const res = await fetch('/api/topics/image/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error('Request failed');
        await res.json();
        controller.showSuccess();
        window.location.reload();
      } catch (err) {
        console.error(err);
        submitBtn.disabled = false;
        controller.showError();
      }
    });
  }
});
