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
      const currentTime = data.current ? new Date(data.current) : new Date();
      Object.keys(mapping).forEach((key) => {
        const info = data[key];
        const controller = window.generationControllers[mapping[key]];
        if (info && controller) {
          let status = info.status;
          if (status === 'in_progress' && info.created_at) {
            const createdAt = new Date(info.created_at);
            if (currentTime - createdAt > 5 * 60 * 1000) {
              status = 'finished';
            }
          }
          controller.setState({ status, error: info.error_message });
          if (status === 'in_progress') {
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
