window.generationControllers = window.generationControllers || {};

function setupGenerationButton({ buttonId, spinnerId, errorId }) {
  const button = document.getElementById(buttonId);
  const spinner = document.getElementById(spinnerId);
  const errorEl = errorId ? document.getElementById(errorId) : null;

  const setState = ({ status, error }) => {
    if (!button) return;
    if (status === 'in_progress') {
      button.disabled = true;
      if (spinner) spinner.classList.remove('d-none');
      if (errorEl) {
        errorEl.classList.add('d-none');
        errorEl.textContent = '';
      }
    } else if (status === 'error') {
      button.disabled = false;
      if (spinner) spinner.classList.add('d-none');
      if (errorEl) {
        errorEl.textContent = error || 'Error';
        errorEl.classList.remove('d-none');
      }
    } else {
      button.disabled = false;
      if (spinner) spinner.classList.add('d-none');
      if (errorEl) {
        errorEl.classList.add('d-none');
        errorEl.textContent = '';
      }
    }
  };

  if (button) {
    setState({
      status: button.dataset.status,
      error: button.dataset.error,
    });
  }

  const controller = {
    setState,
    showLoading: () => setState({ status: 'in_progress' }),
    hideLoading: () => setState({ status: 'finished' }),
  };

  if (button) {
    window.generationControllers[buttonId] = controller;
  }

  return controller;
}

window.setupGenerationButton = setupGenerationButton;
