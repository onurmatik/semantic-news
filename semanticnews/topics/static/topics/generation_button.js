window.generationControllers = window.generationControllers || {};

function setupGenerationButton({ buttonId, spinnerId, errorIconId, successIconId }) {
  const button = document.getElementById(buttonId);
  const spinner = document.getElementById(spinnerId);
  const errorIcon = errorIconId ? document.getElementById(errorIconId) : null;
  const successIcon = successIconId ? document.getElementById(successIconId) : null;

  const setState = ({ status }) => {
    if (!button) return;

    // reset common UI
    const hide = el => el && el.classList.add('d-none');
    const show = el => el && el.classList.remove('d-none');

    switch (status) {
      case 'in_progress':
        button.disabled = true;
        show(spinner);
        hide(errorIcon);
        hide(successIcon);
        button.classList.remove('text-danger', 'text-success');
        button.setAttribute('aria-busy', 'true');
        break;

      case 'error':
        button.disabled = false;
        hide(spinner);
        show(errorIcon);
        hide(successIcon);
        button.classList.add('text-danger');
        button.classList.remove('text-success');
        button.removeAttribute('aria-busy');
        break;

      case 'success':
        button.disabled = false;
        hide(spinner);
        hide(errorIcon);
        show(successIcon);
        button.classList.remove('text-danger');
        button.classList.add('text-success');
        button.removeAttribute('aria-busy');
        break;

      // "finished" or anything else => neutral/stateless
      default:
        button.disabled = false;
        hide(spinner);
        hide(errorIcon);
        hide(successIcon);
        button.classList.remove('text-danger', 'text-success');
        button.removeAttribute('aria-busy');
        break;
    }
  };

  if (button) {
    setState({ status: button.dataset.status });
  }

  const controller = {
    setState,
    showLoading: () => setState({ status: 'in_progress' }),
    showError: () => setState({ status: 'error' }),
    showSuccess: () => setState({ status: 'success' }),
    reset: () => setState({ status: 'finished' }) // neutral
  };

  if (button) {
    window.generationControllers[buttonId] = controller;
  }

  return controller;
}

window.setupGenerationButton = setupGenerationButton;
