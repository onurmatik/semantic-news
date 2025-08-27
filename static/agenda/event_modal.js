// Handles the add event modal workflow

const CONFIDENCE_THRESHOLD = 0.85;

document.addEventListener('DOMContentLoaded', function () {
  const modalElement = document.getElementById('addEventModal');
  if (!modalElement) return;
  const modal = new bootstrap.Modal(modalElement);
  const form = document.getElementById('addEventForm');
  const similarContainer = document.getElementById('similarEvents');

  document.getElementById('addEventBtn').addEventListener('click', () => {
    form.reset();
    similarContainer.innerHTML = '';
    modal.show();
  });

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    const title = document.getElementById('eventTitle').value;
    const date = document.getElementById('eventDate').value;

    const res = await fetch('/api/agenda/get-existing', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, date })
    });

    const data = await res.json();
    if (data.existing) {
      similarContainer.innerHTML = '<p>This event already exists.</p>';
    } else {
      await validateAndCreate(title, date);
    }
  });

  async function validateAndCreate(title, date) {
    const valRes = await fetch('/api/agenda/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, date })
    });
    const valData = await valRes.json();
    const createRes = await fetch('/api/agenda/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, date, confidence: valData.confidence })
    });
    const created = await createRes.json();
    if (valData.confidence < CONFIDENCE_THRESHOLD) {
      alert('Event created as draft due to low confidence.');
    }
    window.location.href = created.url;
  }
});
