// Handles the create topic modal workflow

document.addEventListener('DOMContentLoaded', function () {
  const modalElement = document.getElementById('createTopicModal');
  if (!modalElement) return;
  const modal = new bootstrap.Modal(modalElement);
  const form = document.getElementById('createTopicForm');
  const btn = document.getElementById('addTopicBtn');

  if (btn) {
    btn.addEventListener('click', () => {
      form.reset();
      modal.show();
    });
  }

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    const title = document.getElementById('topicTitle').value;

    const res = await fetch('/api/topics/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title })
    });

    if (res.ok) {
      const data = await res.json();
      if (typeof CURRENT_USERNAME !== 'undefined' && CURRENT_USERNAME) {
        window.location.href = `/@${CURRENT_USERNAME}/${data.slug}/`;
      } else {
        window.location.reload();
      }
    } else {
      alert('Failed to create topic');
    }
  });
});
