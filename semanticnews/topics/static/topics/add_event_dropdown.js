// Handles adding events to topics from the dropdown menu

document.addEventListener('click', async function (e) {
  const link = e.target.closest('.add-to-topic');
  if (!link) return;
  e.preventDefault();
  const topicUuid = link.getAttribute('data-topic-uuid');
  const eventUuid = link.getAttribute('data-event-uuid');
  try {
    const res = await fetch('/api/topics/add-event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic_uuid: topicUuid, event_uuid: eventUuid })
    });
    if (!res.ok) throw new Error('Request failed');
    const data = await res.json();
    const currentTopic = document.querySelector('[data-topic-uuid]');
    if (currentTopic && currentTopic.dataset.topicUuid === data.topic_uuid) {
      window.location.reload();
    }
  } catch (err) {
    console.error(err);
  }
});
