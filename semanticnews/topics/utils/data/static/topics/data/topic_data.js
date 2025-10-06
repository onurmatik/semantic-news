document.addEventListener('DOMContentLoaded', () => {
  const fetchBtn = document.getElementById('fetchDataBtn');
  const form = document.getElementById('dataForm');
  const urlInput = document.getElementById('dataUrl');
  const descriptionInput = document.getElementById('dataDescription');
  const preview = document.getElementById('dataPreview');
  const sourcesWrapper = document.getElementById('dataSourcesWrapper');
  const sourcesList = document.getElementById('dataSources');
  const explanationEl = document.getElementById('dataExplanation');
  const statusMessage = document.getElementById('dataStatusMessage');
  const nameInput = document.getElementById('dataName');
  const nameWrapper = document.getElementById('dataNameWrapper');
  const saveButton = document.getElementById('dataSaveButton');
  const dataModal = document.getElementById('dataModal');
  const dataButtonController = typeof window.setupGenerationButton === 'function'
    ? window.setupGenerationButton({
        buttonId: 'dataButton',
        spinnerId: 'dataSpinner',
        errorIconId: 'dataErrorIcon',
        successIconId: 'dataSuccessIcon',
      })
    : null;
  const analyzeBtn = document.getElementById('analyzeDataBtn');
  const analyzeForm = document.getElementById('dataAnalyzeForm');
  const insightsContainer = document.getElementById('dataInsights');
  const saveInsightsBtn = document.getElementById('saveInsightsBtn');
  const visualizeBtn = document.getElementById('visualizeDataBtn');
  const visualizeForm = document.getElementById('dataVisualizeForm');
  const visualizeOtherInput = document.getElementById('visualizeInsightOtherText');
  const chartTypeSelect = document.getElementById('visualizeChartType');
  const visualizeInstructionsInput = document.getElementById('visualizeInstructions');
  const urlMode = document.getElementById('dataModeUrl');
  const searchMode = document.getElementById('dataModeSearch');
  let fetchedData = null;
  let pollTimer = null;
  let currentTaskId = null;
  let currentRequestId = null;

  const topicUuid = form
    ? form.querySelector('input[name="topic_uuid"]').value
    : null;
  const storageKey = topicUuid ? `topicDataTask:${topicUuid}` : null;

  const normalizeResult = (result) => {
    if (!result || typeof result !== 'object') {
      return null;
    }

    const normalizeString = (value) => {
      if (typeof value === 'string') {
        return value;
      }
      if (value === null || value === undefined) {
        return '';
      }
      return String(value);
    };

    const headers = Array.isArray(result.headers)
      ? result.headers.map(normalizeString)
      : [];

    const rows = Array.isArray(result.rows)
      ? result.rows
          .filter((row) => Array.isArray(row))
          .map((row) => row.map(normalizeString))
      : [];

    let sources = [];
    if (Array.isArray(result.sources)) {
      sources = result.sources
        .filter((value) => typeof value === 'string' && value.trim() !== '')
        .map(normalizeString);
    }
    if (sources.length === 0 && typeof result.source === 'string' && result.source.trim() !== '') {
      sources = [normalizeString(result.source)];
    }
    const primarySource = sources.length > 0 ? sources[0] : null;

    const explanation = result.explanation
      ? normalizeString(result.explanation)
      : null;

    const name = result.name ? normalizeString(result.name) : '';

    const url = result.url ? normalizeString(result.url) : primarySource;

    return {
      headers,
      rows,
      sources,
      source: primarySource,
      explanation,
      name,
      url,
    };
  };

  const loadStoredState = () => {
    if (!storageKey) return null;
    try {
      const raw = localStorage.getItem(storageKey);
      return raw ? JSON.parse(raw) : null;
    } catch (err) {
      console.error(err);
      return null;
    }
  };

  const saveStoredState = (state) => {
    if (!storageKey) return;
    try {
      localStorage.setItem(storageKey, JSON.stringify(state));
    } catch (err) {
      console.error(err);
    }
  };

  const clearStoredState = () => {
    if (!storageKey) return;
    localStorage.removeItem(storageKey);
    currentRequestId = null;
  };

  const registerVisualizationRemoveButton = (button) => {
    if (!button || button.dataset.visualizationRemoveInitialized === 'true') return;
    button.dataset.visualizationRemoveInitialized = 'true';

    button.addEventListener('click', async () => {
      const visualizationId = button.dataset.visualizationId;
      if (!visualizationId) return;

      const message = button.dataset.confirmMessage;
      if (message && !window.confirm(message)) {
        return;
      }

      button.disabled = true;
      try {
        const res = await fetch(`/api/topics/data/visualization/${visualizationId}`, {
          method: 'DELETE',
        });
        if (!res.ok) {
          throw new Error('Request failed');
        }
        window.location.reload();
      } catch (err) {
        console.error(err);
        button.disabled = false;
      }
    });
  };
  };

  const updateSaveButtonState = () => {
    if (!saveButton) return;
    const hasData = fetchedData && Array.isArray(fetchedData.headers) && fetchedData.headers.length > 0;
    saveButton.disabled = !hasData;
  };

  const hideStatusMessage = () => {
    if (!statusMessage) return;
    statusMessage.classList.add('d-none');
    statusMessage.classList.remove('alert-info', 'alert-success', 'alert-danger');
    statusMessage.textContent = '';
  };

  const setStatusMessage = (type, message) => {
    if (!statusMessage) return;
    statusMessage.classList.remove('d-none', 'alert-info', 'alert-success', 'alert-danger');
    const className = type === 'success'
      ? 'alert-success'
      : type === 'error'
        ? 'alert-danger'
        : 'alert-info';
    statusMessage.classList.add(className);
    statusMessage.textContent = message;
  };

  const resetPreview = () => {
    if (preview) preview.innerHTML = '';
    if (sourcesWrapper) sourcesWrapper.classList.add('d-none');
    if (sourcesList) sourcesList.innerHTML = '';
    if (explanationEl) {
      explanationEl.classList.add('d-none');
      explanationEl.textContent = '';
    }
    if (nameWrapper) nameWrapper.classList.add('d-none');
    if (nameInput) nameInput.value = '';
  };

  const renderPreview = (data) => {
    if (!preview) return;
    if (!data || !Array.isArray(data.headers) || data.headers.length === 0) {
      preview.innerHTML = '<p class="text-muted mb-0">No data available.</p>';
      return;
    }
    let html = '<table class="table table-sm"><thead><tr>';
    data.headers.forEach((h) => {
      html += `<th>${h}</th>`;
    });
    html += '</tr></thead><tbody>';
    (data.rows || []).forEach((row) => {
      html += '<tr>' + row.map((c) => `<td>${c}</td>`).join('') + '</tr>';
    });
    html += '</tbody></table>';
    preview.innerHTML = html;
  };

  const applyResult = (result, mode) => {
    const normalized = normalizeResult(result);
    if (!normalized) return;

    const hasSources = Array.isArray(normalized.sources) && normalized.sources.length > 0;
    const effectiveMode = mode || (hasSources && !normalized.url ? 'search' : 'url');
    const urlValue = normalized.url || (effectiveMode === 'url'
      ? (urlInput ? urlInput.value : '')
      : (hasSources ? normalized.sources[0] : ''));

    fetchedData = {
      headers: normalized.headers,
      rows: normalized.rows,
      name: normalized.name,
      sources: hasSources ? normalized.sources : [],
      explanation: normalized.explanation,
      url: urlValue,
      mode: effectiveMode,
    };

    if (nameInput) {
      nameInput.value = fetchedData.name || '';
      if (nameWrapper) {
        nameWrapper.classList.remove('d-none');
      }
    }

    renderPreview(fetchedData);

    if (sourcesWrapper && sourcesList) {
      if (Array.isArray(fetchedData.sources) && fetchedData.sources.length > 0) {
        sourcesList.innerHTML = fetchedData.sources
          .map((src) => `<li><a href="${src}" target="_blank" rel="noreferrer">${src}</a></li>`)
          .join('');
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

    updateSaveButtonState();
  };

  const stopPolling = () => {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  };

  const handleStatusPayload = (payload) => {
    if (!payload) return 'none';
    const taskId = payload.task_id || currentTaskId;
    const requestId = payload.request_id || currentRequestId;
    const isSaved = Boolean(payload.saved);

    if (isSaved) {
      clearStoredState();
      currentTaskId = null;
      currentRequestId = null;
      fetchedData = null;
      resetPreview();
      hideStatusMessage();
      updateSaveButtonState();
      stopPolling();
      return 'saved';
    }

    if (!taskId) return 'none';
    currentTaskId = taskId;
    currentRequestId = requestId || null;
    const status = payload.status;
    const normalizedResult = normalizeResult(payload.result);
    const hasSources = normalizedResult && Array.isArray(normalizedResult.sources) && normalizedResult.sources.length > 0;
    const mode = payload.mode || (hasSources ? 'search' : 'url');

    if (status === 'pending' || status === 'started') {
      setStatusMessage('info', 'We started gathering your data. You can close this modal while we work.');
      if (dataButtonController && dataButtonController.showLoading) {
        dataButtonController.showLoading();
      }
      fetchedData = null;
      updateSaveButtonState();
      saveStoredState({ taskId, status, mode, requestId: currentRequestId, saved: false });
      return 'pending';
    }

    if (status === 'success') {
      if (normalizedResult) {
        applyResult(normalizedResult, mode);
      }
      setStatusMessage('success', 'Your data is ready. Review the preview and click Save to add it to the topic.');
      if (dataButtonController && dataButtonController.showSuccess) {
        dataButtonController.showSuccess();
      }
      stopPolling();
      saveStoredState({
        taskId,
        status: 'success',
        mode,
        result: normalizedResult || null,
        requestId: currentRequestId,
        saved: false,
      });
      return 'success';
    }

    if (status === 'failure') {
      const message = payload.error || 'We were unable to fetch data. Please try again.';
      setStatusMessage('error', message);
      if (dataButtonController && dataButtonController.showError) {
        dataButtonController.showError();
      }
      fetchedData = null;
      updateSaveButtonState();
      stopPolling();
      saveStoredState({
        taskId,
        status: 'failure',
        mode,
        error: message,
        requestId: currentRequestId,
        saved: false,
      });
      return 'failure';
    }

    return 'none';
  };

  const fetchRequestStatus = async (silent = false) => {
    if (!topicUuid) return null;
    const params = new URLSearchParams({ topic_uuid: topicUuid });
    if (currentTaskId) {
      params.set('task_id', currentTaskId);
    }
    if (currentRequestId) {
      params.set('request_id', currentRequestId);
    }

    try {
      const res = await fetch(`/api/topics/data/status?${params.toString()}`);
      if (res.status === 404) {
        if (!silent) {
          fetchedData = null;
          resetPreview();
          hideStatusMessage();
          updateSaveButtonState();
          if (dataButtonController && dataButtonController.reset) {
            dataButtonController.reset();
          }
        }
        clearStoredState();
        currentTaskId = null;
        currentRequestId = null;
        stopPolling();
        return null;
      }
      if (!res.ok) throw new Error('Request failed');
      return await res.json();
    } catch (err) {
      console.error(err);
      if (!silent) {
        setStatusMessage('error', 'Unable to check data status.');
      }
      return null;
    }
  };

  const startPolling = () => {
    if (!currentTaskId) return;
    stopPolling();
    pollTimer = setInterval(async () => {
      if (!currentTaskId) {
        stopPolling();
        return;
      }
      const data = await fetchRequestStatus(true);
      if (!data) return;
      const outcome = handleStatusPayload(data);
      if (outcome === 'success' || outcome === 'failure' || outcome === 'saved') {
        stopPolling();
      }
    }, 3000);
  };

  if (urlInput && urlMode) {
    urlInput.addEventListener('focus', () => {
      urlMode.checked = true;
    });
  }

  if (descriptionInput && searchMode) {
    descriptionInput.addEventListener('focus', () => {
      searchMode.checked = true;
    });
  }

  if (fetchBtn && form) {
    fetchBtn.addEventListener('click', async () => {
      fetchBtn.disabled = true;
      fetchedData = null;
      updateSaveButtonState();
      resetPreview();
      hideStatusMessage();
      stopPolling();
      currentTaskId = null;
      currentRequestId = null;
      clearStoredState();
      if (dataButtonController && dataButtonController.reset) {
        dataButtonController.reset();
      }

      if (!topicUuid) {
        fetchBtn.disabled = false;
        return;
      }

      const modeEl = document.querySelector('input[name="data_mode"]:checked');
      const mode = modeEl ? modeEl.value : 'url';
      const body = { topic_uuid: topicUuid };
      let endpoint = '/api/topics/data/fetch';

      if (mode === 'url') {
        const urlValue = urlInput ? urlInput.value.trim() : '';
        if (!urlValue) {
          fetchBtn.disabled = false;
          return;
        }
        body.url = urlValue;
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
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error('Request failed');
        const data = await res.json();
        const outcome = handleStatusPayload(data);
        if (outcome === 'pending') {
          startPolling();
        }
      } catch (err) {
        console.error(err);
        setStatusMessage('error', 'Unable to start the data request. Please try again.');
        if (dataButtonController && dataButtonController.showError) {
          dataButtonController.showError();
        }
      } finally {
        fetchBtn.disabled = false;
      }
    });
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!fetchedData) return;
      const url = fetchedData.url || (urlInput ? urlInput.value : '');
      const sources = Array.isArray(fetchedData.sources)
        ? Array.from(new Set(fetchedData.sources.filter((src) => typeof src === 'string' && src)))
        : [];
      const body = {
        topic_uuid: topicUuid,
        url,
        name: nameInput ? nameInput.value : null,
        headers: fetchedData.headers,
        rows: fetchedData.rows,
      };
      body.sources = sources;
      if (fetchedData.explanation) {
        body.explanation = fetchedData.explanation;
      }
      if (currentRequestId) {
        body.request_id = currentRequestId;
      }

      const res = await fetch('/api/topics/data/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (res.ok) {
        clearStoredState();
        window.location.reload();
      }
    });
  }

  const loadExistingRequest = async () => {
    const stored = loadStoredState();
    if (stored && stored.taskId) {
      currentTaskId = stored.taskId;
      currentRequestId = stored.requestId || null;
      handleStatusPayload({
        task_id: stored.taskId,
        status: stored.status || 'pending',
        mode: stored.mode || 'url',
        result: stored.result || null,
        error: stored.error || null,
        request_id: stored.requestId || null,
        saved: stored.saved || false,
      });
    }

    const data = await fetchRequestStatus();
    if (!data) {
      if (!stored) {
        resetPreview();
        updateSaveButtonState();
      }
      return;
    }
    const outcome = handleStatusPayload(data);
    if (outcome === 'pending') {
      startPolling();
    }
  };

  if (dataModal) {
    dataModal.addEventListener('show.bs.modal', () => {
      loadExistingRequest();
    });
  }

  updateSaveButtonState();

  // Fetch the latest status on load so the toolbar reflects any queued work.
  loadExistingRequest();


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

  document
    .querySelectorAll('[data-visualization-remove-btn]')
    .forEach((button) => registerVisualizationRemoveButton(button));

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
      if (visualizeInstructionsInput) {
        const instructions = visualizeInstructionsInput.value.trim();
        if (instructions) {
          body.instructions = instructions;
        }
      }
      try {
        const res = await fetch('/api/topics/data/visualize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        if (!res.ok) throw new Error('Request failed');
        await res.json();
        const modalEl = document.getElementById('dataVisualizeModal');
        if (modalEl && window.bootstrap) {
          const modal = window.bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
        }
        if (typeof window.location !== 'undefined') {
          window.location.reload();
        }
      } catch (err) {
        console.error(err);
      } finally {
        visualizeBtn.disabled = false;
      }
    });
  }
});
