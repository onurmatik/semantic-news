(function () {
  function getCsrfToken() {
    const name = 'csrftoken=';
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (let i = 0; i < cookies.length; i += 1) {
      const cookie = cookies[i].trim();
      if (cookie.startsWith(name)) {
        return decodeURIComponent(cookie.substring(name.length));
      }
    }
    return '';
  }

  function setValidationState(wrapper, message, variant) {
    if (!wrapper) return;
    const classes = ['alert-info', 'alert-success', 'alert-danger', 'alert-warning', 'alert-secondary'];
    wrapper.classList.remove('d-none');
    wrapper.classList.remove(...classes);
    wrapper.classList.add(`alert-${variant || 'info'}`);
    wrapper.textContent = message || '';
  }

  function clearValidation(wrapper) {
    if (!wrapper) return;
    wrapper.classList.add('d-none');
    wrapper.textContent = '';
  }

  function setMessage(textEl, message) {
    if (!textEl) return;
    if (message) {
      textEl.classList.remove('d-none');
      textEl.textContent = message;
    } else {
      textEl.classList.add('d-none');
      textEl.textContent = '';
    }
  }

  window.TopicWidgetShared = {
    getCsrfToken,
    setValidationState,
    clearValidation,
    setMessage,
  };
}());
