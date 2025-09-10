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
  const visualizeBtn = document.getElementById('visualizeDataBtn');
  const visualizeForm = document.getElementById('dataVisualizeForm');
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
      const instructionsEl = analyzeForm.querySelector('textarea[name="instructions"]');
      const instructions = instructionsEl ? instructionsEl.value.trim() : '';
      try {
        const body = { topic_uuid: topicUuid, data_ids: dataIds };
        if (instructions) body.instructions = instructions;
        const res = await fetch('/api/topics/data/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
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
      const dataIds = Array.from(analyzeForm.querySelectorAll('input[name="data_ids"]:checked')).map(cb => parseInt(cb.value));
      const res = await fetch('/api/topics/data/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_uuid: topicUuid, data_ids: dataIds, insights: selected })
      });
      if (res.ok) {
        window.location.reload();
      }
    });
  }

  const initChart = (canvas, type, data) => {
    if (!canvas) return;
    new Chart(canvas.getContext('2d'), { type, data });
  };

  document.querySelectorAll('.data-visualization-chart').forEach((canvas) => {
    const type = canvas.dataset.chartType;
    const data = JSON.parse(canvas.dataset.chart);
    initChart(canvas, type, data);
  });

  if (visualizeBtn && visualizeForm) {
    visualizeBtn.addEventListener('click', async () => {
      visualizeBtn.disabled = true;
      const topicUuid = visualizeForm.querySelector('input[name="topic_uuid"]').value;
      const insightInput = visualizeForm.querySelector('input[name="insight_id"]:checked');
      if (!insightInput) {
        visualizeBtn.disabled = false;
        return;
      }
      const insightId = parseInt(insightInput.value);
      try {
        const res = await fetch('/api/topics/data/visualize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid, insight_id: insightId })
        });
        if (!res.ok) throw new Error('Request failed');
        const data = await res.json();
        const container = document.getElementById('topicDataVisualizationsContainer');
        const cards = document.getElementById('topicDataVisualizationCards');
        if (container && cards) {
          container.style.display = '';
          const div = document.createElement('div');
          div.classList.add('mb-3');
          const textDiv = document.createElement('div');
          textDiv.className = 'mb-1';
          textDiv.textContent = data.insight;
          const canvas = document.createElement('canvas');
          canvas.id = `dataVisualizationChart${data.id}`;
          canvas.className = 'data-visualization-chart';
          canvas.dataset.chartType = data.chart_type;
          canvas.dataset.chart = JSON.stringify(data.chart_data);
          div.appendChild(textDiv);
          div.appendChild(canvas);
          cards.prepend(div);
          initChart(canvas, data.chart_type, data.chart_data);
        }
        const modalEl = document.getElementById('dataVisualizeModal');
        if (modalEl && window.bootstrap) {
          const modal = window.bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
        }
      } catch (err) {
        console.error(err);
      } finally {
        visualizeBtn.disabled = false;
      }
    });
  }
});
