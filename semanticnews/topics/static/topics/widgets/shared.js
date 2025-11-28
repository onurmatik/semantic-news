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

    const classes = [
      'alert-info',
      'alert-success',
      'alert-danger',
      'alert-warning',
      'alert-secondary'
    ];

    wrapper.classList.remove('d-none');
    wrapper.classList.remove(...classes);
    wrapper.classList.add(`alert-${variant || 'info'}`);

    // Clear old content
    wrapper.innerHTML = '';

    // Loading spinner for informational states
    if ((variant || '').toLowerCase() === 'info') {
      const spinner = document.createElement('span');
      spinner.className = 'spinner-border spinner-border-sm me-2 align-text-bottom';
      spinner.setAttribute('role', 'status');
      spinner.setAttribute('aria-hidden', 'true');
      wrapper.appendChild(spinner);
    }

    // Add message span
    const textSpan = document.createElement('span');
    textSpan.textContent = message || '';
    wrapper.appendChild(textSpan);

    // Add close button ONLY for success variant
    if ((variant || '').toLowerCase() === 'success') {
      wrapper.classList.add('alert-dismissible');

      const closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.className = 'btn-close ms-2';
      closeBtn.setAttribute('aria-label', 'Close');

      closeBtn.addEventListener('click', () => {
        clearValidation(wrapper);
      });

      wrapper.appendChild(closeBtn);
    }
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
