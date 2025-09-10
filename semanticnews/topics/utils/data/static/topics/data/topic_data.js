document.addEventListener('DOMContentLoaded', () => {
  const fetchBtn = document.getElementById('fetchDataBtn');
  const form = document.getElementById('dataForm');
  const urlInput = document.getElementById('dataUrl');
  const preview = document.getElementById('dataPreview');
  const nameInput = document.getElementById('dataName');
  const nameWrapper = document.getElementById('dataNameWrapper');
  const analyzeBtn = document.getElementById('analyzeDataBtn');
  const analyzeForm = document.getElementById('dataAnalyzeForm');
  const insightsContainer = document.getElementById('dataInsights');
  const saveInsightsBtn = document.getElementById('saveInsightsBtn');
  let fetchedData = null;

  if (fetchBtn && urlInput) {
    fetchBtn.addEventListener('click', async () => {
      fetchBtn.disabled = true;
      const topicUuid = form.querySelector('input[name="topic_uuid"]').value;
      try {
        const res = await fetch('/api/topics/data/fetch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid, url: urlInput.value })
        });
        if (!res.ok) throw new Error('Request failed');
        fetchedData = await res.json();
        if (nameInput) {
          nameInput.value = fetchedData.name || '';
          if (nameWrapper) nameWrapper.classList.remove('d-none');
        }
        let html = '<table class="table table-sm"><thead><tr>';
        fetchedData.headers.forEach(h => { html += `<th>${h}</th>`; });
        html += '</tr></thead><tbody>';
        fetchedData.rows.forEach(row => {
          html += '<tr>' + row.map(c => `<td>${c}</td>`).join('') + '</tr>';
        });
        html += '</tbody></table>';
        preview.innerHTML = html;
      } catch (err) {
        console.error(err);
      } finally {
        fetchBtn.disabled = false;
      }
    });
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!fetchedData) return;
      const topicUuid = form.querySelector('input[name="topic_uuid"]').value;
      const url = urlInput.value;
      const res = await fetch('/api/topics/data/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic_uuid: topicUuid,
          url,
          name: nameInput ? nameInput.value : null,
          headers: fetchedData.headers,
          rows: fetchedData.rows
        })
      });
      if (res.ok) {
        window.location.reload();
      }
    });
  }

  if (analyzeBtn && analyzeForm) {
    analyzeBtn.addEventListener('click', async () => {
      analyzeBtn.disabled = true;
      const topicUuid = analyzeForm.querySelector('input[name="topic_uuid"]').value;
      const dataIds = Array.from(analyzeForm.querySelectorAll('input[name="data_ids"]:checked')).map(cb => parseInt(cb.value));
      try {
        const res = await fetch('/api/topics/data/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid, data_ids: dataIds })
        });
        if (!res.ok) throw new Error('Request failed');
        const data = await res.json();
        insightsContainer.innerHTML = data.insights.map((insight, idx) => {
          return `<div class="form-check">
            <input class="form-check-input" type="checkbox" id="insight${idx}" value="${insight.replace(/"/g, '&quot;')}" checked>
            <label class="form-check-label" for="insight${idx}">${insight}</label>
          </div>`;
        }).join('');
        insightsContainer.classList.remove('d-none');
        if (saveInsightsBtn) saveInsightsBtn.disabled = false;
      } catch (err) {
        console.error(err);
      } finally {
        analyzeBtn.disabled = false;
      }
    });
  }

  if (analyzeForm) {
    analyzeForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const selected = Array.from(insightsContainer.querySelectorAll('input:checked')).map(cb => cb.value);
      if (selected.length === 0) return;
      const topicUuid = analyzeForm.querySelector('input[name="topic_uuid"]').value;
      const res = await fetch('/api/topics/data/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_uuid: topicUuid, insights: selected })
      });
      if (res.ok) {
        window.location.reload();
      }
    });
  }
});
