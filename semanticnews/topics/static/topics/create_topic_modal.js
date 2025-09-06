// Handles the create topic modal workflow

document.addEventListener('DOMContentLoaded', function () {
  const modalElement = document.getElementById('createTopicModal');
  if (!modalElement) return;
  const modal = new bootstrap.Modal(modalElement);
  const form = document.getElementById('createTopicForm');
  const btn = document.getElementById('addTopicBtn');
  const suggestForm = document.getElementById('suggestTopicsForm');
  const suggestField = document.getElementById('suggestTopicsAbout');
  const fetchBtn = document.getElementById('fetchTopicSuggestions');
  const suggestedList = document.getElementById('suggestedTopicsList');
  const suggestedTitle = document.getElementById('suggestedTopicTitle');
  const createTab = document.getElementById('topic-create-tab');
  const defaultSuggestion = suggestField ? suggestField.value : '';

  if (btn) {
    btn.addEventListener('click', () => {
      if (form) form.reset();
      if (suggestForm) suggestForm.reset();
      if (suggestField) {
        const t = btn.getAttribute('data-event-title') || defaultSuggestion;
        suggestField.value = t;
      }
      if (suggestedList) {
        suggestedList.innerHTML = '';
        suggestedList.classList.add('d-none');
      }
      if (suggestedTitle) suggestedTitle.value = '';
      if (createTab) {
        new bootstrap.Tab(createTab).show();
      }
      modal.show();
    });
  }

  async function createTopic(title) {
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
  }

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    const title = document.getElementById('topicTitle').value;
    await createTopic(title);
  });

  if (suggestForm) {
    suggestForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      const title = suggestedTitle ? suggestedTitle.value : '';
      if (title) {
        await createTopic(title);
      }
    });
  }

  if (fetchBtn && suggestField && suggestedList) {
    fetchBtn.addEventListener('click', async () => {
      suggestedList.innerHTML = '<p>Loading suggestions...</p>';
      suggestedList.classList.remove('d-none');
      try {
        const about = suggestField.value;
        const res = await fetch(`/api/topics/suggest?about=${encodeURIComponent(about)}`);
        const data = await res.json();
        if (Array.isArray(data) && data.length) {
          suggestedList.innerHTML = '';
          data.forEach((title) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'list-group-item list-group-item-action';
            item.textContent = title;
            item.addEventListener('click', () => {
              if (suggestedTitle) suggestedTitle.value = title;
            });
            suggestedList.appendChild(item);
          });
        } else {
          suggestedList.innerHTML = '<p>No suggestions found.</p>';
        }
      } catch (err) {
        suggestedList.innerHTML = '<p>Error loading suggestions.</p>';
      }
    });
  }
});
