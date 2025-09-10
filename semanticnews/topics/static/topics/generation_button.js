window.generationControllers = window.generationControllers || {};

function setupGenerationButton({ buttonId, spinnerId, errorIconId }) {
  const button = document.getElementById(buttonId);
  const spinner = document.getElementById(spinnerId);
  const errorIcon = errorIconId ? document.getElementById(errorIconId) : null;

  const setState = ({ status }) => {
    if (!button) return;
    if (status === 'in_progress') {
      button.disabled = true;
      if (spinner) spinner.classList.remove('d-none');
      if (errorIcon) errorIcon.classList.add('d-none');
      button.classList.remove('text-danger');
    } else if (status === 'error') {
      button.disabled = false;
      if (spinner) spinner.classList.add('d-none');
      if (errorIcon) errorIcon.classList.remove('d-none');
      button.classList.add('text-danger');
    } else {
      button.disabled = false;
      if (spinner) spinner.classList.add('d-none');
      if (errorIcon) errorIcon.classList.add('d-none');
      button.classList.remove('text-danger');
    }
  };

  if (button) {
    setState({
      status: button.dataset.status,
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
