document.addEventListener('DOMContentLoaded', () => {
  const container = document.querySelector('[data-topic-uuid]');
  if (!container) return;
  const topicUuid = container.getAttribute('data-topic-uuid');

  const fetchStatus = async () => {
    try {
      const res = await fetch(`/api/topics/${topicUuid}/generation-status`);
      if (!res.ok) return;
      const data = await res.json();
      let allDone = true;
      const mapping = {
        recap: 'recapButton',
        narrative: 'narrativeButton',
        relation: 'relationButton',
      };
      Object.keys(mapping).forEach((key) => {
        const info = data[key];
        const controller = window.generationControllers[mapping[key]];
        if (info && controller) {
          controller.setState({ status: info.status, error: info.error_message });
          if (info.status === 'in_progress') {
            allDone = false;
          }
        }
      });
      if (allDone) {
        clearInterval(intervalId);
      }
    } catch (err) {
      console.error(err);
    }
  };

  fetchStatus();
  const intervalId = setInterval(fetchStatus, 3000);
});
