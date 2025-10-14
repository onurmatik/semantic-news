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
  const analyzeStatusMessage = document.getElementById('analyzeStatusMessage');
  const analyzeRequestInput = document.getElementById('analyzeRequestId');
  const visualizeBtn = document.getElementById('visualizeDataBtn');
  const visualizeForm = document.getElementById('dataVisualizeForm');
  const visualizeOtherInput = document.getElementById('visualizeInsightOtherText');
  const chartTypeSelect = document.getElementById('visualizeChartType');
  const visualizeInstructionsInput = document.getElementById('visualizeInstructions');
  const visualizeStatusMessage = document.getElementById('visualizeStatusMessage');
  const visualizeRequestInput = document.getElementById('visualizeRequestId');
  const visualizePreviewWrapper = document.getElementById('visualizePreviewWrapper');
  const visualizePreviewCanvas = document.getElementById('visualizePreviewChart');
  const saveVisualizationBtn = document.getElementById('saveVisualizationBtn');
  const analyzeModalEl = document.getElementById('dataAnalyzeModal');
  const visualizeModalEl = document.getElementById('dataVisualizeModal');
  const urlMode = document.getElementById('dataModeUrl');
  const searchMode = document.getElementById('dataModeSearch');
  let fetchedData = null;
  let pollTimer = null;
  let currentTaskId = null;
  let currentRequestId = null;
  let analyzePollTimer = null;
  let analyzeRequestId = null;
  let analyzeTaskId = null;
  let visualizePollTimer = null;
  let visualizeRequestId = null;
  let visualizeTaskId = null;
  let visualizeChartInstance = null;

  const topicUuid = form
    ? form.querySelector('input[name="topic_uuid"]').value
    : null;
  const storageKey = topicUuid ? `topicDataTask:${topicUuid}` : null;
  const analyzeStorageKey = topicUuid ? `topicDataAnalyzeTask:${topicUuid}` : null;
  const visualizeStorageKey = topicUuid ? `topicDataVisualizeTask:${topicUuid}` : null;

  const hideVisualizationPreview = () => {
    if (visualizePreviewWrapper) visualizePreviewWrapper.classList.add('d-none');
    if (visualizeChartInstance) {
      visualizeChartInstance.destroy();
      visualizeChartInstance = null;
    }
  };

  const renderVisualizationPreview = (chartType, chartData) => {
    if (!visualizePreviewCanvas || typeof Chart === 'undefined') return;
    try {
      if (visualizeChartInstance) {
        visualizeChartInstance.destroy();
      }
      visualizeChartInstance = new Chart(visualizePreviewCanvas.getContext('2d'), {
        type: chartType || 'bar',
        data: chartData,
        options: {
          responsive: true,
          maintainAspectRatio: false,
        },
      });
      if (visualizePreviewWrapper) visualizePreviewWrapper.classList.remove('d-none');
    } catch (err) {
      console.error(err);
      hideVisualizationPreview();
      showAlert(visualizeStatusMessage, 'error', 'Unable to render the preview.');
    }
  };

  const clearVisualizeState = () => {
    if (visualizeStorageKey) {
      try {
        localStorage.removeItem(visualizeStorageKey);
      } catch (err) {
        console.error(err);
      }
    }
    visualizeRequestId = null;
    visualizeTaskId = null;
    if (visualizeRequestInput) visualizeRequestInput.value = '';
    if (visualizePollTimer) {
      clearInterval(visualizePollTimer);
      visualizePollTimer = null;
    }
  };

  const saveVisualizeState = (payload) => {
    if (!visualizeStorageKey || !payload || typeof payload.request_id !== 'number') return;
    const state = {
      requestId: payload.request_id,
      taskId: payload.task_id || null,
      status: payload.status,
      chartType: payload.chart_type || null,
      chartData: payload.chart_data || null,
      insight: payload.insight || null,
      error: payload.error || null,
      saved: Boolean(payload.saved),
    };
    try {
      localStorage.setItem(visualizeStorageKey, JSON.stringify(state));
    } catch (err) {
      console.error(err);
    }
  };

  const loadVisualizeState = () => {
    if (!visualizeStorageKey) return null;
    try {
      const raw = localStorage.getItem(visualizeStorageKey);
      return raw ? JSON.parse(raw) : null;
    } catch (err) {
      console.error(err);
      return null;
    }
  };

  const fetchVisualizeStatus = async (silent = false) => {
    if (!topicUuid || !visualizeRequestId) return null;
    const params = new URLSearchParams({ topic_uuid: topicUuid, request_id: visualizeRequestId });
    if (visualizeTaskId) params.set('task_id', visualizeTaskId);
    try {
      const res = await fetch(`/api/topics/data/visualize/status?${params.toString()}`);
      if (res.status === 404) {
        if (!silent) resetAlert(visualizeStatusMessage);
        clearVisualizeState();
        hideVisualizationPreview();
        return null;
      }
      if (!res.ok) throw new Error('Request failed');
      return await res.json();
    } catch (err) {
      console.error(err);
      if (!silent) showAlert(visualizeStatusMessage, 'error', 'Unable to check visualization status.');
      return null;
    }
  };

  const handleVisualizationTaskPayload = (payload, { persist = true } = {}) => {
    if (!payload) return 'none';
    if (typeof payload.request_id === 'number') {
      visualizeRequestId = payload.request_id;
      if (visualizeRequestInput) visualizeRequestInput.value = String(payload.request_id);
    }
    if (typeof payload.task_id === 'string') {
      visualizeTaskId = payload.task_id;
    } else if (!payload.task_id) {
      visualizeTaskId = null;
    }
    if (persist) {
      saveVisualizeState(payload);
    }

    const status = payload.status;
    const saved = Boolean(payload.saved);

    if (status === 'pending' || status === 'started') {
      showAlert(visualizeStatusMessage, 'info', 'We started building your visualization. Feel free to close this modal.');
      if (saveVisualizationBtn) saveVisualizationBtn.disabled = true;
      hideVisualizationPreview();
      return 'pending';
    }

    if (status === 'failure') {
      showAlert(visualizeStatusMessage, 'error', payload.error || 'Unable to generate a visualization.');
      if (saveVisualizationBtn) saveVisualizationBtn.disabled = true;
      if (visualizeBtn) visualizeBtn.disabled = false;
      clearVisualizeState();
      return 'failure';
    }

    if (status === 'success') {
      if (visualizeBtn) visualizeBtn.disabled = false;
      if (saved) {
        showAlert(visualizeStatusMessage, 'success', 'Visualization saved to the topic.');
        hideVisualizationPreview();
        if (saveVisualizationBtn) saveVisualizationBtn.disabled = true;
        clearVisualizeState();
        return 'success';
      }
      if (payload.chart_type && payload.chart_data) {
        renderVisualizationPreview(payload.chart_type, payload.chart_data);
        showAlert(visualizeStatusMessage, 'success', 'Review the preview and click Save to add it to the topic.');
        if (saveVisualizationBtn) saveVisualizationBtn.disabled = false;
      } else {
        hideVisualizationPreview();
        showAlert(visualizeStatusMessage, 'info', 'The visualization completed without chart data.');
        if (saveVisualizationBtn) saveVisualizationBtn.disabled = true;
      }
      return 'success';
    }

    return 'none';
  };

  const startVisualizePolling = () => {
    if (visualizePollTimer) {
      clearInterval(visualizePollTimer);
      visualizePollTimer = null;
    }
    if (!visualizeRequestId) return;
    visualizePollTimer = setInterval(async () => {
      if (!visualizeRequestId) {
        if (visualizePollTimer) {
          clearInterval(visualizePollTimer);
          visualizePollTimer = null;
        }
        return;
      }
      const data = await fetchVisualizeStatus(true);
      if (!data) return;
      const outcome = handleVisualizationTaskPayload(data);
      if (outcome === 'success' || outcome === 'failure') {
        if (visualizePollTimer) {
          clearInterval(visualizePollTimer);
          visualizePollTimer = null;
        }
      }
    }, 3000);
  };

  const resumeVisualizeRequest = async () => {
    if (!visualizeForm || !topicUuid) return;
    const stored = loadVisualizeState();
    if (!stored) return;
    if (visualizePollTimer) {
      clearInterval(visualizePollTimer);
      visualizePollTimer = null;
    }
    visualizeRequestId = stored.requestId || null;
    visualizeTaskId = stored.taskId || null;
    if (visualizeRequestInput) visualizeRequestInput.value = visualizeRequestId || '';
    const payload = {
      request_id: stored.requestId,
      task_id: stored.taskId,
      status: stored.status,
      chart_type: stored.chartType,
      chart_data: stored.chartData,
      insight: stored.insight,
      error: stored.error,
      saved: stored.saved,
    };
    const outcome = handleVisualizationTaskPayload(payload, { persist: false });
    if (outcome === 'pending') {
      if (visualizeBtn) visualizeBtn.disabled = true;
      const latest = await fetchVisualizeStatus(true);
      if (latest) {
        const latestOutcome = handleVisualizationTaskPayload(latest);
        if (latestOutcome === 'pending') {
          startVisualizePolling();
        }
      } else {
        startVisualizePolling();
      }
    } else if (outcome === 'success' && !stored.saved && stored.chartType && stored.chartData) {
      renderVisualizationPreview(stored.chartType, stored.chartData);
      if (saveVisualizationBtn) saveVisualizationBtn.disabled = false;
    }
  };


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

  const resetAlert = (element) => {
    if (!element) return;
    element.classList.add('d-none');
    element.classList.remove('alert-info', 'alert-success', 'alert-danger');
    element.textContent = '';
  };

  const showAlert = (element, type, message) => {
    if (!element) return;
    element.classList.remove('d-none', 'alert-info', 'alert-success', 'alert-danger');
    const className = type === 'success'
      ? 'alert-success'
      : type === 'error'
        ? 'alert-danger'
        : 'alert-info';
    element.classList.add(className);
    element.textContent = message;
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


  const updateSaveInsightsState = () => {
    if (!saveInsightsBtn) return;
    if (!insightsContainer) {
      saveInsightsBtn.disabled = true;
      return;
    }
    const hasSelection = insightsContainer.querySelectorAll('input[type="checkbox"]:checked').length > 0;
    saveInsightsBtn.disabled = !hasSelection || !analyzeRequestId;
  };

  const renderInsights = (insights) => {
    if (!insightsContainer) return;
    insightsContainer.innerHTML = '';
    if (!Array.isArray(insights) || insights.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'text-muted mb-0';
      empty.textContent = 'No insights generated.';
      insightsContainer.appendChild(empty);
      insightsContainer.classList.remove('d-none');
      updateSaveInsightsState();
      return;
    }
    insights.forEach((insight, idx) => {
      const wrapper = document.createElement('div');
      wrapper.className = 'form-check';
      const input = document.createElement('input');
      input.className = 'form-check-input';
      input.type = 'checkbox';
      input.id = `insight${idx}`;
      input.checked = true;
      input.value = typeof insight === 'string' ? insight : String(insight ?? '');
      const label = document.createElement('label');
      label.className = 'form-check-label';
      label.htmlFor = input.id;
      label.textContent = input.value;
      wrapper.appendChild(input);
      wrapper.appendChild(label);
      insightsContainer.appendChild(wrapper);
    });
    insightsContainer.classList.remove('d-none');
    updateSaveInsightsState();
  };

  if (insightsContainer) {
    insightsContainer.addEventListener('change', updateSaveInsightsState);
  }

  const clearAnalyzeState = () => {
    if (analyzeStorageKey) {
      try {
        localStorage.removeItem(analyzeStorageKey);
      } catch (err) {
        console.error(err);
      }
    }
    analyzeRequestId = null;
    analyzeTaskId = null;
    if (analyzeRequestInput) analyzeRequestInput.value = '';
    if (analyzePollTimer) {
      clearInterval(analyzePollTimer);
      analyzePollTimer = null;
    }
    updateSaveInsightsState();
  };

  const saveAnalyzeState = (payload) => {
    if (!analyzeStorageKey || !payload || typeof payload.request_id !== 'number') return;
    const state = {
      requestId: payload.request_id,
      taskId: payload.task_id || null,
      status: payload.status,
      insights: payload.insights || [],
      error: payload.error || null,
      saved: Boolean(payload.saved),
    };
    try {
      localStorage.setItem(analyzeStorageKey, JSON.stringify(state));
    } catch (err) {
      console.error(err);
    }
  };

  const loadAnalyzeState = () => {
    if (!analyzeStorageKey) return null;
    try {
      const raw = localStorage.getItem(analyzeStorageKey);
      return raw ? JSON.parse(raw) : null;
    } catch (err) {
      console.error(err);
      return null;
    }
  };

  const fetchAnalyzeStatus = async (silent = false) => {
    if (!topicUuid || !analyzeRequestId) return null;
    const params = new URLSearchParams({ topic_uuid: topicUuid, request_id: analyzeRequestId });
    if (analyzeTaskId) params.set('task_id', analyzeTaskId);
    try {
      const res = await fetch(`/api/topics/data/analyze/status?${params.toString()}`);
      if (res.status === 404) {
        if (!silent) resetAlert(analyzeStatusMessage);
        clearAnalyzeState();
        if (insightsContainer) {
          insightsContainer.classList.add('d-none');
          insightsContainer.innerHTML = '';
        }
        return null;
      }
      if (!res.ok) throw new Error('Request failed');
      return await res.json();
    } catch (err) {
      console.error(err);
      if (!silent) showAlert(analyzeStatusMessage, 'error', 'Unable to check analysis status.');
      return null;
    }
  };

  const handleAnalyzeTaskPayload = (payload, { persist = true } = {}) => {
    if (!payload) return 'none';
    if (typeof payload.request_id === 'number') {
      analyzeRequestId = payload.request_id;
      if (analyzeRequestInput) analyzeRequestInput.value = String(payload.request_id);
    }
    if (typeof payload.task_id === 'string') {
      analyzeTaskId = payload.task_id;
    } else if (!payload.task_id) {
      analyzeTaskId = null;
    }
    if (persist) {
      saveAnalyzeState(payload);
    }

    const status = payload.status;
    const saved = Boolean(payload.saved);

    if (status === 'pending' || status === 'started') {
      showAlert(analyzeStatusMessage, 'info', 'We started analyzing your data. You can close this modal while we work.');
      if (insightsContainer) {
        insightsContainer.classList.add('d-none');
        insightsContainer.innerHTML = '';
      }
      if (saveInsightsBtn) saveInsightsBtn.disabled = true;
      return 'pending';
    }

    if (status === 'failure') {
      showAlert(analyzeStatusMessage, 'error', payload.error || 'Unable to analyze the selected data.');
      if (insightsContainer) {
        insightsContainer.classList.add('d-none');
        insightsContainer.innerHTML = '';
      }
      if (saveInsightsBtn) saveInsightsBtn.disabled = true;
      if (analyzeBtn) analyzeBtn.disabled = false;
      clearAnalyzeState();
      return 'failure';
    }

    if (status === 'success') {
      if (analyzeBtn) analyzeBtn.disabled = false;
      if (saved) {
        showAlert(analyzeStatusMessage, 'success', 'Insights saved to the topic.');
        clearAnalyzeState();
        return 'success';
      }
      if (Array.isArray(payload.insights) && payload.insights.length > 0) {
        renderInsights(payload.insights);
        showAlert(analyzeStatusMessage, 'success', 'Analysis complete. Select the insights you want to keep.');
      } else {
        renderInsights([]);
        showAlert(analyzeStatusMessage, 'info', 'The analysis finished but did not produce insights.');
      }
      return 'success';
    }

    return 'none';
  };

  const startAnalyzePolling = () => {
    if (analyzePollTimer) {
      clearInterval(analyzePollTimer);
      analyzePollTimer = null;
    }
    if (!analyzeRequestId) return;
    analyzePollTimer = setInterval(async () => {
      if (!analyzeRequestId) {
        if (analyzePollTimer) {
          clearInterval(analyzePollTimer);
          analyzePollTimer = null;
        }
        return;
      }
      const data = await fetchAnalyzeStatus(true);
      if (!data) return;
      const outcome = handleAnalyzeTaskPayload(data);
      if (outcome === 'success' || outcome === 'failure') {
        if (analyzePollTimer) {
          clearInterval(analyzePollTimer);
          analyzePollTimer = null;
        }
      }
    }, 3000);
  };

  const resumeAnalyzeRequest = async () => {
    if (!analyzeForm || !topicUuid) return;
    const stored = loadAnalyzeState();
    if (!stored) return;
    if (analyzePollTimer) {
      clearInterval(analyzePollTimer);
      analyzePollTimer = null;
    }
    analyzeRequestId = stored.requestId || null;
    analyzeTaskId = stored.taskId || null;
    if (analyzeRequestInput) analyzeRequestInput.value = analyzeRequestId || '';
    const payload = {
      request_id: stored.requestId,
      task_id: stored.taskId,
      status: stored.status,
      insights: stored.insights,
      error: stored.error,
      saved: stored.saved,
    };
    const outcome = handleAnalyzeTaskPayload(payload, { persist: false });
    if (outcome === 'pending') {
      if (analyzeBtn) analyzeBtn.disabled = true;
      const latest = await fetchAnalyzeStatus(true);
      if (latest) {
        const latestOutcome = handleAnalyzeTaskPayload(latest);
        if (latestOutcome === 'pending') {
          startAnalyzePolling();
        }
      } else {
        startAnalyzePolling();
      }
    }
    updateSaveInsightsState();
  };

  updateSaveInsightsState();

  if (analyzeBtn && analyzeForm) {
    analyzeBtn.addEventListener('click', async () => {
      if (!topicUuid) return;
      const dataIds = Array.from(analyzeForm.querySelectorAll('input[name="data_ids"]:checked'))
        .map((cb) => parseInt(cb.value, 10))
        .filter((id) => !Number.isNaN(id));
      if (dataIds.length === 0) {
        showAlert(analyzeStatusMessage, 'error', 'Select at least one data table to analyze.');
        return;
      }
      const instructionsEl = analyzeForm.querySelector('textarea[name="instructions"]');
      const instructions = instructionsEl ? instructionsEl.value.trim() : '';
      analyzeBtn.disabled = true;
      if (saveInsightsBtn) saveInsightsBtn.disabled = true;
      if (insightsContainer) {
        insightsContainer.classList.add('d-none');
        insightsContainer.innerHTML = '';
      }
      if (analyzePollTimer) {
        clearInterval(analyzePollTimer);
        analyzePollTimer = null;
      }
      clearAnalyzeState();
      try {
        showAlert(analyzeStatusMessage, 'info', 'We started analyzing your data. You can close this modal while we work.');
        const body = { topic_uuid: topicUuid, data_ids: dataIds };
        if (instructions) body.instructions = instructions;
        const res = await fetch('/api/topics/data/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error('Request failed');
        const data = await res.json();
        const outcome = handleAnalyzeTaskPayload(data);
        if (outcome === 'pending') {
          startAnalyzePolling();
        }
      } catch (err) {
        console.error(err);
        showAlert(analyzeStatusMessage, 'error', 'Unable to start the analysis. Please try again.');
        analyzeBtn.disabled = false;
        clearAnalyzeState();
      }
    });
  }

  if (analyzeForm) {
    analyzeForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!topicUuid || !analyzeRequestId) return;
      const selected = insightsContainer
        ? Array.from(insightsContainer.querySelectorAll('input[type="checkbox"]:checked')).map((cb) => cb.value)
        : [];
      if (selected.length === 0) {
        updateSaveInsightsState();
        return;
      }
      if (saveInsightsBtn) saveInsightsBtn.disabled = true;
      try {
        const res = await fetch('/api/topics/data/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid, request_id: analyzeRequestId, insights: selected }),
        });
        if (!res.ok) throw new Error('Request failed');
        clearAnalyzeState();
        window.location.reload();
      } catch (err) {
        console.error(err);
        showAlert(analyzeStatusMessage, 'error', 'Unable to save the selected insights. Please try again.');
        updateSaveInsightsState();
      }
    });
  }


  if (visualizeBtn && visualizeForm) {
    visualizeBtn.addEventListener('click', async () => {
      if (!topicUuid) return;
      const insightInput = visualizeForm.querySelector('input[name="insight_id"]:checked');
      if (!insightInput) {
        showAlert(visualizeStatusMessage, 'error', 'Select an insight to visualize.');
        return;
      }
      let body;
      if (insightInput.value === 'other') {
        const insight = visualizeOtherInput ? visualizeOtherInput.value.trim() : '';
        if (!insight) {
          showAlert(visualizeStatusMessage, 'error', 'Enter an insight to visualize.');
          return;
        }
        body = { topic_uuid: topicUuid, insight };
      } else {
        const insightId = parseInt(insightInput.value, 10);
        if (Number.isNaN(insightId)) {
          showAlert(visualizeStatusMessage, 'error', 'Select a valid insight to visualize.');
          return;
        }
        body = { topic_uuid: topicUuid, insight_id: insightId };
      }
      const chartType = chartTypeSelect ? chartTypeSelect.value : '';
      if (chartType) body.chart_type = chartType;
      if (visualizeInstructionsInput) {
        const instructions = visualizeInstructionsInput.value.trim();
        if (instructions) body.instructions = instructions;
      }
      visualizeBtn.disabled = true;
      if (saveVisualizationBtn) saveVisualizationBtn.disabled = true;
      if (visualizePollTimer) {
        clearInterval(visualizePollTimer);
        visualizePollTimer = null;
      }
      clearVisualizeState();
      hideVisualizationPreview();
      try {
        showAlert(visualizeStatusMessage, 'info', 'We started building your visualization. Feel free to close this modal.');
        const res = await fetch('/api/topics/data/visualize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error('Request failed');
        const data = await res.json();
        const outcome = handleVisualizationTaskPayload(data);
        if (outcome === 'pending') {
          startVisualizePolling();
        }
      } catch (err) {
        console.error(err);
        showAlert(visualizeStatusMessage, 'error', 'Unable to start the visualization. Please try again.');
        visualizeBtn.disabled = false;
        clearVisualizeState();
      }
    });
  }

  if (saveVisualizationBtn) {
    saveVisualizationBtn.addEventListener('click', async () => {
      if (!topicUuid || !visualizeRequestId) return;
      saveVisualizationBtn.disabled = true;
      try {
        const res = await fetch('/api/topics/data/visualize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid, request_id: visualizeRequestId }),
        });
        if (!res.ok) throw new Error('Request failed');
        clearVisualizeState();
        const modalEl = document.getElementById('dataVisualizeModal');
        if (modalEl && window.bootstrap) {
          const modal = window.bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
        }
        window.location.reload();
      } catch (err) {
        console.error(err);
        showAlert(visualizeStatusMessage, 'error', 'Unable to save the visualization. Please try again.');
        if (visualizeRequestId) {
          saveVisualizationBtn.disabled = false;
        }
      }
    });
  }

  resumeAnalyzeRequest();
  resumeVisualizeRequest();

  if (analyzeModalEl) {
    analyzeModalEl.addEventListener('show.bs.modal', () => {
      resumeAnalyzeRequest();
    });
  }

  if (visualizeModalEl) {
    visualizeModalEl.addEventListener('show.bs.modal', () => {
      resumeVisualizeRequest();
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

});
