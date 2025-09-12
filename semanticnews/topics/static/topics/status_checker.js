document.addEventListener('DOMContentLoaded', () => {
  const container = document.querySelector('[data-topic-uuid]');
  if (!container) return;
  const topicUuid = container.getAttribute('data-topic-uuid');

  const KEYS_TO_CHECK = ['recap'];

  const mapping = {
    recap: 'recapButton',
    narrative: 'narrativeButton',
    relation: 'relationButton',
  };

  const INPROGRESS_TIMEOUT_MS = 5 * 60 * 1000;

  const fetchStatus = async () => {
    try {
      const res = await fetch(`/api/topics/${topicUuid}/generation-status`);
      if (!res.ok) return;

      const data = await res.json();
      let anyStillInProgress = false;

      const currentTime = data.current ? new Date(data.current) : new Date();

      KEYS_TO_CHECK.forEach((key) => {
        const info = data[key];
        const controller = window.generationControllers[mapping[key]];
        if (!info || !controller) return;

        // Only care about in_progress; ignore finished/error
        if (info.status !== 'in_progress') return;

        if (info.created_at) {
          const createdAt = new Date(info.created_at);
          const age = currentTime - createdAt;

          if (age > INPROGRESS_TIMEOUT_MS) {
            // Too old — neutralize and stop tracking
            // TODO change status to error in db
            controller.setState({ status: 'finished' }); // neutral/stateless in button code
            return;
          }
        }

        // Still in progress and within timeout window -> keep spinner on
        controller.setState({ status: 'in_progress' });
        anyStillInProgress = true;
      });

      if (!anyStillInProgress) {
        clearInterval(intervalId);
      }
    } catch (err) {
      console.error(err);
    }
  };

  fetchStatus();
  const intervalId = setInterval(fetchStatus, 3000);
});
