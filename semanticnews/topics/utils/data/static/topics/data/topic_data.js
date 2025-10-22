document.addEventListener('DOMContentLoaded', () => {
  const fetchBtn = document.getElementById('fetchDataBtn');
  const form = document.getElementById('dataForm');
  const urlInput = document.getElementById('dataUrl');
  const descriptionInput = document.getElementById('dataDescription');
  const preview = document.getElementById('dataPreview');
  const dataPreviewSection = document.getElementById('dataPreviewSection');
  const sourcesWrapper = document.getElementById('dataSourcesWrapper');
  const sourcesList = document.getElementById('dataSources');
  const explanationEl = document.getElementById('dataExplanation');
  const statusMessage = document.getElementById('dataStatusMessage');
  const nameInput = document.getElementById('dataName');
  const nameWrapper = document.getElementById('dataNameWrapper');
  const previewMeta = document.getElementById('dataPreviewMeta');
  const previewDeleteBtn = document.getElementById('dataPreviewDeleteBtn');
  const previewDeleteModalEl = document.getElementById('dataPreviewDeleteModal');
  const previewDeleteConfirmBtn = document.getElementById('dataPreviewDeleteConfirm');
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
  const analyzePreviewMeta = document.getElementById('analyzePreviewMeta');
  const analyzePreviewDeleteBtn = document.getElementById('analyzePreviewDeleteBtn');
  const analyzePreviewDeleteModalEl = document.getElementById('analyzePreviewDeleteModal');
  const analyzePreviewDeleteConfirmBtn = document.getElementById('analyzePreviewDeleteConfirm');
  const analyzePreviewSection = document.getElementById('analyzePreviewSection');
  const visualizeBtn = document.getElementById('visualizeDataBtn');
  const visualizeForm = document.getElementById('dataVisualizeForm');
  const visualizeOtherInput = document.getElementById('visualizeInsightOtherText');
  const chartTypeSelect = document.getElementById('visualizeChartType');
  const visualizeInstructionsInput = document.getElementById('visualizeInstructions');
  const visualizeStatusMessage = document.getElementById('visualizeStatusMessage');
  const visualizeRequestInput = document.getElementById('visualizeRequestId');
  const visualizePreviewSection = document.getElementById('visualizePreviewSection');
  const visualizePreviewWrapper = document.getElementById('visualizePreviewWrapper');
  const visualizePreviewCanvas = document.getElementById('visualizePreviewChart');
  const visualizePreviewMeta = document.getElementById('visualizePreviewMeta');
  const visualizePreviewInsight = document.getElementById('visualizePreviewInsight');
  const visualizePreviewDeleteBtn = document.getElementById('visualizePreviewDeleteBtn');
  const visualizePreviewDeleteModalEl = document.getElementById('visualizePreviewDeleteModal');
  const visualizePreviewDeleteConfirmBtn = document.getElementById('visualizePreviewDeleteConfirm');
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
  let analyzeDataLabels = [];
  let visualizeDataLabels = [];
  let lastDataRequestMode = null;
  let lastDataRequestDetail = null;

  const IN_PROGRESS_TIMEOUT_MS = 5 * 60 * 1000;

  const normalizeTimestampValue = (value) => {
    if (value instanceof Date) {
      return value.toISOString();
    }
    return typeof value === 'string' && value ? value : null;
  };

  const coalesceTimestamp = (...values) => {
    for (const value of values) {
      const normalized = normalizeTimestampValue(value);
      if (normalized) {
        return normalized;
      }
    }
    return null;
  };

  const isFreshInProgress = (isoString) => {
    const normalized = normalizeTimestampValue(isoString);
    if (!normalized) {
      return true;
    }
    const parsed = Date.parse(normalized);
    if (Number.isNaN(parsed)) {
      return true;
    }
    return (Date.now() - parsed) <= IN_PROGRESS_TIMEOUT_MS;
  };

  const deleteRequestRecord = async (basePath, requestId) => {
    if (requestId === null || requestId === undefined) {
      return;
    }
    const numericId =
      typeof requestId === 'number' ? requestId : parseInt(String(requestId), 10);
    if (Number.isNaN(numericId) || numericId <= 0) {
      return;
    }
    try {
      const res = await fetch(`${basePath}/${numericId}`, { method: 'DELETE' });
      if (res.status === 404) {
        return;
      }
      if (!res.ok) {
        throw new Error('Request failed');
      }
    } catch (err) {
      console.error(err);
    }
  };

  const setFetchButtonBusy = (busy) => {
    if (!fetchBtn) return;
    fetchBtn.disabled = !!busy;
    if (busy) {
      fetchBtn.setAttribute('aria-busy', 'true');
    } else {
      fetchBtn.removeAttribute('aria-busy');
    }
  };

  const setSaveButtonBusy = (busy) => {
    if (!saveButton) return;
    if (busy) {
      saveButton.disabled = true;
      saveButton.setAttribute('aria-busy', 'true');
    } else {
      saveButton.removeAttribute('aria-busy');
    }
  };

  const setAnalyzeButtonBusy = (busy) => {
    if (!analyzeBtn) return;
    analyzeBtn.disabled = !!busy;
    if (busy) {
      analyzeBtn.setAttribute('aria-busy', 'true');
    } else {
      analyzeBtn.removeAttribute('aria-busy');
    }
  };

  const setSaveInsightsButtonBusy = (busy) => {
    if (!saveInsightsBtn) return;
    if (busy) {
      saveInsightsBtn.disabled = true;
      saveInsightsBtn.setAttribute('aria-busy', 'true');
    } else {
      saveInsightsBtn.removeAttribute('aria-busy');
    }
  };

  const setVisualizeButtonBusy = (busy) => {
    if (!visualizeBtn) return;
    visualizeBtn.disabled = !!busy;
    if (busy) {
      visualizeBtn.setAttribute('aria-busy', 'true');
    } else {
      visualizeBtn.removeAttribute('aria-busy');
    }
  };

  const setSaveVisualizationButtonBusy = (busy) => {
    if (!saveVisualizationBtn) return;
    if (busy) {
      saveVisualizationBtn.disabled = true;
      saveVisualizationBtn.setAttribute('aria-busy', 'true');
    } else {
      saveVisualizationBtn.removeAttribute('aria-busy');
    }
  };

  const createStatusIndicator = ({ spinnerId, errorIconId, successIconId }) => {
    const spinner = spinnerId ? document.getElementById(spinnerId) : null;
    const errorIcon = errorIconId ? document.getElementById(errorIconId) : null;
    const successIcon = successIconId ? document.getElementById(successIconId) : null;

    const hide = (el) => el && el.classList.add('d-none');
    const show = (el) => el && el.classList.remove('d-none');

    const setState = (state) => {
      switch (state) {
        case 'loading':
          show(spinner);
          hide(errorIcon);
          hide(successIcon);
          break;
        case 'error':
          hide(spinner);
          show(errorIcon);
          hide(successIcon);
          break;
        case 'success':
          hide(spinner);
          hide(errorIcon);
          show(successIcon);
          break;
        default:
          hide(spinner);
          hide(errorIcon);
          hide(successIcon);
          break;
      }
    };

    setState('idle');

    return {
      showLoading: () => setState('loading'),
      showError: () => setState('error'),
      showSuccess: () => setState('success'),
      reset: () => setState('idle'),
    };
  };

  const dataAddIndicator = createStatusIndicator({
    spinnerId: 'dataAddSpinner',
    errorIconId: 'dataAddErrorIcon',
    successIconId: 'dataAddSuccessIcon',
  });

  const analyzeIndicator = createStatusIndicator({
    spinnerId: 'dataAnalyzeSpinner',
    errorIconId: 'dataAnalyzeErrorIcon',
    successIconId: 'dataAnalyzeSuccessIcon',
  });

  const visualizeIndicator = createStatusIndicator({
    spinnerId: 'dataVisualizeSpinner',
    errorIconId: 'dataVisualizeErrorIcon',
    successIconId: 'dataVisualizeSuccessIcon',
  });

  const getModalInstance = (element) => {
    if (!element || typeof bootstrap === 'undefined' || !bootstrap.Modal) {
      return null;
    }
    if (typeof bootstrap.Modal.getOrCreateInstance === 'function') {
      return bootstrap.Modal.getOrCreateInstance(element);
    }
    return new bootstrap.Modal(element);
  };

  const setMetaText = (element, text) => {
    if (!element) return;
    if (text) {
      element.textContent = text;
      element.classList.remove('d-none');
    } else {
      element.textContent = '';
      element.classList.add('d-none');
    }
  };

  const setPreviewInsightText = (element, text) => {
    if (!element) return;
    let value = '';
    if (typeof text === 'string') {
      value = text.trim();
    } else if (text !== null && text !== undefined) {
      value = String(text).trim();
    }
    if (value) {
      element.textContent = value;
      element.classList.remove('d-none');
    } else {
      element.textContent = '';
      element.classList.add('d-none');
    }
  };

  const toStringList = (values) => {
    if (!Array.isArray(values)) return [];
    return values
      .map((value) => {
        if (typeof value === 'string') {
          return value.trim();
        }
        if (typeof value === 'number' && Number.isFinite(value)) {
          return String(value);
        }
        return '';
      })
      .filter((value) => value);
  };

  const setListMeta = (element, values) => {
    if (!element) return;
    const list = toStringList(values);
    if (list.length === 0) {
      setMetaText(element, '');
      return;
    }
    const labelText = element.dataset ? element.dataset.label || '' : '';
    const content = labelText ? `${labelText}: ${list.join(', ')}` : list.join(', ');
    setMetaText(element, content);
  };

  const toggleButtonVisibility = (button, visible) => {
    if (!button) return;
    if (visible) {
      button.classList.remove('d-none');
      button.disabled = false;
    } else {
      button.classList.add('d-none');
      button.disabled = true;
    }
  };

  const setPreviewSectionVisible = (section, visible) => {
    if (!section) return;
    if (visible) {
      section.classList.remove('d-none');
    } else {
      section.classList.add('d-none');
    }
  };

  const dataPreviewDeleteModal = getModalInstance(previewDeleteModalEl);
  const analyzePreviewDeleteModal = getModalInstance(analyzePreviewDeleteModalEl);
  const visualizePreviewDeleteModal = getModalInstance(visualizePreviewDeleteModalEl);

  const setDataPreviewUsage = (data) => {
    if (!previewMeta) return;
    if (!data) {
      setMetaText(previewMeta, '');
      return;
    }
    const dataset = previewMeta.dataset || {};
    const mode = data.mode === 'search' ? 'search' : 'url';
    let labelText = '';
    if (mode === 'search' && dataset.labelSearch) {
      labelText = dataset.labelSearch;
    } else if (mode === 'url' && dataset.labelUrl) {
      labelText = dataset.labelUrl;
    } else {
      labelText = dataset.label || '';
    }
    let value = '';
    if (mode === 'search') {
      value = typeof data.sourceDetail === 'string' ? data.sourceDetail.trim() : '';
      if (!value && typeof lastDataRequestDetail === 'string') {
        value = lastDataRequestDetail.trim();
      }
    } else {
      value = typeof data.url === 'string' ? data.url.trim() : '';
      if (!value) {
        value = typeof data.sourceDetail === 'string' ? data.sourceDetail.trim() : '';
      }
    }
    if (!value && Array.isArray(data.sources)) {
      const fallback = data.sources.find((src) => typeof src === 'string' && src.trim());
      if (fallback) {
        value = fallback.trim();
      }
    }
    const text = value ? (labelText ? `${labelText}: ${value}` : value) : '';
    setMetaText(previewMeta, text);
  };

  const updateAnalyzeUsageDisplay = () => {
    if (!analyzePreviewMeta) return;
    setListMeta(analyzePreviewMeta, analyzeDataLabels);
  };

  const updateVisualizeUsageDisplay = () => {
    if (!visualizePreviewMeta) return;
    setListMeta(visualizePreviewMeta, visualizeDataLabels);
  };

  let activeDataOperation = null;

  const setDataOperationState = (operation, status) => {
    if (!dataButtonController) return;

    if (status === 'reset') {
      if (activeDataOperation === operation) {
        activeDataOperation = null;
        dataButtonController.reset();
      }
      return;
    }

    activeDataOperation = operation;

    if (status === 'loading') {
      dataButtonController.showLoading();
      return;
    }

    if (status === 'success') {
      dataButtonController.showSuccess();
      return;
    }

    if (status === 'error') {
      dataButtonController.showError();
    }
  };

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
    setMetaText(visualizePreviewMeta, '');
    setPreviewInsightText(visualizePreviewInsight, '');
    toggleButtonVisibility(visualizePreviewDeleteBtn, false);
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
    visualizeDataLabels = [];
    updateVisualizeUsageDisplay();
    toggleButtonVisibility(visualizePreviewDeleteBtn, false);
    setPreviewSectionVisible(visualizePreviewSection, false);
    setPreviewInsightText(visualizePreviewInsight, '');
  };

  const handleVisualizePreviewDelete = () => {
    const requestId = visualizeRequestId;
    clearVisualizeState();
    hideVisualizationPreview();
    resetAlert(visualizeStatusMessage);
    visualizeIndicator.reset();
    setDataOperationState('visualize', 'reset');
    setVisualizeButtonBusy(false);
    setSaveVisualizationButtonBusy(false);
    if (saveVisualizationBtn) saveVisualizationBtn.disabled = true;
    setPreviewSectionVisible(visualizePreviewSection, false);
    if (requestId !== null && requestId !== undefined) {
      deleteRequestRecord('/api/topics/data/visualize/request', requestId);
    }
  };

  const saveVisualizeState = (payload) => {
    if (!visualizeStorageKey || !payload || typeof payload.request_id !== 'number') return;
    const insightText =
      typeof payload.insight === 'string'
        ? payload.insight.trim()
        : payload.insight !== null && payload.insight !== undefined
          ? String(payload.insight).trim()
          : '';

    const state = {
      requestId: payload.request_id,
      taskId: payload.task_id || null,
      status: payload.status,
      chartType: payload.chart_type || null,
      chartData: payload.chart_data || null,
      insight: insightText || null,
      error: payload.error || null,
      saved: Boolean(payload.saved),
    };
    const createdAt = normalizeTimestampValue(payload.created_at);
    const updatedAt = normalizeTimestampValue(payload.updated_at) || createdAt;
    const persistedAt = normalizeTimestampValue(payload.persisted_at);
    if (createdAt) state.createdAt = createdAt;
    if (updatedAt) state.updatedAt = updatedAt;
    state.persistedAt = persistedAt || new Date().toISOString();
    state.dataIds = Array.isArray(payload.data_ids)
      ? payload.data_ids
          .map((value) => {
            if (typeof value === 'number' && Number.isFinite(value)) {
              return value;
            }
            const parsed = parseInt(value, 10);
            return Number.isNaN(parsed) ? null : parsed;
          })
          .filter((value) => value !== null)
      : [];
    state.dataLabels = toStringList(payload.data_labels);
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
        visualizeIndicator.reset();
        setDataOperationState('visualize', 'reset');
        return null;
      }
      if (!res.ok) throw new Error('Request failed');
      const data = await res.json();
      if (data && !data.input_detail && lastDataRequestDetail) {
        data.input_detail = lastDataRequestDetail;
      }
      if (data && !data.mode && lastDataRequestMode) {
        data.mode = lastDataRequestMode;
      }
      return data;
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

    setPreviewInsightText(visualizePreviewInsight, payload.insight);

    const payloadLabels = toStringList(payload.data_labels);
    if (payloadLabels.length > 0) {
      visualizeDataLabels = payloadLabels;
    } else {
      visualizeDataLabels = toStringList(payload.data_ids);
    }
    updateVisualizeUsageDisplay();

    const status = payload.status;
    const saved = Boolean(payload.saved);
    const createdAtIso = normalizeTimestampValue(payload.created_at);
    const updatedAtIso = normalizeTimestampValue(payload.updated_at) || createdAtIso;
    const persistedAtIso = normalizeTimestampValue(payload.persisted_at);
    const pendingTimestamp = coalesceTimestamp(updatedAtIso, persistedAtIso, createdAtIso);

    if (status === 'pending' || status === 'started') {
      if (!isFreshInProgress(pendingTimestamp)) {
        clearVisualizeState();
        hideVisualizationPreview();
        resetAlert(visualizeStatusMessage);
        visualizeIndicator.reset();
        setDataOperationState('visualize', 'reset');
        setVisualizeButtonBusy(false);
        setSaveVisualizationButtonBusy(false);
        return 'stale';
      }
      showAlert(visualizeStatusMessage, 'info', 'We started building your visualization. Feel free to close this modal.');
      setVisualizeButtonBusy(true);
      setSaveVisualizationButtonBusy(true);
      hideVisualizationPreview();
      visualizeIndicator.showLoading();
      setDataOperationState('visualize', 'loading');
      setPreviewSectionVisible(visualizePreviewSection, false);
      return 'pending';
    }

    if (status === 'failure') {
      showAlert(visualizeStatusMessage, 'error', payload.error || 'Unable to generate a visualization.');
      if (saveVisualizationBtn) saveVisualizationBtn.disabled = true;
      setVisualizeButtonBusy(false);
      setSaveVisualizationButtonBusy(false);
      clearVisualizeState();
      visualizeIndicator.showError();
      setDataOperationState('visualize', 'error');
      return 'failure';
    }

    if (status === 'success') {
      visualizeIndicator.showSuccess();
      setDataOperationState('visualize', 'success');
      setVisualizeButtonBusy(false);
      setSaveVisualizationButtonBusy(false);
      if (saved) {
        showAlert(visualizeStatusMessage, 'success', 'Visualization saved to the topic.');
        hideVisualizationPreview();
        if (saveVisualizationBtn) saveVisualizationBtn.disabled = true;
        clearVisualizeState();
        return 'success';
      }
      setPreviewSectionVisible(visualizePreviewSection, true);
      if (payload.chart_type && payload.chart_data) {
        renderVisualizationPreview(payload.chart_type, payload.chart_data);
        showAlert(visualizeStatusMessage, 'success', 'Review the preview and click Save to add it to the topic.');
        if (saveVisualizationBtn) saveVisualizationBtn.disabled = false;
        updateVisualizeUsageDisplay();
        toggleButtonVisibility(visualizePreviewDeleteBtn, true);
      } else {
        hideVisualizationPreview();
        showAlert(visualizeStatusMessage, 'info', 'The visualization completed without chart data.');
        if (saveVisualizationBtn) saveVisualizationBtn.disabled = true;
        updateVisualizeUsageDisplay();
        toggleButtonVisibility(visualizePreviewDeleteBtn, true);
        setPreviewInsightText(visualizePreviewInsight, payload.insight);
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
      if (outcome === 'success' || outcome === 'failure' || outcome === 'stale') {
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
      data_ids: stored.dataIds,
      data_labels: stored.dataLabels,
      created_at: stored.createdAt || stored.persistedAt || null,
      updated_at: stored.updatedAt || stored.persistedAt || null,
      persisted_at: stored.persistedAt || null,
    };
    const outcome = handleVisualizationTaskPayload(payload, { persist: false });
    if (outcome === 'pending') {
      setVisualizeButtonBusy(true);
      setSaveVisualizationButtonBusy(true);
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
    if (!storageKey || !state) return;
    const normalized = { ...state };
    const createdAt = normalizeTimestampValue(normalized.createdAt)
      || normalizeTimestampValue(normalized.created_at);
    const updatedAt = normalizeTimestampValue(normalized.updatedAt)
      || normalizeTimestampValue(normalized.updated_at)
      || createdAt;
    if (createdAt) {
      normalized.createdAt = createdAt;
    } else {
      delete normalized.createdAt;
    }
    if (updatedAt) {
      normalized.updatedAt = updatedAt;
    } else {
      delete normalized.updatedAt;
    }
    delete normalized.created_at;
    delete normalized.updated_at;
    const persistedAt = normalizeTimestampValue(normalized.persistedAt)
      || normalizeTimestampValue(normalized.persisted_at);
    normalized.persistedAt = persistedAt || new Date().toISOString();
    delete normalized.persisted_at;
    try {
      localStorage.setItem(storageKey, JSON.stringify(normalized));
    } catch (err) {
      console.error(err);
    }
  };

  const clearStoredState = () => {
    currentRequestId = null;
    lastDataRequestDetail = null;
    lastDataRequestMode = null;
    if (!storageKey) return;
    localStorage.removeItem(storageKey);
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
    setPreviewSectionVisible(dataPreviewSection, false);
    if (preview) preview.innerHTML = '';
    if (sourcesWrapper) sourcesWrapper.classList.add('d-none');
    if (sourcesList) sourcesList.innerHTML = '';
    if (explanationEl) {
      explanationEl.classList.add('d-none');
      explanationEl.textContent = '';
    }
    if (nameWrapper) nameWrapper.classList.add('d-none');
    if (nameInput) nameInput.value = '';
    setDataPreviewUsage(null);
    toggleButtonVisibility(previewDeleteBtn, false);
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

  const applyResult = (result, mode, inputDetail) => {
    const normalized = normalizeResult(result);
    if (!normalized) return;

    const hasSources = Array.isArray(normalized.sources) && normalized.sources.length > 0;
    const fallbackMode = hasSources && !normalized.url ? 'search' : 'url';
    const effectiveMode = mode || lastDataRequestMode || fallbackMode;
    const urlFromResult = typeof normalized.url === 'string' ? normalized.url.trim() : '';
    const fallbackUrlValue = effectiveMode === 'url'
      ? (urlInput ? urlInput.value.trim() : '')
      : hasSources
        ? normalized.sources[0]
        : '';
    const normalizedUrl = urlFromResult || (typeof fallbackUrlValue === 'string' ? fallbackUrlValue.trim() : '');

    const providedDetail = typeof inputDetail === 'string' ? inputDetail.trim() : '';
    let sourceDetail = providedDetail;
    if (!sourceDetail) {
      if (effectiveMode === 'search') {
        sourceDetail = descriptionInput ? descriptionInput.value.trim() : '';
      } else if (effectiveMode === 'url') {
        sourceDetail = normalizedUrl;
      }
    }

    fetchedData = {
      headers: normalized.headers,
      rows: normalized.rows,
      name: normalized.name,
      sources: hasSources ? normalized.sources : [],
      explanation: normalized.explanation,
      url: normalizedUrl,
      mode: effectiveMode,
      sourceDetail,
    };

    lastDataRequestMode = effectiveMode;
    if (sourceDetail) {
      lastDataRequestDetail = sourceDetail;
    } else if (effectiveMode === 'url' && normalizedUrl) {
      lastDataRequestDetail = normalizedUrl;
    }

    if (nameInput) {
      nameInput.value = fetchedData.name || '';
      if (nameWrapper) {
        nameWrapper.classList.remove('d-none');
      }
    }

    setPreviewSectionVisible(dataPreviewSection, true);
    renderPreview(fetchedData);
    setDataPreviewUsage(fetchedData);
    toggleButtonVisibility(previewDeleteBtn, true);

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
    const payloadDetail =
      typeof payload.input_detail === 'string' ? payload.input_detail.trim() : '';

    if (isSaved) {
      setFetchButtonBusy(false);
      dataAddIndicator.showSuccess();
      setDataOperationState('add', 'success');
      clearStoredState();
      lastDataRequestDetail = null;
      lastDataRequestMode = null;
      currentTaskId = null;
      currentRequestId = null;
      fetchedData = null;
      resetPreview();
      hideStatusMessage();
      updateSaveButtonState();
      setSaveButtonBusy(false);
      stopPolling();
      return 'saved';
    }

    if (!taskId) return 'none';
    currentTaskId = taskId;
    currentRequestId = requestId || null;
    const status = payload.status;
    const normalizedResult = normalizeResult(payload.result);
    const hasSources = normalizedResult && Array.isArray(normalizedResult.sources) && normalizedResult.sources.length > 0;
    const fallbackMode = hasSources && normalizedResult && !normalizedResult.url ? 'search' : 'url';
    const mode = payload.mode || lastDataRequestMode || fallbackMode;
    lastDataRequestMode = mode;

    let inputDetail = payloadDetail;
    if (!inputDetail && typeof lastDataRequestDetail === 'string' && lastDataRequestDetail.trim()) {
      inputDetail = lastDataRequestDetail.trim();
    }
    if (
      !inputDetail &&
      normalizedResult &&
      mode === 'url' &&
      typeof normalizedResult.url === 'string' &&
      normalizedResult.url.trim()
    ) {
      inputDetail = normalizedResult.url.trim();
    }
    lastDataRequestDetail = inputDetail || lastDataRequestDetail || null;

    const createdAtIso = normalizeTimestampValue(payload.created_at);
    const updatedAtIso = normalizeTimestampValue(payload.updated_at) || createdAtIso;
    const persistedAtIso = normalizeTimestampValue(payload.persisted_at);
    const pendingTimestamp = coalesceTimestamp(updatedAtIso, persistedAtIso, createdAtIso);

    if (status === 'pending' || status === 'started') {
      if (!isFreshInProgress(pendingTimestamp)) {
        setFetchButtonBusy(false);
        hideStatusMessage();
        dataAddIndicator.reset();
        setDataOperationState('add', 'reset');
        fetchedData = null;
        resetPreview();
        updateSaveButtonState();
        setSaveButtonBusy(false);
        stopPolling();
        clearStoredState();
        currentTaskId = null;
        currentRequestId = null;
        return 'stale';
      }
      setFetchButtonBusy(true);
      setStatusMessage('info', 'We started gathering your data. You can close this modal while we work.');
      dataAddIndicator.showLoading();
      setDataOperationState('add', 'loading');
      fetchedData = null;
      resetPreview();
      updateSaveButtonState();
      setSaveButtonBusy(true);
      saveStoredState({
        taskId,
        status,
        mode,
        requestId: currentRequestId,
        saved: false,
        inputDetail: inputDetail || null,
        createdAt: createdAtIso,
        updatedAt: updatedAtIso,
        persistedAt: persistedAtIso,
      });
      return 'pending';
    }

    if (status === 'success') {
      setFetchButtonBusy(false);
      if (normalizedResult) {
        applyResult(normalizedResult, mode, inputDetail);
      }
      setStatusMessage('success', 'Your data is ready. Review the preview and click Save to add it to the topic.');
      dataAddIndicator.showSuccess();
      setDataOperationState('add', 'success');
      setSaveButtonBusy(false);
      stopPolling();
      saveStoredState({
        taskId,
        status: 'success',
        mode,
        result: normalizedResult || null,
        requestId: currentRequestId,
        saved: false,
        inputDetail: inputDetail || null,
        createdAt: createdAtIso,
        updatedAt: updatedAtIso,
        persistedAt: persistedAtIso,
      });
      return 'success';
    }

    if (status === 'failure') {
      setFetchButtonBusy(false);
      const message = payload.error || 'We were unable to fetch data. Please try again.';
      setStatusMessage('error', message);
      dataAddIndicator.showError();
      setDataOperationState('add', 'error');
      fetchedData = null;
      resetPreview();
      updateSaveButtonState();
      setSaveButtonBusy(false);
      stopPolling();
      saveStoredState({
        taskId,
        status: 'failure',
        mode,
        error: message,
        requestId: currentRequestId,
        saved: false,
        inputDetail: inputDetail || null,
        createdAt: createdAtIso,
        updatedAt: updatedAtIso,
        persistedAt: persistedAtIso,
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
        }
        setFetchButtonBusy(false);
        dataAddIndicator.reset();
        setDataOperationState('add', 'reset');
        clearStoredState();
        currentTaskId = null;
        currentRequestId = null;
        setSaveButtonBusy(false);
        stopPolling();
        return null;
      }
      if (!res.ok) throw new Error('Request failed');
      const data = await res.json();
      if (data && !data.input_detail && lastDataRequestDetail) {
        data.input_detail = lastDataRequestDetail;
      }
      if (data && !data.mode && lastDataRequestMode) {
        data.mode = lastDataRequestMode;
      }
      return data;
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
      if (outcome === 'success' || outcome === 'failure' || outcome === 'saved' || outcome === 'stale') {
        stopPolling();
      }
    }, 3000);
  };

  const handleDataPreviewDelete = () => {
    const requestId = currentRequestId;
    stopPolling();
    clearStoredState();
    fetchedData = null;
    currentTaskId = null;
    resetPreview();
    hideStatusMessage();
    setFetchButtonBusy(false);
    setSaveButtonBusy(false);
    dataAddIndicator.reset();
    setDataOperationState('add', 'reset');
    updateSaveButtonState();
    if (requestId !== null && requestId !== undefined) {
      deleteRequestRecord('/api/topics/data/request', requestId);
    }
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

  if (previewDeleteBtn && previewDeleteConfirmBtn) {
    previewDeleteBtn.addEventListener('click', () => {
      if (dataPreviewDeleteModal) {
        dataPreviewDeleteModal.show();
      } else {
        handleDataPreviewDelete();
      }
    });
    previewDeleteConfirmBtn.addEventListener('click', () => {
      handleDataPreviewDelete();
      if (dataPreviewDeleteModal) {
        dataPreviewDeleteModal.hide();
      }
    });
  }

  if (fetchBtn && form) {
    fetchBtn.addEventListener('click', async () => {
      setFetchButtonBusy(true);
      setSaveButtonBusy(true);
      fetchedData = null;
      updateSaveButtonState();
      resetPreview();
      hideStatusMessage();
      stopPolling();
      currentTaskId = null;
      currentRequestId = null;
      clearStoredState();
      dataAddIndicator.reset();
      setDataOperationState('add', 'reset');

      if (!topicUuid) {
        setFetchButtonBusy(false);
        setSaveButtonBusy(false);
        return;
      }

      const modeEl = document.querySelector('input[name="data_mode"]:checked');
      const mode = modeEl ? modeEl.value : 'url';
      const body = { topic_uuid: topicUuid };
      let endpoint = '/api/topics/data/fetch';

      if (mode === 'url') {
        const urlValue = urlInput ? urlInput.value.trim() : '';
        if (!urlValue) {
          setFetchButtonBusy(false);
          setSaveButtonBusy(false);
          return;
        }
        body.url = urlValue;
        lastDataRequestDetail = urlValue;
      } else {
        endpoint = '/api/topics/data/search';
        const description = descriptionInput ? descriptionInput.value.trim() : '';
        if (!description) {
          setFetchButtonBusy(false);
          setSaveButtonBusy(false);
          return;
        }
        body.description = description;
        lastDataRequestDetail = description;
      }
      lastDataRequestMode = mode;

      try {
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error('Request failed');
        const data = await res.json();
        if (data && !data.input_detail && lastDataRequestDetail) {
          data.input_detail = lastDataRequestDetail;
        }
        if (data && !data.mode) {
          data.mode = mode;
        }
        const outcome = handleStatusPayload(data);
        if (outcome === 'pending') {
          startPolling();
        } else if (outcome === 'none') {
          setFetchButtonBusy(false);
          setSaveButtonBusy(false);
        }
      } catch (err) {
        console.error(err);
        setStatusMessage('error', 'Unable to start the data request. Please try again.');
        dataAddIndicator.showError();
        setDataOperationState('add', 'error');
        setFetchButtonBusy(false);
        setSaveButtonBusy(false);
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
      if (typeof stored.mode === 'string') {
        lastDataRequestMode = stored.mode;
      }
      if (typeof stored.inputDetail === 'string' && stored.inputDetail.trim()) {
        lastDataRequestDetail = stored.inputDetail.trim();
      }
      handleStatusPayload({
        task_id: stored.taskId,
        status: stored.status || 'pending',
        mode: stored.mode || 'url',
        result: stored.result || null,
        error: stored.error || null,
        request_id: stored.requestId || null,
        saved: stored.saved || false,
        input_detail: stored.inputDetail || null,
        created_at: stored.createdAt || stored.persistedAt || null,
        updated_at: stored.updatedAt || stored.persistedAt || null,
        persisted_at: stored.persistedAt || null,
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
    analyzeDataLabels = [];
    updateAnalyzeUsageDisplay();
    toggleButtonVisibility(analyzePreviewDeleteBtn, false);
    setPreviewSectionVisible(analyzePreviewSection, false);
    updateSaveInsightsState();
  };

  const handleAnalyzePreviewDelete = () => {
    const requestId = analyzeRequestId;
    clearAnalyzeState();
    if (insightsContainer) {
      insightsContainer.classList.add('d-none');
      insightsContainer.innerHTML = '';
    }
    resetAlert(analyzeStatusMessage);
    analyzeIndicator.reset();
    setDataOperationState('analyze', 'reset');
    setAnalyzeButtonBusy(false);
    setSaveInsightsButtonBusy(false);
    if (saveInsightsBtn) saveInsightsBtn.disabled = true;
    setPreviewSectionVisible(analyzePreviewSection, false);
    if (requestId !== null && requestId !== undefined) {
      deleteRequestRecord('/api/topics/data/analyze/request', requestId);
    }
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
    const createdAt = normalizeTimestampValue(payload.created_at);
    const updatedAt = normalizeTimestampValue(payload.updated_at) || createdAt;
    const persistedAt = normalizeTimestampValue(payload.persisted_at);
    if (createdAt) state.createdAt = createdAt;
    if (updatedAt) state.updatedAt = updatedAt;
    state.persistedAt = persistedAt || new Date().toISOString();
    state.dataIds = Array.isArray(payload.data_ids)
      ? payload.data_ids
          .map((value) => {
            if (typeof value === 'number' && Number.isFinite(value)) {
              return value;
            }
            const parsed = parseInt(value, 10);
            return Number.isNaN(parsed) ? null : parsed;
          })
          .filter((value) => value !== null)
      : [];
    state.dataLabels = toStringList(payload.data_labels);
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
        analyzeIndicator.reset();
        setDataOperationState('analyze', 'reset');
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

    const payloadLabels = toStringList(payload.data_labels);
    if (payloadLabels.length > 0) {
      analyzeDataLabels = payloadLabels;
    } else {
      analyzeDataLabels = toStringList(payload.data_ids);
    }
    updateAnalyzeUsageDisplay();

    const status = payload.status;
    const saved = Boolean(payload.saved);
    const createdAtIso = normalizeTimestampValue(payload.created_at);
    const updatedAtIso = normalizeTimestampValue(payload.updated_at) || createdAtIso;
    const persistedAtIso = normalizeTimestampValue(payload.persisted_at);
    const pendingTimestamp = coalesceTimestamp(updatedAtIso, persistedAtIso, createdAtIso);

    if (status === 'pending' || status === 'started') {
      if (!isFreshInProgress(pendingTimestamp)) {
        clearAnalyzeState();
        if (insightsContainer) {
          insightsContainer.classList.add('d-none');
          insightsContainer.innerHTML = '';
        }
        resetAlert(analyzeStatusMessage);
        analyzeIndicator.reset();
        setDataOperationState('analyze', 'reset');
        setAnalyzeButtonBusy(false);
        setSaveInsightsButtonBusy(false);
        return 'stale';
      }
      showAlert(analyzeStatusMessage, 'info', 'We started analyzing your data. You can close this modal while we work.');
      if (insightsContainer) {
        insightsContainer.classList.add('d-none');
        insightsContainer.innerHTML = '';
      }
      setAnalyzeButtonBusy(true);
      setSaveInsightsButtonBusy(true);
      analyzeIndicator.showLoading();
      setDataOperationState('analyze', 'loading');
      toggleButtonVisibility(analyzePreviewDeleteBtn, false);
      setPreviewSectionVisible(analyzePreviewSection, false);
      return 'pending';
    }

    if (status === 'failure') {
      showAlert(analyzeStatusMessage, 'error', payload.error || 'Unable to analyze the selected data.');
      if (insightsContainer) {
        insightsContainer.classList.add('d-none');
        insightsContainer.innerHTML = '';
      }
      if (saveInsightsBtn) saveInsightsBtn.disabled = true;
      setAnalyzeButtonBusy(false);
      setSaveInsightsButtonBusy(false);
      analyzeIndicator.showError();
      setDataOperationState('analyze', 'error');
      analyzeDataLabels = [];
      updateAnalyzeUsageDisplay();
      toggleButtonVisibility(analyzePreviewDeleteBtn, false);
      clearAnalyzeState();
      setPreviewSectionVisible(analyzePreviewSection, false);
      return 'failure';
    }

    if (status === 'success') {
      analyzeIndicator.showSuccess();
      setDataOperationState('analyze', 'success');
      setAnalyzeButtonBusy(false);
      setSaveInsightsButtonBusy(false);
      if (saved) {
        showAlert(analyzeStatusMessage, 'success', 'Insights saved to the topic.');
        clearAnalyzeState();
        return 'success';
      }
      setPreviewSectionVisible(analyzePreviewSection, true);
      if (Array.isArray(payload.insights) && payload.insights.length > 0) {
        renderInsights(payload.insights);
        showAlert(analyzeStatusMessage, 'success', 'Analysis complete. Select the insights you want to keep.');
      } else {
        renderInsights([]);
        showAlert(analyzeStatusMessage, 'info', 'The analysis finished but did not produce insights.');
      }
      updateAnalyzeUsageDisplay();
      toggleButtonVisibility(analyzePreviewDeleteBtn, true);
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
      if (outcome === 'success' || outcome === 'failure' || outcome === 'stale') {
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
      data_ids: stored.dataIds,
      data_labels: stored.dataLabels,
      created_at: stored.createdAt || stored.persistedAt || null,
      updated_at: stored.updatedAt || stored.persistedAt || null,
      persisted_at: stored.persistedAt || null,
    };
    const outcome = handleAnalyzeTaskPayload(payload, { persist: false });
    if (outcome === 'pending') {
      setAnalyzeButtonBusy(true);
      setSaveInsightsButtonBusy(true);
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

  if (analyzePreviewDeleteBtn && analyzePreviewDeleteConfirmBtn) {
    analyzePreviewDeleteBtn.addEventListener('click', () => {
      if (analyzePreviewDeleteModal) {
        analyzePreviewDeleteModal.show();
      } else {
        handleAnalyzePreviewDelete();
      }
    });
    analyzePreviewDeleteConfirmBtn.addEventListener('click', () => {
      handleAnalyzePreviewDelete();
      if (analyzePreviewDeleteModal) {
        analyzePreviewDeleteModal.hide();
      }
    });
  }

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
      analyzeDataLabels = dataIds
        .map((id) => {
          const input = analyzeForm.querySelector(`input[name="data_ids"][value="${id}"]`);
          if (!input) return '';
          const label = analyzeForm.querySelector(`label[for="${input.id}"]`);
          return label && label.textContent ? label.textContent.trim() : '';
        })
        .filter((value) => value);
      updateAnalyzeUsageDisplay();
      toggleButtonVisibility(analyzePreviewDeleteBtn, false);
      const instructionsEl = analyzeForm.querySelector('textarea[name="instructions"]');
      const instructions = instructionsEl ? instructionsEl.value.trim() : '';
      setAnalyzeButtonBusy(true);
      setSaveInsightsButtonBusy(true);
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
        analyzeIndicator.showLoading();
        setDataOperationState('analyze', 'loading');
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
        } else if (outcome === 'none') {
          setAnalyzeButtonBusy(false);
          setSaveInsightsButtonBusy(false);
          updateSaveInsightsState();
        }
      } catch (err) {
        console.error(err);
        showAlert(analyzeStatusMessage, 'error', 'Unable to start the analysis. Please try again.');
        clearAnalyzeState();
        analyzeIndicator.showError();
        setDataOperationState('analyze', 'error');
        setAnalyzeButtonBusy(false);
        setSaveInsightsButtonBusy(false);
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
      setSaveInsightsButtonBusy(true);
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
        setSaveInsightsButtonBusy(false);
      }
    });
  }


  if (visualizePreviewDeleteBtn && visualizePreviewDeleteConfirmBtn) {
    visualizePreviewDeleteBtn.addEventListener('click', () => {
      if (visualizePreviewDeleteModal) {
        visualizePreviewDeleteModal.show();
      } else {
        handleVisualizePreviewDelete();
      }
    });
    visualizePreviewDeleteConfirmBtn.addEventListener('click', () => {
      handleVisualizePreviewDelete();
      if (visualizePreviewDeleteModal) {
        visualizePreviewDeleteModal.hide();
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
      setVisualizeButtonBusy(true);
      setSaveVisualizationButtonBusy(true);
      if (visualizePollTimer) {
        clearInterval(visualizePollTimer);
        visualizePollTimer = null;
      }
      clearVisualizeState();
      hideVisualizationPreview();
      try {
        showAlert(visualizeStatusMessage, 'info', 'We started building your visualization. Feel free to close this modal.');
        visualizeIndicator.showLoading();
        setDataOperationState('visualize', 'loading');
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
        } else if (outcome === 'none') {
          setVisualizeButtonBusy(false);
          setSaveVisualizationButtonBusy(false);
        }
      } catch (err) {
        console.error(err);
        showAlert(visualizeStatusMessage, 'error', 'Unable to start the visualization. Please try again.');
        clearVisualizeState();
        visualizeIndicator.showError();
        setDataOperationState('visualize', 'error');
        setVisualizeButtonBusy(false);
        setSaveVisualizationButtonBusy(false);
      }
    });
  }

  if (saveVisualizationBtn) {
    saveVisualizationBtn.addEventListener('click', async () => {
      if (!topicUuid || !visualizeRequestId) return;
      setSaveVisualizationButtonBusy(true);
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
          setSaveVisualizationButtonBusy(false);
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
