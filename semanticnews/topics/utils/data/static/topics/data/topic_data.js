document.addEventListener('DOMContentLoaded', () => {
  const fetchBtn = document.getElementById('fetchDataBtn');
  const form = document.getElementById('dataForm');
  const urlInput = document.getElementById('dataUrl');
  const descriptionInput = document.getElementById('dataDescription');
  const urlWrapper = document.getElementById('dataUrlWrapper');
  const descriptionWrapper = document.getElementById('dataDescriptionWrapper');
  const modeRadios = document.querySelectorAll('input[name="data_mode"]');
  const preview = document.getElementById('dataPreview');
  const sourcesWrapper = document.getElementById('dataSourcesWrapper');
  const sourcesList = document.getElementById('dataSources');
  const explanationEl = document.getElementById('dataExplanation');
  const nameInput = document.getElementById('dataName');
  const nameWrapper = document.getElementById('dataNameWrapper');
  const analyzeBtn = document.getElementById('analyzeDataBtn');
  const analyzeForm = document.getElementById('dataAnalyzeForm');
  const insightsContainer = document.getElementById('dataInsights');
  const saveInsightsBtn = document.getElementById('saveInsightsBtn');
  const visualizeBtn = document.getElementById('visualizeDataBtn');
  const visualizeForm = document.getElementById('dataVisualizeForm');
  const visualizeOtherInput = document.getElementById('visualizeInsightOtherText');
  const chartTypeSelect = document.getElementById('visualizeChartType');
  let fetchedData = null;

  modeRadios.forEach((radio) => {
    radio.addEventListener('change', () => {
      if (radio.value === 'url' && radio.checked) {
        if (urlWrapper) urlWrapper.classList.remove('d-none');
        if (descriptionWrapper) descriptionWrapper.classList.add('d-none');
      } else if (radio.value === 'search' && radio.checked) {
        if (descriptionWrapper) descriptionWrapper.classList.remove('d-none');
        if (urlWrapper) urlWrapper.classList.add('d-none');
      }
    });
  });

  if (fetchBtn) {
    fetchBtn.addEventListener('click', async () => {
      fetchBtn.disabled = true;
      const topicUuid = form.querySelector('input[name="topic_uuid"]').value;
      const modeEl = document.querySelector('input[name="data_mode"]:checked');
      const mode = modeEl ? modeEl.value : 'url';
      const body = { topic_uuid: topicUuid };
      let endpoint = '/api/topics/data/fetch';
      if (mode === 'url') {
        if (!urlInput || !urlInput.value) {
          fetchBtn.disabled = false;
          return;
        }
        body.url = urlInput.value;
      } else {
        endpoint = '/api/topics/data/search';
        const description = descriptionInput ? descriptionInput.value.trim() : '';
        if (!description) {
          fetchBtn.disabled = false;
          return;
        }
        body.description = description;
      }
      try {
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        if (!res.ok) throw new Error('Request failed');
        fetchedData = await res.json();
        fetchedData.url = mode === 'url'
          ? (urlInput ? urlInput.value : '')
          : (fetchedData.sources && fetchedData.sources.length > 0 ? fetchedData.sources[0] : '');
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
        if (mode === 'search') {
          if (sourcesWrapper && sourcesList) {
            if (fetchedData.sources && fetchedData.sources.length > 0) {
              sourcesList.innerHTML = fetchedData.sources.map(src => `<li><a href="${src}" target="_blank">${src}</a></li>`).join('');
              sourcesWrapper.classList.remove('d-none');
            } else {
              sourcesList.innerHTML = '';
              sourcesWrapper.classList.add('d-none');
            }
          }
          if (explanationEl) {
            if (fetchedData.explanation) {
              explanationEl.textContent = fetchedData.explanation;
              explanationEl.classList.remove('d-none');
            } else {
              explanationEl.classList.add('d-none');
              explanationEl.textContent = '';
            }
          }
        } else {
          if (sourcesWrapper) sourcesWrapper.classList.add('d-none');
          if (sourcesList) sourcesList.innerHTML = '';
          if (explanationEl) {
            explanationEl.classList.add('d-none');
            explanationEl.textContent = '';
          }
        }
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
      const url = fetchedData.url || (urlInput ? urlInput.value : '');
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

  if (visualizeForm && visualizeOtherInput) {
    const insightRadios = visualizeForm.querySelectorAll('input[name="insight_id"]');
    insightRadios.forEach((radio) => {
      radio.addEventListener('change', () => {
        const selected = visualizeForm.querySelector('input[name="insight_id"]:checked');
        if (selected && selected.value === 'other') {
          visualizeOtherInput.classList.remove('d-none');
          visualizeOtherInput.focus();
        } else {
          visualizeOtherInput.classList.add('d-none');
          visualizeOtherInput.value = '';
        }
      });
    });
  }

  if (visualizeBtn && visualizeForm) {
    visualizeBtn.addEventListener('click', async () => {
      visualizeBtn.disabled = true;
      const topicUuid = visualizeForm.querySelector('input[name="topic_uuid"]').value;
      const insightInput = visualizeForm.querySelector('input[name="insight_id"]:checked');
      if (!insightInput) {
        visualizeBtn.disabled = false;
        return;
      }
      const value = insightInput.value;
      let body;
      if (value === 'other') {
        const insight = visualizeOtherInput ? visualizeOtherInput.value.trim() : '';
        if (!insight) {
          visualizeBtn.disabled = false;
          return;
        }
        body = { topic_uuid: topicUuid, insight };
      } else {
        const insightId = parseInt(value);
        body = { topic_uuid: topicUuid, insight_id: insightId };
      }
      const chartType = chartTypeSelect ? chartTypeSelect.value : '';
      if (chartType) {
        body.chart_type = chartType;
      }
      try {
        const res = await fetch('/api/topics/data/visualize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
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
