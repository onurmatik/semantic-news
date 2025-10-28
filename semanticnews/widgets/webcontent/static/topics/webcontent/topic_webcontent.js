function handleModalForm({ formId, modalId, endpoint }) {
  const form = document.getElementById(formId);
  if (!form) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
      submitBtn.disabled = true;
    }

    const modalEl = document.getElementById(modalId);
    if (modalEl && window.bootstrap) {
      const modal = window.bootstrap.Modal.getInstance(modalEl);
      if (modal) {
        modal.hide();
      }
    }

    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      await response.json();
      window.location.reload();
    } catch (error) {
      console.error(error);
      if (submitBtn) {
        submitBtn.disabled = false;
      }
    }
  });
}

function initWebContentForms() {
  const forms = [
    {
      formId: 'topicDocumentForm',
      modalId: 'topicDocumentModal',
      endpoint: '/api/topics/webcontent/document/create',
    },
    {
      formId: 'topicWebpageForm',
      modalId: 'topicWebpageModal',
      endpoint: '/api/topics/webcontent/webpage/create',
    },
    {
      formId: 'youtubeVideoForm',
      modalId: 'youtubeVideoModal',
      endpoint: '/api/topics/webcontent/video/add',
    },
    {
      formId: 'tweetEmbedForm',
      modalId: 'tweetEmbedModal',
      endpoint: '/api/topics/webcontent/tweet/add',
    },
  ];

  forms.forEach(handleModalForm);
}

document.addEventListener('DOMContentLoaded', initWebContentForms);
