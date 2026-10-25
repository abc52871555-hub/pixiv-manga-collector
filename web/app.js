/* Pixiv 漫画采集 · 前端逻辑
 * 与 server.py 的约定:
 *   GET  /api/config
 *   POST /api/connect
 *   POST /api/preview
 *   POST /api/download  → job_id
 *   GET  /api/jobs/{id}
 *   POST /api/jobs/{id}/cancel
 *   POST /api/open-output
 */

(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const els = {
    account: $('#account'),
    accountName: $('#accountName'),
    keySource: $('#keySource'),
    tokenInput: $('#tokenInput'),
    toggleToken: $('#toggleToken'),
    rememberKey: $('#rememberKey'),
    connectBtn: $('#connectBtn'),
    connectNote: $('#connectNote'),
    extractKeyBtn: $('#extractKeyBtn'),
    autoLoginBtn: $('#autoLoginBtn'),
    autoLoginStatus: $('#autoLoginStatus'),
    libraryBtn: $('#libraryBtn'),
    libraryDialog: $('#libraryDialog'),
    libraryClose: $('#libraryClose'),
    libSearch: $('#libSearch'),
    libSource: $('#libSource'),
    libType: $('#libType'),
    libR18: $('#libR18'),
    libHit: $('#libHit'),
    libTag: $('#libTag'),
    libAuthor: $('#libAuthor'),
    libSession: $('#libSession'),
    libSort: $('#libSort'),
    libGroup: $('#libGroup'),
    libRefresh: $('#libRefresh'),
    libSummary: $('#libSummary'),
    libStats: $('#libStats'),
    libGroups: $('#libGroups'),
    libEmpty: $('#libEmpty'),
    libMore: $('#libMore'),
    libViewer: $('#libViewer'),
    libViewerTitle: $('#libViewerTitle'),
    libViewerMeta: $('#libViewerMeta'),
    libViewerImg: $('#libViewerImg'),
    libViewerPrev: $('#libViewerPrev'),
    libViewerNext: $('#libViewerNext'),
    libViewerThumbs: $('#libViewerThumbs'),
    libViewerClose: $('#libViewerClose'),
    libViewerFolder: $('#libViewerFolder'),
    libViewerPixiv: $('#libViewerPixiv'),
    libViewerCounter: $('#libViewerCounter'),
    libViewerTags: $('#libViewerTags'),
    keyDialog: $('#keyDialog'),
    keyDialogClose: $('#keyDialogClose'),
    extractOpenBtn: $('#extractOpenBtn'),
    extractPasteBtn: $('#extractPasteBtn'),
    extractLoginLink: $('#extractLoginLink'),
    extractCode: $('#extractCode'),
    extractStatus: $('#extractStatus'),
    extractFinishBtn: $('#extractFinishBtn'),
    keySourceList: $('#keySourceList'),
    refreshSourcesBtn: $('#refreshSourcesBtn'),
    tabTag: $('#tabTag'),
    tabSimilar: $('#tabSimilar'),
    tabRelated: $('#tabRelated'),
    similarTagOptions: $('#similarTagOptions'),
    relatedOptions: $('#relatedOptions'),
    relatedBatch: $('#relatedBatch'),
    relatedStartBtn: $('#relatedStartBtn'),
    relatedNextBtn: $('#relatedNextBtn'),
    relatedNextTop: $('#relatedNextTop'),
    panelTag: $('#panelTag'),
    panelSimilar: $('#panelSimilar'),
    tagInput: $('#tagInput'),
    tagChips: $('#tagChips'),
    tagPresets: $('#tagPresets'),
    idInput: $('#idInput'),
    idChips: $('#idChips'),
    idNote: $('#idNote'),
    includeRelated: $('#includeRelated'),
    seedTagLimit: $('#seedTagLimit'),
    r18Toggle: $('#r18Toggle'),
    sortSelect: $('#sortSelect'),
    limitSelect: $('#limitSelect'),
    pagesSelect: $('#pagesSelect'),
    bookmarkInput: $('#bookmarkInput'),
    concurrencyInput: $('#concurrencyInput'),
    concurrencyOut: $('#concurrencyOut'),
    skipExisting: $('#skipExisting'),
    scanBtn: $('#scanBtn'),
    scanState: $('#scanState'),
    resultSummary: $('#resultSummary'),
    wsTitle: $('#wsTitle'),
    seedNote: $('#seedNote'),
    selectAllWrap: $('#selectAllWrap'),
    selectAll: $('#selectAll'),
    selectAllLabel: $('#selectAllLabel'),
    saveSearchBtn: $('#saveSearchBtn'),
    savedRow: $('#savedRow'),
    savedChips: $('#savedChips'),
    seedPreview: $('#seedPreview'),
    seedGrid: $('#seedGrid'),
    seedPreviewState: $('#seedPreviewState'),
    aiScanToggle: $('#aiScanToggle'),
    aiScanStatus: $('#aiScanStatus'),
    aiScanStopBtn: $('#aiScanStopBtn'),
    scanMetrics: $('#scanMetrics'),
    scanBatchValue: $('#scanBatchValue'),
    scanDownloadValue: $('#scanDownloadValue'),
    scanHitValue: $('#scanHitValue'),
    scanProgressValue: $('#scanProgressValue'),
    scanFolderRow: $('#scanFolderRow'),
    openScanFolderBtn: $('#openScanFolderBtn'),
    scanSessionHint: $('#scanSessionHint'),
    scanPanel: $('#scanPanel'),
    scanPanelSummary: $('#scanPanelSummary'),
    scanBackBtn: $('#scanBackBtn'),
    scanBarFill: $('#scanBarFill'),
    scanProgressText: $('#scanProgressText'),
    scanSpeedText: $('#scanSpeedText'),
    scanHits: $('#scanHits'),
    scanHitsEmpty: $('#scanHitsEmpty'),
    scanHitHint: $('#scanHitHint'),
    scanLogWrap: $('#scanLogWrap'),
    scanLog: $('#scanLog'),
    scanBatchSelect: $('#scanBatchSelect'),
    scanHistoryBtn: $('#scanHistoryBtn'),
    networkBtn: $('#networkBtn'),
    settingsDialog: $('#settingsDialog'),
    settingsClose: $('#settingsClose'),
    proxyMode: $('#proxyMode'),
    proxyUrl: $('#proxyUrl'),
    runSpeedtestBtn: $('#runSpeedtestBtn'),
    speedtestStatus: $('#speedtestStatus'),
    speedResults: $('#speedResults'),
    downloadTimeout: $('#downloadTimeout'),
    apiInterval: $('#apiInterval'),
    defaultBatch: $('#defaultBatch'),
    maxBatches: $('#maxBatches'),
    maxDisk: $('#maxDisk'),
    notifyHits: $('#notifyHits'),
    saveSettingsBtn: $('#saveSettingsBtn'),
    settingsStatus: $('#settingsStatus'),
    historyDialog: $('#historyDialog'),
    historyClose: $('#historyClose'),
    historySessions: $('#historySessions'),
    historyDetail: $('#historyDetail'),
    historyBackBtn: $('#historyBackBtn'),
    historySummary: $('#historySummary'),
    historySearch: $('#historySearch'),
    historyLevel: $('#historyLevel'),
    historyExportCsv: $('#historyExportCsv'),
    historyExportJson: $('#historyExportJson'),
    historyOpenFolder: $('#historyOpenFolder'),
    historyHits: $('#historyHits'),
    historyEmpty: $('#historyEmpty'),
    historyMore: $('#historyMore'),
    historyCount: $('#historyCount'),
    cardMenu: $('#cardMenu'),
    retryFailedBtn: $('#retryFailedBtn'),
    emptyState: $('#emptyState'),
    grid: $('#grid'),
    dock: $('#dock'),
    speedValue: $('#speedValue'),
    speedPages: $('#speedPages'),
    speedWorks: $('#speedWorks'),
    speedEta: $('#speedEta'),
    spark: $('#spark'),
    sparkNote: $('#sparkNote'),
    barFill: $('#barFill'),
    pageCounter: $('#pageCounter'),
    byteCounter: $('#byteCounter'),
    downloadBtn: $('#downloadBtn'),
    cancelBtn: $('#cancelBtn'),
    openOutputBtn: $('#openOutputBtn'),
    openOutputTop: $('#openOutputTop'),
    currentList: $('#currentList'),
    logWrap: $('#logWrap'),
    jobLog: $('#jobLog'),
    toast: $('#toast'),
  };

  const WORK_TYPES = new Set(['manga', 'illust', 'all']);
  const SORTS = new Set(['date', 'popular']);
  const SAVED_KEY = 'pixiv-collector-saved-searches';
  const GENERIC_TAGS = new Set([
    'イラスト', 'オリジナル', '漫画', 'マンガ', '插画', '原创', '原创插画',
    'r-18', 'r18', 'r-18g', 'r18g', '女の子', '男の子', '女の子一人', '男の子一人',
    'ai生成', 'ai', 'aiイラスト', 'ai-generated', '健全', '全年齢', 'pixiv',
    'ファンボックス', 'fanbox', '落書き', 'らくがき', 'キャラクター', 'アニメ',
    'クリスタ', 'clip studio', 'sai', 'photoshop', 'procreate', 'アナログ', 'デジタル',
  ]);

  const state = {
    connected: false,
    user: null,
    mode: 'tag',
    relatedSession: null,
    relatedBatchNo: 0,
    relatedExhausted: false,
    relatedBusy: false,
    nextBusy: false,
    tagCursor: '',
    itemsMode: 'tag',
    library: {
      items: [],
      total: 0,
      offset: 0,
      limit: 60,
      loading: false,
      viewer: null,
      page: 0,
      timer: null,
    },
    tags: [],
    ids: [],
    items: [],
    picked: new Map(),
    scanning: false,
    job: null,
    jobId: null,
    pollTimer: null,
    pollFailures: 0,
    outputDir: '',
    sparkPoints: [],
    toastTimer: null,
    saved: [],
    resultSummaryText: '还没有结果',
    extractSession: null,
    extractUrl: '',
    extractCreatedAt: 0,
    autoLoginSession: null,
    autoLoginTimer: null,
    apiToken: '',
    settings: null,
    menuItem: null,
    history: {
      session: null,
      offset: 0,
      total: 0,
      items: [],
      query: '',
      level: '',
      expanded: new Set(),
      details: new Map(),
      timer: null,
    },
    seedCache: new Map(),
    seedTimer: null,
    seedError: '',
    seedFetchSeq: 0,
    scan: {
      id: null,
      timer: null,
      snapshot: null,
      view: false,
      starting: false,
      lastHits: 0,
      lastHitKey: '',
      expanded: new Set(),
      hitDetails: new Map(),
    },
  };

  /* ── 基础工具 ───────────────────────────────────── */

  function loadSettings() {
    let saved = {};
    try {
      saved = JSON.parse(localStorage.getItem('pixiv-collector-settings') || '{}') || {};
    } catch { saved = {}; }
    if (saved.r18 === true) els.r18Toggle.checked = true;
    if (WORK_TYPES.has(saved.workType)) {
      const radio = document.querySelector(`input[name="workType"][value="${saved.workType}"]`);
      if (radio) radio.checked = true;
    }
    if (SORTS.has(saved.sort)) els.sortSelect.value = saved.sort;
    ['limit', 'pages', 'bookmark'].forEach((key) => {
      const map = { limit: els.limitSelect, pages: els.pagesSelect, bookmark: els.bookmarkInput };
      const el = map[key];
      if (saved[key] !== undefined && el) {
        if (key === 'bookmark') el.value = String(saved[key]);
        else if (Array.from(el.options).some((o) => o.value === String(saved[key]))) el.value = String(saved[key]);
      }
    });
    if (Number.isInteger(saved.concurrency) && saved.concurrency >= 1 && saved.concurrency <= 8) {
      els.concurrencyInput.value = String(saved.concurrency);
    }
    if (typeof saved.includeRelated === 'boolean') els.includeRelated.checked = saved.includeRelated;
    if (saved.seedTagLimit && Array.from(els.seedTagLimit.options).some((o) => o.value === String(saved.seedTagLimit))) {
      els.seedTagLimit.value = String(saved.seedTagLimit);
    }
    if (typeof saved.skipExisting === 'boolean') els.skipExisting.checked = saved.skipExisting;
    if (saved.relatedBatch && Array.from(els.relatedBatch.options).some((o) => o.value === String(saved.relatedBatch))) {
      els.relatedBatch.value = String(saved.relatedBatch);
    }
    if (Array.isArray(saved.tags)) state.tags = saved.tags.filter((t) => typeof t === 'string').slice(0, 20);
    if (typeof saved.mode === 'string' && (saved.mode === 'tag' || saved.mode === 'similar' || saved.mode === 'related')) setMode(saved.mode, false);
    renderTags();
    syncConcurrency();
  }

  function saveSettings() {
    try {
      localStorage.setItem('pixiv-collector-settings', JSON.stringify({
        r18: els.r18Toggle.checked,
        workType: document.querySelector('input[name="workType"]:checked')?.value || 'manga',
        sort: els.sortSelect.value,
        limit: els.limitSelect.value,
        pages: els.pagesSelect.value,
        bookmark: els.bookmarkInput.value,
        concurrency: Number(els.concurrencyInput.value),
        includeRelated: els.includeRelated.checked,
        seedTagLimit: els.seedTagLimit.value,
        skipExisting: els.skipExisting.checked,
        tags: state.tags,
        mode: state.mode,
        relatedBatch: els.relatedBatch.value,
      }));
    } catch { /* 隐私模式忽略 */ }
  }

  function getWorkType() {
    return document.querySelector('input[name="workType"]:checked')?.value || 'manga';
  }

  function showToast(text, tone = 'info') {
    els.toast.textContent = text;
    els.toast.dataset.tone = tone;
    els.toast.hidden = false;
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => { els.toast.hidden = true; }, 3200);
  }

  function setScanState(text, tone = '') {
    els.scanState.textContent = text;
    if (tone) els.scanState.dataset.tone = tone;
    else delete els.scanState.dataset.tone;
  }

  function syncConcurrency() {
    els.concurrencyOut.textContent = els.concurrencyInput.value;
  }

  async function api(path, options = {}) {
    const init = { method: 'GET', headers: {}, ...options };
    if (state.apiToken) init.headers['X-API-Token'] = state.apiToken;
    if (init.body && typeof init.body !== 'string') {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(init.body);
    }
    let res;
    try {
      res = await fetch(path, init);
    } catch (err) {
      throw new Error('无法连接本地服务，请确认 server.py 正在运行');
    }
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : {}; } catch {
      throw new Error(`服务返回了非 JSON 内容（HTTP ${res.status}）`);
    }
    if (!res.ok || data.ok === false) {
      throw new Error(data.error || `请求失败（HTTP ${res.status}）`);
    }
    return data;
  }

  function humanBytes(bytes) {
    const n = Number(bytes) || 0;
    if (n < 1024) return `${Math.round(n)} B`;
    const units = ['KB', 'MB', 'GB', 'TB'];
    let v = n / 1024;
    let i = 0;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
    return `${v.toFixed(v >= 100 ? 0 : v >= 10 ? 1 : 2)} ${units[i]}`;
  }

  function formatEta(seconds) {
    const s = Number(seconds);
    if (!Number.isFinite(s) || s < 0) return '剩余时间未知';
    if (s < 60) return `剩余约 ${Math.ceil(s)} 秒`;
    const m = Math.floor(s / 60);
    const rest = Math.round(s % 60);
    if (m < 60) return `剩余约 ${m} 分 ${rest} 秒`;
    return `剩余约 ${Math.floor(m / 60)} 时 ${m % 60} 分`;
  }

  function formatCount(n) {
    const v = Number(n) || 0;
    if (v >= 10000) return `${(v / 10000).toFixed(1)} 万`;
    return String(v);
  }

  /* ── 账号连接 ───────────────────────────────────── */

  function renderAccount() {
    if (state.connected && state.user) {
      els.account.dataset.state = 'online';
      els.accountName.textContent = state.user.name || state.user.account || '已连接';
      els.accountName.title = `@${state.user.account || ''}`;
      els.connectNote.textContent = `已连接 ${state.user.name || ''}。密钥只留在本机内存中。`;
      els.connectNote.dataset.tone = 'ok';
      els.connectBtn.textContent = '重新连接';
      setScanState('账号已就绪，可以开始扫描。');
    } else {
      els.account.dataset.state = 'offline';
      els.accountName.textContent = '未连接';
      els.accountName.title = '';
      els.connectNote.textContent = '密钥仅保存在本机，不会上传到任何第三方。';
      delete els.connectNote.dataset.tone;
      els.connectBtn.textContent = '连接账号';
    }
    updateDownloadButton();
  }

  async function connect() {
    const token = els.tokenInput.value.trim();
    if (!token) {
      els.connectNote.textContent = '请先填入 refresh_token。';
      els.connectNote.dataset.tone = 'error';
      els.tokenInput.focus();
      return;
    }
    els.connectBtn.disabled = true;
    const oldText = els.connectBtn.textContent;
    els.connectBtn.textContent = '连接中';
    els.connectNote.textContent = '正在验证通行密钥…';
    delete els.connectNote.dataset.tone;
    try {
      const data = await api('/api/connect', {
        method: 'POST',
        body: { refresh_token: token, remember: els.rememberKey.checked },
      });
      state.connected = true;
      state.user = data.user || null;
      renderAccount();
      showToast(data.message || '连接成功');
    } catch (err) {
      state.connected = false;
      state.user = null;
      renderAccount();
      els.connectNote.textContent = err.message;
      els.connectNote.dataset.tone = 'error';
      els.account.dataset.state = 'error';
      els.accountName.textContent = '连接失败';
      showToast(err.message, 'error');
    } finally {
      els.connectBtn.disabled = false;
      els.connectBtn.textContent = state.connected ? '重新连接' : oldText;
      updateDownloadButton();
    }
  }

  /* ── 通行密钥提取 ───────────────────────────────── */

  function setExtractStatus(text, tone = '') {
    els.extractStatus.textContent = text;
    if (tone) els.extractStatus.dataset.tone = tone;
    else delete els.extractStatus.dataset.tone;
  }

  function setAutoLoginStatus(text, tone = '') {
    els.autoLoginStatus.textContent = text;
    if (tone) els.autoLoginStatus.dataset.tone = tone;
    else delete els.autoLoginStatus.dataset.tone;
  }

  function stopAutoPolling(cancel = false) {
    if (state.autoLoginTimer) {
      clearInterval(state.autoLoginTimer);
      state.autoLoginTimer = null;
    }
    const session = state.autoLoginSession;
    state.autoLoginSession = null;
    if (cancel && session) {
      api('/api/token/extract/auto/cancel', {
        method: 'POST',
        body: { session_id: session },
      }).catch(() => {});
    }
  }

  async function pollAutoLogin() {
    const session = state.autoLoginSession;
    if (!session) return;
    try {
      const data = await api(`/api/token/extract/auto/status?session_id=${encodeURIComponent(session)}`);
      if (state.autoLoginSession !== session) return;
      if (data.state === 'running') return;
      if (state.autoLoginTimer) {
        clearInterval(state.autoLoginTimer);
        state.autoLoginTimer = null;
      }
      state.autoLoginSession = null;
      if (data.state === 'done' && data.refresh_token) {
        els.tokenInput.value = data.refresh_token;
        els.keySource.textContent = '一键登录提取的密钥';
        els.keySource.title = '';
        els.autoLoginBtn.disabled = false;
        els.autoLoginBtn.textContent = '打开登录窗口';
        setAutoLoginStatus(data.message || '已提取通行密钥', 'ok');
        closeExtractDialog();
        showToast(data.message || '通行密钥已提取');
        await connect();
        return;
      }
      els.autoLoginBtn.disabled = false;
      els.autoLoginBtn.textContent = '重新打开登录窗口';
      setAutoLoginStatus(data.error || '登录没有完成，请重试', 'error');
    } catch (err) {
      stopAutoPolling(false);
      els.autoLoginBtn.disabled = false;
      els.autoLoginBtn.textContent = '打开登录窗口';
      setAutoLoginStatus(err.message, 'error');
    }
  }

  async function startAutoLogin() {
    stopAutoPolling(true);
    els.autoLoginBtn.disabled = true;
    els.autoLoginBtn.textContent = '正在打开…';
    setAutoLoginStatus('正在启动内置登录窗口…');
    try {
      const data = await api('/api/token/extract/auto/start', { method: 'POST', body: {} });
      state.autoLoginSession = data.session_id;
      els.autoLoginBtn.textContent = '登录窗口已打开';
      setAutoLoginStatus('登录窗口已打开；完成登录后会自动提取，不用按 F12。');
      state.autoLoginTimer = setInterval(pollAutoLogin, 1000);
      pollAutoLogin();
    } catch (err) {
      els.autoLoginBtn.disabled = false;
      els.autoLoginBtn.textContent = '打开登录窗口';
      setAutoLoginStatus(err.message || '无法打开内置登录窗口', 'error');
    }
  }

  async function startExtractSession(openInBrowser) {
    try {
      const data = await api('/api/token/extract/start', { method: 'POST', body: {} });
      state.extractSession = data.session_id;
      state.extractUrl = data.login_url;
      state.extractCreatedAt = Date.now();
      els.extractLoginLink.href = data.login_url;
      els.extractLoginLink.hidden = false;
      if (openInBrowser) {
        const win = window.open(data.login_url, '_blank');
        if (win) win.opener = null;
      }
      return true;
    } catch (err) {
      setExtractStatus(err.message, 'error');
      return false;
    }
  }

  function openExtractDialog() {
    els.extractStatus.textContent = '';
    els.extractCode.value = '';
    els.extractLoginLink.hidden = true;
    if (!state.autoLoginSession) {
      els.autoLoginBtn.disabled = false;
      els.autoLoginBtn.textContent = '打开登录窗口';
      setAutoLoginStatus('');
    } else {
      els.autoLoginBtn.disabled = true;
      els.autoLoginBtn.textContent = '登录窗口已打开';
    }
    if (typeof els.keyDialog.showModal === 'function') els.keyDialog.showModal();
    else els.keyDialog.setAttribute('open', '');
    refreshTokenSources();
    const fresh = state.extractSession && Date.now() - state.extractCreatedAt < 15 * 60 * 1000;
    if (fresh) {
      els.extractLoginLink.href = state.extractUrl;
      els.extractLoginLink.hidden = false;
    } else {
      state.extractSession = null;
      startExtractSession(false);
    }
  }

  function closeExtractDialog() {
    stopAutoPolling(true);
    try {
      els.keyDialog.close();
    } catch {
      els.keyDialog.removeAttribute('open');
    }
  }

  async function openPixivLogin() {
    setExtractStatus('正在生成授权链接…');
    if (!state.extractSession) {
      const ok = await startExtractSession(false);
      if (!ok) return;
    }
    const win = window.open(state.extractUrl, '_blank');
    if (win) win.opener = null;
    if (!win) {
      setExtractStatus('浏览器拦截了新窗口，请点「手动打开授权链接」。', 'error');
    } else {
      setExtractStatus('已打开登录页；登录后把回调 URL 或 code 粘贴到下面。');
    }
  }

  async function pasteExtractCode() {
    try {
      const text = await navigator.clipboard.readText();
      if (!text) {
        showToast('剪贴板是空的');
        return;
      }
      els.extractCode.value = text.trim();
      setExtractStatus('已从剪贴板读取，点「提取通行密钥」。');
    } catch {
      showToast('浏览器不允许读取剪贴板，请手动粘贴', 'error');
      els.extractCode.focus();
    }
  }

  async function finishExtract() {
    const code = els.extractCode.value.trim();
    if (!code) {
      setExtractStatus('请先粘贴授权码或回调 URL', 'error');
      els.extractCode.focus();
      return;
    }
    if (!state.extractSession) {
      const ok = await startExtractSession(false);
      if (!ok) return;
    }
    els.extractFinishBtn.disabled = true;
    setExtractStatus('正在向 Pixiv 换取通行密钥…');
    try {
      const data = await api('/api/token/extract/finish', {
        method: 'POST',
        body: { session_id: state.extractSession, code },
      });
      state.extractSession = null;
      els.tokenInput.value = data.refresh_token || '';
      els.extractCode.value = '';
      els.keySource.textContent = '已提取的密钥';
      els.keySource.title = '';
      closeExtractDialog();
      showToast(data.message || '通行密钥已提取');
      await connect();
    } catch (err) {
      state.extractSession = null;
      setExtractStatus(`${err.message} 已生成新的授权链接，请重新登录后再试。`, 'error');
      startExtractSession(false);
    } finally {
      els.extractFinishBtn.disabled = false;
    }
  }

  async function refreshTokenSources() {
    els.keySourceList.textContent = '扫描中…';
    try {
      const data = await api('/api/token/sources');
      renderTokenSources(Array.isArray(data.items) ? data.items : []);
    } catch (err) {
      els.keySourceList.textContent = `扫描失败：${err.message}`;
    }
  }

  function renderTokenSources(items) {
    els.keySourceList.textContent = '';
    if (!items.length) {
      const empty = document.createElement('p');
      empty.className = 'key-source-empty';
      empty.textContent = '没有找到可导入的密钥缓存；可以先用上面的登录页提取。';
      els.keySourceList.appendChild(empty);
      return;
    }
    items.forEach((item) => {
      const row = document.createElement('div');
      row.className = 'key-source';
      const meta = document.createElement('div');
      meta.className = 'key-source-meta';
      const title = document.createElement('span');
      title.className = 'key-source-title';
      const kind = item.kind || '密钥文件';
      title.textContent = `${kind}${item.account ? ` · ${item.account}` : ''} · ${item.masked || '…'}`;
      const path = document.createElement('span');
      path.className = 'key-source-path';
      path.textContent = item.source || '';
      path.title = item.source || '';
      meta.append(title, path);
      const use = document.createElement('button');
      use.type = 'button';
      use.className = 'btn btn-outline btn-sm';
      use.textContent = '使用';
      use.addEventListener('click', () => useImportedToken(item));
      row.append(meta, use);
      els.keySourceList.appendChild(row);
    });
  }

  function useImportedToken(item) {
    if (!item || !item.refresh_token) return;
    els.tokenInput.value = item.refresh_token;
    els.keySource.textContent = '已导入的密钥';
    els.keySource.title = item.source || '';
    closeExtractDialog();
    showToast(`已导入 ${item.kind || '本机'} 的通行密钥，正在连接…`);
    connect();
  }

  /* ── 历史扫描 ─────────────────────────────────── */

  function closeHistoryDialog() {
    try {
      els.historyDialog.close();
    } catch {
      els.historyDialog.removeAttribute('open');
    }
    els.historyDetail.hidden = true;
    els.historySessions.hidden = false;
    els.historyHits.textContent = '';
    els.historyEmpty.hidden = false;
    state.history.session = null;
    state.history.items = [];
    state.history.details.clear();
    state.history.expanded.clear();
  }

  async function openHistoryDialog() {
    if (typeof els.historyDialog.showModal === 'function') els.historyDialog.showModal();
    else els.historyDialog.setAttribute('open', '');
    els.historyDetail.hidden = true;
    els.historySessions.hidden = false;
    els.historySearch.value = '';
    els.historyLevel.value = '';
    await loadHistorySessions();
  }

  async function loadHistorySessions() {
    els.historySessions.textContent = '读取中…';
    try {
      const data = await api('/api/scan/history');
      renderHistorySessions(data.sessions || []);
    } catch (err) {
      els.historySessions.textContent = `读取失败：${err.message}`;
    }
  }

  function renderHistorySessions(sessions) {
    els.historySessions.textContent = '';
    if (!sessions.length) {
      const empty = document.createElement('p');
      empty.className = 'key-source-empty';
      empty.textContent = '还没有历史扫描记录。';
      els.historySessions.appendChild(empty);
      return;
    }
    sessions.forEach((session) => {
      const row = document.createElement('div');
      row.className = 'history-session';
      const meta = document.createElement('div');
      meta.className = 'history-session-meta';
      const title = document.createElement('span');
      title.className = 'history-session-title';
      const stats = session.stats || {};
      title.textContent = `${session.started_at || session.session} · 命中 ${stats.hits || 0} / 下载 ${stats.downloaded || 0}`;
      const sub = document.createElement('span');
      sub.className = 'history-session-sub';
      sub.textContent = `${session.session} · ${session.mode === 'similar' ? '按作品找相似' : '按标签搜索'} · 每批 ${session.batch_size || '?'} 个 · ${session.state || ''}`;
      meta.append(title, sub);
      const actions = document.createElement('div');
      actions.className = 'key-dialog-actions';
      const view = document.createElement('button');
      view.type = 'button';
      view.className = 'btn btn-outline btn-sm';
      view.textContent = '查看命中';
      view.addEventListener('click', () => openHistorySession(session));
      const folder = document.createElement('button');
      folder.type = 'button';
      folder.className = 'btn btn-quiet btn-sm';
      folder.textContent = '打开文件夹';
      folder.addEventListener('click', () => openScanSubdir(`AI元数据扫描/${session.session}`));
      actions.append(view, folder);
      row.append(meta, actions);
      els.historySessions.appendChild(row);
    });
  }

  function openHistorySession(session) {
    state.history.session = session.session;
    state.history.items = [];
    state.history.offset = 0;
    state.history.total = 0;
    state.history.expanded.clear();
    state.history.details.clear();
    els.historySessions.hidden = true;
    els.historyDetail.hidden = false;
    els.historySearch.value = '';
    els.historyLevel.value = '';
    const stats = session.stats || {};
    els.historySummary.textContent = `${session.started_at || session.session} · 命中 ${stats.hits || 0} 个 · 检查 ${stats.inspected || 0} 个`;
    loadHistoryHits(true);
  }

  function showHistoryList() {
    els.historyDetail.hidden = true;
    els.historySessions.hidden = false;
    state.history.session = null;
    loadHistorySessions();
  }

  async function loadHistoryHits(reset) {
    const session = state.history.session;
    if (!session) return;
    if (reset) {
      state.history.offset = 0;
      state.history.items = [];
      state.history.expanded.clear();
      state.history.details.clear();
    }
    state.history.query = els.historySearch.value.trim();
    state.history.level = els.historyLevel.value;
    const params = new URLSearchParams({
      offset: String(state.history.offset),
      limit: '20',
      q: state.history.query,
      level: state.history.level,
    });
    els.historyMore.disabled = true;
    try {
      const data = await api(`/api/scan/history/${encodeURIComponent(session)}/hits?${params.toString()}`);
      state.history.total = data.total || 0;
      const items = data.items || [];
      state.history.items = reset ? items : state.history.items.concat(items);
      state.history.offset = state.history.items.length;
      els.historySummary.textContent = `${data.report?.started_at || session} · 命中 ${data.total || 0} 个` +
        ` · 检查 ${data.report?.stats?.inspected || 0} 个`;
      renderHistoryHits();
    } catch (err) {
      showToast(`读取历史命中失败：${err.message}`, 'error');
    } finally {
      els.historyMore.disabled = false;
    }
  }

  function renderHistoryHits() {
    const items = state.history.items;
    els.historyHits.textContent = '';
    items.forEach((hit) => {
      const card = document.createElement('article');
      card.className = 'scan-hit';
      const thumb = document.createElement('a');
      thumb.className = 'scan-hit-thumb';
      thumb.href = `https://www.pixiv.net/artworks/${hit.id}`;
      thumb.target = '_blank';
      thumb.rel = 'noopener noreferrer';
      if (hit.thumb_url) {
        const img = document.createElement('img');
        img.loading = 'lazy';
        img.alt = '';
        img.src = hit.thumb_url;
        thumb.appendChild(img);
      }
      const body = document.createElement('div');
      body.className = 'scan-hit-body';
      const title = document.createElement('a');
      title.className = 'scan-hit-title';
      title.href = `https://www.pixiv.net/artworks/${hit.id}`;
      title.target = '_blank';
      title.rel = 'noopener noreferrer';
      title.textContent = hit.title || `作品 ${hit.id}`;
      const meta = document.createElement('p');
      meta.className = 'scan-hit-meta';
      const author = document.createElement('span');
      author.textContent = hit.author?.name || '未知作者';
      const batch = document.createElement('span');
      batch.textContent = `第 ${hit.batch || '?'} 批`;
      const exposure = document.createElement('span');
      exposure.textContent = `暴露 ${hit.exposure?.level || '?'}`;
      meta.append(author, batch, exposure);
      const summary = document.createElement('p');
      summary.className = 'scan-hit-exposure';
      summary.textContent = hit.exposure?.summary || '';
      const details = document.createElement('details');
      details.className = 'scan-exposure';
      const detailSummary = document.createElement('summary');
      const fieldCount = Number(hit.field_count) || (hit.field_keys || []).length;
      detailSummary.textContent = `展开暴露的数据（${fieldCount} 个字段）`;
      const detailBody = document.createElement('div');
      detailBody.className = 'exposure-body';
      detailBody.textContent = '展开后加载…';
      details.append(detailSummary, detailBody);
      details.addEventListener('toggle', () => {
        if (details.open) {
          state.history.expanded.add(hit.id);
          loadHistoryHitDetail(hit.id, detailBody);
        } else {
          state.history.expanded.delete(hit.id);
        }
      });
      const actions = document.createElement('div');
      actions.className = 'scan-hit-actions';
      const detail = document.createElement('a');
      detail.href = `https://www.pixiv.net/artworks/${hit.id}`;
      detail.target = '_blank';
      detail.rel = 'noopener noreferrer';
      detail.textContent = '详细页';
      const folder = document.createElement('button');
      folder.type = 'button';
      folder.textContent = '打开作品文件夹';
      folder.addEventListener('click', () => openScanSubdir(hit.dir));
      actions.append(detail, folder);
      body.append(title, meta, summary, details, actions);
      card.append(thumb, body);
      els.historyHits.appendChild(card);
      if (state.history.expanded.has(hit.id)) {
        details.open = true;
        loadHistoryHitDetail(hit.id, detailBody);
      }
    });
    els.historyEmpty.hidden = items.length > 0;
    if (!items.length) {
      els.historyEmpty.textContent = state.history.query || state.history.level
        ? '没有匹配的命中作品。'
        : '这个会话没有命中作品。';
    }
    els.historyMore.hidden = state.history.items.length >= state.history.total;
    els.historyCount.textContent = state.history.total
      ? `已显示 ${state.history.items.length} / ${state.history.total}`
      : '';
  }

  async function loadHistoryHitDetail(hitId, container) {
    const cached = state.history.details.get(hitId);
    if (cached) {
      renderHitExposure(container, cached);
      return;
    }
    if (container.dataset.loading === '1') return;
    container.dataset.loading = '1';
    container.textContent = '读取中…';
    const session = state.history.session;
    if (!session) return;
    try {
      const data = await api(`/api/scan/history/${encodeURIComponent(session)}/hit/${hitId}`);
      state.history.details.set(hitId, data.hit);
      renderHitExposure(container, data.hit);
    } catch (err) {
      container.textContent = `读取失败：${err.message}`;
    } finally {
      container.dataset.loading = '0';
    }
  }

  async function exportHistory(format) {
    const session = state.history.session;
    if (!session) return;
    try {
      const data = await api(`/api/scan/history/${encodeURIComponent(session)}/export?format=${format}`);
      const blob = new Blob([data.content || ''], { type: data.content_type || 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = data.filename || `scan-hits.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (err) {
      showToast(`导出失败：${err.message}`, 'error');
    }
  }

  function openHistoryFolder() {
    const session = state.history.session;
    if (session) openScanSubdir(`AI元数据扫描/${session}`);
  }

  /* ── 下载库 ─────────────────────────────────────── */

  function librarySourceLabel(source) {
    return { download: '普通下载', scan: 'AI 扫描', hit: '命中隔离' }[source] || source;
  }

  function libraryGroupTitle(item, group) {
    if (group === 'author') return item.author?.name || '未知作者';
    if (group === 'tag') return item.tags?.[0] || '未分类';
    if (group === 'month') return (item.downloaded_at || '').slice(0, 7) || '未知月份';
    if (group === 'source') return librarySourceLabel(item.source);
    if (group === 'hit') return item.hit ? '元数据命中' : '未命中';
    if (group === 'type') return item.type === 'manga' ? '漫画' : '插画';
    return '全部作品';
  }

  function populateLibrarySelect(select, values, placeholder) {
    if (!select) return;
    const current = select.value;
    select.textContent = '';
    const empty = document.createElement('option');
    empty.value = '';
    empty.textContent = placeholder;
    select.appendChild(empty);
    values.forEach((entry) => {
      const name = typeof entry === 'string' ? entry : entry.name;
      const count = typeof entry === 'string' ? null : entry.count;
      if (!name) return;
      const option = document.createElement('option');
      option.value = name;
      option.textContent = count != null ? `${name}（${count}）` : name;
      select.appendChild(option);
    });
    if (Array.from(select.options).some((option) => option.value === current)) {
      select.value = current;
    }
  }

  function renderLibraryFacets(facets) {
    const tags = facets?.tags || [];
    const authors = facets?.authors || [];
    const sessions = Object.keys(facets?.sessions || {});
    populateLibrarySelect(els.libTag, tags, '全部标签');
    populateLibrarySelect(els.libAuthor, authors, '全部作者');
    populateLibrarySelect(els.libSession, sessions, '全部会话');
  }

  function libraryQueryParams(force = false) {
    const params = new URLSearchParams();
    const values = {
      q: els.libSearch.value.trim(),
      source: els.libSource.value,
      type: els.libType.value,
      r18: els.libR18.value,
      hit: els.libHit.value,
      tag: els.libTag.value,
      author: els.libAuthor.value,
      session: els.libSession.value,
      sort: els.libSort.value,
      offset: String(state.library.offset),
      limit: String(state.library.limit),
    };
    Object.entries(values).forEach(([key, value]) => {
      if (value && value !== 'all') params.set(key, value);
    });
    if (force) params.set('refresh', '1');
    return params;
  }

  async function loadLibrary(reset = false, force = false) {
    if (state.library.loading) return;
    state.library.loading = true;
    if (reset) state.library.offset = 0;
    els.libSummary.textContent = '读取中…';
    els.libMore.disabled = true;
    try {
      const data = await api(`/api/library?${libraryQueryParams(force).toString()}`);
      const incoming = Array.isArray(data.items) ? data.items : [];
      if (reset) {
        state.library.items = incoming;
      } else {
        const existing = new Set(state.library.items.map((item) => `${item.dir}:${item.id}`));
        state.library.items = state.library.items.concat(
          incoming.filter((item) => !existing.has(`${item.dir}:${item.id}`)),
        );
      }
      state.library.total = Number(data.total) || 0;
      state.library.offset = state.library.items.length;
      renderLibraryFacets(data.facets || {});
      renderLibrary();
    } catch (err) {
      els.libSummary.textContent = `读取失败：${err.message}`;
    } finally {
      state.library.loading = false;
      els.libMore.disabled = false;
    }
  }

  function renderLibrary() {
    const items = state.library.items;
    const total = state.library.total;
    const hits = items.filter((item) => item.hit).length;
    const downloaded = items.filter((item) => item.source === 'download').length;
    const scanned = items.filter((item) => item.source === 'scan').length;
    const bytes = items.reduce((sum, item) => sum + (Number(item.bytes) || 0), 0);
    els.libSummary.textContent = total
      ? `共 ${total} 个作品 · 已加载 ${items.length} 个`
      : '没有找到作品';
    els.libStats.textContent = items.length
      ? `命中 ${hits} · 普通下载 ${downloaded} · 扫描 ${scanned} · 合计 ${humanBytes(bytes)}`
      : '';
    els.libGroups.textContent = '';

    if (!items.length) {
      els.libEmpty.hidden = false;
      els.libEmpty.textContent = total === 0 && !els.libSearch.value.trim()
        ? '下载库里还没有作品，先去抓取并下载一些吧。'
        : '没有符合当前筛选条件的作品。';
      els.libMore.hidden = true;
      return;
    }
    els.libEmpty.hidden = true;

    const groupMode = els.libGroup.value;
    const groups = new Map();
    items.forEach((item) => {
      const key = groupMode === 'none' ? '全部作品' : libraryGroupTitle(item, groupMode);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    });

    groups.forEach((groupItems, title) => {
      const section = document.createElement('section');
      section.className = 'library-group';
      const heading = document.createElement('h3');
      heading.className = 'library-group-title';
      heading.textContent = title;
      const count = document.createElement('span');
      count.className = 'hint';
      count.textContent = `${groupItems.length} 个`;
      heading.appendChild(count);
      const grid = document.createElement('div');
      grid.className = 'library-grid';
      groupItems.forEach((item) => grid.appendChild(createLibraryCard(item)));
      section.append(heading, grid);
      els.libGroups.appendChild(section);
    });
    els.libMore.hidden = items.length >= total;
  }

  function createLibraryCard(item) {
    const card = document.createElement('article');
    card.className = 'library-card';
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    card.setAttribute('aria-label', `查看 ${item.title}`);
    const cover = document.createElement('div');
    cover.className = 'library-card-cover';
    const img = document.createElement('img');
    img.loading = 'lazy';
    img.alt = '';
    img.src = item.cover || '';
    cover.appendChild(img);

    const badges = document.createElement('div');
    badges.className = 'library-card-badges';
    const source = document.createElement('span');
    source.className = 'library-badge';
    source.textContent = librarySourceLabel(item.source);
    badges.appendChild(source);
    if (item.hit) {
      const hit = document.createElement('span');
      hit.className = 'library-badge is-hit';
      hit.textContent = '命中';
      badges.appendChild(hit);
    }
    if (item.x_restrict > 0) {
      const r18 = document.createElement('span');
      r18.className = 'library-badge is-r18';
      r18.textContent = 'R-18';
      badges.appendChild(r18);
    }
    cover.appendChild(badges);

    const body = document.createElement('div');
    body.className = 'library-card-body';
    const title = document.createElement('div');
    title.className = 'library-card-title';
    title.textContent = item.title || `作品 ${item.id}`;
    const sub = document.createElement('div');
    sub.className = 'library-card-sub';
    sub.textContent = `${item.author?.name || '未知作者'} · ${item.page_count || item.images.length} 页`;
    const tags = document.createElement('div');
    tags.className = 'library-card-tags';
    (item.tags || []).slice(0, 3).forEach((tag) => {
      const chip = document.createElement('span');
      chip.textContent = tag;
      tags.appendChild(chip);
    });
    body.append(title, sub, tags);
    card.append(cover, body);
    card.addEventListener('click', () => openLibraryViewer(item));
    card.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' || ev.key === ' ') {
        ev.preventDefault();
        openLibraryViewer(item);
      }
    });
    return card;
  }

  function openLibraryViewer(item) {
    if (!item || !Array.isArray(item.images) || !item.images.length) return;
    state.library.viewer = item;
    state.library.page = 0;
    els.libViewer.hidden = false;
    els.libViewerTitle.textContent = item.title || `作品 ${item.id}`;
    els.libViewerMeta.textContent = `${item.author?.name || '未知作者'} · ${librarySourceLabel(item.source)} · ${item.images.length} 页`;
    els.libViewerTags.textContent = (item.tags || []).slice(0, 8).join(' · ');
    renderLibraryViewerThumbs();
    showLibraryPage(0);
  }

  function closeLibraryViewer() {
    els.libViewer.hidden = true;
    els.libViewerImg.removeAttribute('src');
    els.libViewerThumbs.textContent = '';
    state.library.viewer = null;
  }

  function renderLibraryViewerThumbs() {
    const item = state.library.viewer;
    if (!item) return;
    els.libViewerThumbs.textContent = '';
    item.images.forEach((image, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.setAttribute('aria-label', `第 ${index + 1} 页`);
      const img = document.createElement('img');
      img.loading = 'lazy';
      img.alt = '';
      img.src = image.thumb || image.url;
      button.appendChild(img);
      button.addEventListener('click', () => showLibraryPage(index));
      els.libViewerThumbs.appendChild(button);
    });
  }

  function showLibraryPage(index) {
    const item = state.library.viewer;
    if (!item) return;
    const page = Math.max(0, Math.min(index, item.images.length - 1));
    state.library.page = page;
    els.libViewerImg.src = item.images[page].url;
    els.libViewerCounter.textContent = `${page + 1} / ${item.images.length}`;
    els.libViewerPrev.disabled = page <= 0;
    els.libViewerNext.disabled = page >= item.images.length - 1;
    Array.from(els.libViewerThumbs.children).forEach((button, i) => {
      button.classList.toggle('is-active', i === page);
    });
    const active = els.libViewerThumbs.children[page];
    if (active && active.scrollIntoView) {
      active.scrollIntoView({ block: 'nearest', inline: 'center' });
    }
  }

  function openLibraryFolder() {
    const item = state.library.viewer;
    if (!item) return;
    api('/api/open-output', { method: 'POST', body: { subdir: item.dir } }).catch((err) => {
      showToast(err.message, 'error');
    });
  }

  function openLibraryPixiv() {
    const item = state.library.viewer;
    if (!item) return;
    window.open(`https://www.pixiv.net/artworks/${item.id}`, '_blank');
  }

  function openLibraryDialog() {
    closeLibraryViewer();
    if (typeof els.libraryDialog.showModal === 'function') els.libraryDialog.showModal();
    else els.libraryDialog.setAttribute('open', '');
    loadLibrary(true, true);
    els.libSearch.focus();
  }

  function closeLibraryDialog() {
    closeLibraryViewer();
    clearTimeout(state.library.timer);
    try {
      els.libraryDialog.close();
    } catch {
      els.libraryDialog.removeAttribute('open');
    }
  }

  /* ── 网络与设置 ─────────────────────────────────── */

  function formatSpeed(bps) {
    const value = Number(bps) || 0;
    if (value <= 0) return '0 B/s';
    if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(2)} MB/s`;
    if (value >= 1024) return `${(value / 1024).toFixed(1)} KB/s`;
    return `${Math.round(value)} B/s`;
  }

  function setSettingsStatus(text, tone = '') {
    els.settingsStatus.textContent = text;
    if (tone) els.settingsStatus.dataset.tone = tone;
    else delete els.settingsStatus.dataset.tone;
  }

  function applySettingsToUi(settings) {
    if (!settings) return;
    state.settings = settings;
    if (els.scanBatchSelect) {
      const batch = String(settings.scan_batch_size || 10);
      if (Array.from(els.scanBatchSelect.options).some((option) => option.value === batch)) {
        els.scanBatchSelect.value = batch;
      }
    }
  }

  function populateSettingsForm(settings) {
    const s = settings || state.settings || {};
    els.proxyMode.value = s.proxy_mode || 'system';
    els.proxyUrl.value = s.proxy_url || '';
    els.downloadTimeout.value = String(s.download_timeout || 25);
    els.apiInterval.value = String(s.api_min_interval ?? 0.35);
    els.defaultBatch.value = String(s.scan_batch_size || 10);
    els.maxBatches.value = String(s.scan_max_batches || 0);
    els.maxDisk.value = String(s.scan_max_disk_gb || 0);
    els.notifyHits.checked = s.notify_hits !== false;
    syncProxyInputState();
  }

  function syncProxyInputState() {
    els.proxyUrl.disabled = els.proxyMode.value !== 'custom';
  }

  async function openSettingsDialog() {
    clearSpeedResults();
    setSettingsStatus('');
    if (typeof els.settingsDialog.showModal === 'function') els.settingsDialog.showModal();
    else els.settingsDialog.setAttribute('open', '');
    try {
      const data = await api('/api/settings');
      populateSettingsForm(data.settings);
      if (data.settings) applySettingsToUi(data.settings);
    } catch (err) {
      setSettingsStatus(err.message, 'error');
    }
  }

  function closeSettingsDialog() {
    try {
      els.settingsDialog.close();
    } catch {
      els.settingsDialog.removeAttribute('open');
    }
  }

  async function saveSettingsFromForm() {
    setSettingsStatus('正在保存…');
    const payload = {
      proxy_mode: els.proxyMode.value,
      proxy_url: els.proxyUrl.value.trim(),
      download_timeout: Number(els.downloadTimeout.value) || 25,
      api_min_interval: Number(els.apiInterval.value) || 0,
      scan_batch_size: Number(els.defaultBatch.value) || 10,
      scan_max_batches: Number(els.maxBatches.value) || 0,
      scan_max_disk_gb: Number(els.maxDisk.value) || 0,
      notify_hits: els.notifyHits.checked,
    };
    try {
      const data = await api('/api/settings', { method: 'POST', body: payload });
      applySettingsToUi(data.settings);
      populateSettingsForm(data.settings);
      setSettingsStatus('设置已保存', 'ok');
      showToast('设置已保存');
    } catch (err) {
      setSettingsStatus(err.message, 'error');
    }
  }

  function clearSpeedResults() {
    els.speedResults.hidden = true;
    els.speedResults.textContent = '';
    els.speedtestStatus.textContent = '';
    delete els.speedtestStatus.dataset.tone;
  }

  function renderSpeedResults(data) {
    els.speedResults.hidden = false;
    els.speedResults.textContent = '';
    const entries = [
      ['direct', '直连', data.results && data.results.direct],
      ['current', '当前线路', data.results && data.results.current],
    ];
    entries.forEach(([key, label, result]) => {
      const card = document.createElement('div');
      card.className = 'speed-card';
      if (!result || (!result.ok && result.error)) card.classList.add('is-error');
      const title = document.createElement('h4');
      title.textContent = label;
      const big = document.createElement('div');
      big.className = 'speed-big';
      big.textContent = result && result.ok ? formatSpeed(result.speed_bps) : '失败';
      const lines = document.createElement('div');
      lines.className = 'speed-line';
      if (result) {
        const latency = result.latency_ms != null ? `${result.latency_ms} ms` : '—';
        lines.textContent = `延迟 ${latency} · 首字节 ${result.first_byte_ms != null ? `${result.first_byte_ms} ms` : '—'}`;
        if (result.ok && result.bytes) {
          lines.textContent += ` · 采样 ${(result.bytes / 1024).toFixed(0)} KB`;
        }
      }
      card.append(title, big, lines);
      if (result && result.error) {
        const error = document.createElement('p');
        error.className = 'speed-err';
        error.textContent = result.error;
        card.appendChild(error);
      }
      els.speedResults.appendChild(card);
    });
    els.speedtestStatus.textContent = `目标：${data.target || 'Pixiv'}`;
    delete els.speedtestStatus.dataset.tone;
  }

  async function runSpeedtest() {
    els.runSpeedtestBtn.disabled = true;
    els.speedtestStatus.textContent = '测试中，直连可能较慢…';
    clearSpeedResults();
    try {
      const data = await api('/api/network/speedtest', {
        method: 'POST',
        body: {
          proxy_mode: els.proxyMode.value,
          proxy_url: els.proxyUrl.value.trim(),
        },
      });
      renderSpeedResults(data);
    } catch (err) {
      els.speedtestStatus.textContent = err.message;
      els.speedtestStatus.dataset.tone = 'error';
    } finally {
      els.runSpeedtestBtn.disabled = false;
    }
  }

  function maybeRequestNotificationPermission() {
    if (!state.settings || state.settings.notify_hits === false) return;
    if (!('Notification' in window)) return;
    if (Notification.permission === 'default') {
      Notification.requestPermission().catch(() => {});
    }
  }

  function notifyHit(title) {
    if (!state.settings || state.settings.notify_hits === false) return;
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    try {
      new Notification('AI 元数据命中', { body: title || '发现带残留元数据的作品' });
    } catch { /* 忽略 */ }
  }

  /* ── 方向切换 ───────────────────────────────────── */

  function setMode(mode, persist = true) {
    if (mode !== 'tag' && mode !== 'similar' && mode !== 'related') return;
    state.mode = mode;
    const isTag = mode === 'tag';
    const isRelated = mode === 'related';
    els.tabTag.classList.toggle('is-active', isTag);
    els.tabSimilar.classList.toggle('is-active', mode === 'similar');
    els.tabRelated.classList.toggle('is-active', isRelated);
    els.tabTag.setAttribute('aria-selected', String(isTag));
    els.tabSimilar.setAttribute('aria-selected', String(mode === 'similar'));
    els.tabRelated.setAttribute('aria-selected', String(isRelated));
    els.panelTag.hidden = !isTag;
    els.panelSimilar.hidden = isTag;
    els.similarTagOptions.hidden = isRelated;
    els.relatedOptions.hidden = !isRelated;
    els.scanBtn.hidden = isRelated;
    els.relatedStartBtn.hidden = !isRelated;
    updateNextButton();
    if (els.idNote) {
      els.idNote.textContent = isRelated
        ? '从种子作品的相关推荐开始，一层层往下找；每次「下一批」继续抓没出现过的作品。'
        : '从 2 到 10 个作品里提取画风标签，再按标签相似度寻找同风格作品。';
    }
    if (isTag) {
      els.seedNote.hidden = true;
      els.seedNote.textContent = '';
    }
    updateCardHints();
    if (isTag) renderSeedPreview();
    else scheduleSeedPreview();
    updateSaveButton();
    if (persist) saveSettings();
  }

  function bindTabs() {
    const tabs = [els.tabTag, els.tabSimilar, els.tabRelated];
    const modes = ['tag', 'similar', 'related'];
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => setMode(modes[index]));
      tab.addEventListener('keydown', (ev) => {
        if (ev.key !== 'ArrowLeft' && ev.key !== 'ArrowRight') return;
        ev.preventDefault();
        const next = tabs[(index + (ev.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
        next.focus();
        next.click();
      });
    });
  }

  /* ── 标签输入 ───────────────────────────────────── */

  function parseTagText(text) {
    return String(text)
      .split(/[,，、\n]+/)
      .map((t) => t.trim())
      .filter(Boolean);
  }

  function addTags(raw) {
    const incoming = Array.isArray(raw) ? raw : parseTagText(raw);
    let count = 0;
    incoming.forEach((tag) => {
      const clean = String(tag).trim().slice(0, 60);
      if (!clean) return;
      if (state.tags.some((t) => t.toLowerCase() === clean.toLowerCase())) return;
      if (state.tags.length >= 20) return;
      state.tags.push(clean);
      count += 1;
    });
    if (count > 0) {
      renderTags();
      saveSettings();
    }
    return count;
  }

  function removeTag(tag) {
    state.tags = state.tags.filter((t) => t !== tag);
    renderTags();
    saveSettings();
  }

  function renderTags() {
    els.tagChips.textContent = '';
    state.tags.forEach((tag) => {
      const chip = document.createElement('span');
      chip.className = 'chip';
      const label = document.createElement('span');
      label.textContent = tag;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('aria-label', `移除标签 ${tag}`);
      btn.textContent = '×';
      btn.addEventListener('click', () => removeTag(tag));
      chip.append(label, btn);
      els.tagChips.appendChild(chip);
    });
    updateSaveButton();
  }

  function renderPresets() {
    const presets = ['漫画', '厚塗り', '水彩', 'モノクロ', 'ちびキャラ', '背景'];
    els.tagPresets.textContent = '';
    presets.forEach((tag) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = `+ ${tag}`;
      btn.addEventListener('click', () => {
        if (addTags([tag])) els.tagInput.focus();
      });
      els.tagPresets.appendChild(btn);
    });
  }

  function bindTagInput() {
    els.tagInput.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' || ev.key === ',' || ev.key === '，') {
        ev.preventDefault();
        const value = els.tagInput.value.trim();
        if (value) addTags(value);
        els.tagInput.value = '';
      } else if (ev.key === 'Backspace' && !els.tagInput.value && state.tags.length) {
        removeTag(state.tags[state.tags.length - 1]);
      }
    });
    els.tagInput.addEventListener('blur', () => {
      const value = els.tagInput.value.trim();
      if (value) {
        addTags(value);
        els.tagInput.value = '';
      }
    });
    els.tagInput.addEventListener('paste', (ev) => {
      const text = ev.clipboardData?.getData('text');
      if (!text) return;
      ev.preventDefault();
      const parts = parseTagText(text);
      if (parts.length > 1) {
        addTags(parts);
        els.tagInput.value = '';
      } else {
        els.tagInput.value = text.trim();
      }
    });
  }

  /* ── 作品 ID 输入 ───────────────────────────────── */

  function parseIds(text) {
    const seen = new Set();
    const ids = [];
    (String(text).match(/\d{5,12}/g) || []).forEach((raw) => {
      const id = Number(raw);
      if (!Number.isSafeInteger(id) || id <= 0 || seen.has(id)) return;
      seen.add(id);
      ids.push(id);
    });
    return ids.slice(0, 10);
  }

  function renderIdChips() {
    state.ids = parseIds(els.idInput.value);
    els.idChips.textContent = '';
    state.ids.forEach((id) => {
      const chip = document.createElement('span');
      chip.className = 'chip';
      const label = document.createElement('span');
      label.textContent = String(id);
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('aria-label', `移除作品 ${id}`);
      btn.textContent = '×';
      btn.addEventListener('click', () => {
        const rest = state.ids.filter((x) => x !== id);
        els.idInput.value = rest.join('\n');
        renderIdChips();
      });
      chip.append(label, btn);
      els.idChips.appendChild(chip);
    });
    const n = state.ids.length;
    if (!n) {
      els.idNote.textContent = '从 2 到 10 个作品里提取画风标签，再按标签相似度寻找同风格作品。';
      delete els.idNote.dataset.tone;
    } else if (n === 1) {
      els.idNote.textContent = '已识别 1 个作品，建议再补几个，画风标签会更准。';
      delete els.idNote.dataset.tone;
    } else if (n >= 10) {
      els.idNote.textContent = '已识别 10 个作品（上限），多余的 ID 被忽略。';
      els.idNote.dataset.tone = 'warn';
    } else {
      els.idNote.textContent = `已识别 ${n} 个作品，将提取共同画风标签并排序相似作品。`;
      delete els.idNote.dataset.tone;
    }
    if (state.mode === 'related') {
      els.idNote.textContent = n
        ? `已识别 ${n} 个种子作品，将沿相关推荐一层层往下找；每次「下一批」不重复。`
        : '从种子作品的相关推荐开始，一层层往下找；每次「下一批」继续抓没出现过的作品。';
      delete els.idNote.dataset.tone;
    }
    updateSaveButton();
    scheduleSeedPreview();
  }

  /* ── 搜索池 / 保存搜索 ─────────────────────────── */

  function tagsFromItem(item) {
    const raw = (state.mode === 'similar' && Array.isArray(item.match_tags) && item.match_tags.length)
      ? item.match_tags
      : (Array.isArray(item.tags) ? item.tags : []);
    const seen = new Set();
    const result = [];
    raw.forEach((tag) => {
      const name = (typeof tag === 'string' ? tag : (tag && tag.name) || '').trim();
      if (!name) return;
      const low = name.toLowerCase();
      if (GENERIC_TAGS.has(low) || seen.has(low)) return;
      seen.add(low);
      result.push(name);
    });
    if (!result.length) {
      raw.forEach((tag) => {
        const name = (typeof tag === 'string' ? tag : (tag && tag.name) || '').trim();
        const low = name.toLowerCase();
        if (name && !seen.has(low)) {
          seen.add(low);
          result.push(name);
        }
      });
    }
    return result.slice(0, 8);
  }

  const STYLE_TAG_KEYWORDS = [
    '画風', '塗り', '水彩', '厚塗り', '線画', 'アニメ調', 'セル', 'ちび',
    'デフォルメ', 'タッチ', '彩色', 'モノクロ', '油絵', '筆', '質感', '陰影',
    '光', '構図', '背景', 'アニメ', '漫画', 'イラスト',
  ];

  function isStyleTagName(name) {
    const low = String(name || '').toLowerCase();
    return STYLE_TAG_KEYWORDS.some((keyword) => low.includes(String(keyword).toLowerCase()));
  }

  function addTagsFromWork(item, onlyStyle = false) {
    let list = tagsFromItem(item);
    if (onlyStyle) list = list.filter(isStyleTagName);
    if (!list.length) {
      showToast(onlyStyle ? '这个作品没有可加入的画风标签' : '这个作品没有可加入的标签', 'error');
      return;
    }
    const added = addTags(list);
    if (!added) {
      showToast('这些标签已经在搜索池里了');
      return;
    }
    setMode('tag');
    showToast(`已把 ${added} 个标签加入搜索池`);
  }

  function rightClickHint() {
    return '右键打开操作菜单';
  }

  function updateCardHints() {
    const hint = rightClickHint();
    $$('.card .thumb-wrap', els.grid).forEach((el) => {
      el.title = `左键点图片选中或取消，${hint}`;
    });
  }

  function closeCardMenu() {
    els.cardMenu.hidden = true;
    els.cardMenu.textContent = '';
    state.menuItem = null;
  }

  function addCardMenuItem(label, handler, primary = false) {
    const button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('role', 'menuitem');
    button.textContent = label;
    if (primary) button.style.color = 'var(--accent)';
    button.addEventListener('click', () => {
      closeCardMenu();
      handler();
    });
    els.cardMenu.appendChild(button);
  }

  function openCardMenu(item, x, y) {
    state.menuItem = item;
    els.cardMenu.textContent = '';
    if (state.mode === 'similar' || state.mode === 'related') {
      addCardMenuItem('把作品加入种子列表', () => addSeedFromWork(item), true);
      addCardMenuItem('只加画风标签到标签池', () => addTagsFromWork(item, true));
      addCardMenuItem('加入全部标签到标签池', () => addTagsFromWork(item, false));
    } else {
      addCardMenuItem('只加画风标签到标签池', () => addTagsFromWork(item, true), true);
      addCardMenuItem('加入全部标签到标签池', () => addTagsFromWork(item, false));
      addCardMenuItem('把作品加入种子列表', () => addSeedFromWork(item));
    }
    const divider = document.createElement('hr');
    els.cardMenu.appendChild(divider);
    addCardMenuItem('在 Pixiv 打开详细页', () => {
      window.open(`https://www.pixiv.net/artworks/${item.id}`, '_blank');
    });
    addCardMenuItem('复制作品 ID', async () => {
      try {
        await navigator.clipboard.writeText(String(item.id));
        showToast(`已复制 ID ${item.id}`);
      } catch {
        showToast('剪贴板不可用', 'error');
      }
    });
    els.cardMenu.hidden = false;
    const rect = els.cardMenu.getBoundingClientRect();
    const left = Math.max(8, Math.min(x, window.innerWidth - rect.width - 8));
    const top = Math.max(8, Math.min(y, window.innerHeight - rect.height - 8));
    els.cardMenu.style.left = `${left}px`;
    els.cardMenu.style.top = `${top}px`;
  }

  function addSeedFromWork(item) {
    const id = Number(item.id);
    if (!id) return;
    if (state.ids.includes(id)) {
      showToast('这个作品已经在种子列表里了');
      return;
    }
    if (state.ids.length >= 10) {
      showToast('种子作品最多 10 个', 'error');
      return;
    }
    if (state.mode !== 'similar' && state.mode !== 'related') setMode('similar');
    state.relatedSession = null;
    state.relatedExhausted = false;
    els.relatedNextBtn.hidden = true;
    els.idInput.value = [...state.ids, id].join('\n');
    renderIdChips();
    showToast(`已把作品 ${id} 加入种子列表`);
  }

  /* ── 种子作品预览 ───────────────────────────────── */

  function scheduleSeedPreview() {
    clearTimeout(state.seedTimer);
    state.seedError = '';
    renderSeedPreview();
    if (state.mode !== 'similar' || !state.ids.length) return;
    state.seedTimer = setTimeout(fetchSeedDetails, 650);
  }

  async function fetchSeedDetails() {
    if (state.mode !== 'similar') return;
    const missing = state.ids.filter((id) => !state.seedCache.has(id));
    if (!missing.length) {
      renderSeedPreview();
      return;
    }
    const seq = ++state.seedFetchSeq;
    try {
      const data = await api('/api/lookup', { method: 'POST', body: { ids: missing } });
      if (seq !== state.seedFetchSeq) return;
      (data.items || []).forEach((item) => state.seedCache.set(item.id, item));
      (data.errors || []).forEach((err) => state.seedCache.set(err.id, null));
      state.seedError = '';
    } catch (err) {
      if (seq !== state.seedFetchSeq) return;
      state.seedError = err.message;
    }
    renderSeedPreview();
  }

  function renderSeedPreview() {
    const show = state.mode === 'similar' && state.ids.length > 0;
    els.seedPreview.hidden = !show;
    if (!show) {
      els.seedGrid.textContent = '';
      return;
    }
    els.seedGrid.textContent = '';
    let missing = 0;
    let failed = 0;
    state.ids.forEach((id) => {
      const cached = state.seedCache.get(id);
      let node;
      if (cached) {
        node = document.createElement('a');
        node.className = 'seed-thumb';
        node.href = `https://www.pixiv.net/artworks/${id}`;
        node.target = '_blank';
        node.rel = 'noopener noreferrer';
        node.title = `${cached.title || id}（${Number(cached.page_count) || 1} 页）`;
        const img = document.createElement('img');
        img.loading = 'lazy';
        img.alt = '';
        img.src = cached.thumb_url;
        const pages = document.createElement('span');
        pages.className = 'seed-pages';
        pages.textContent = `${Number(cached.page_count) || 1} 页`;
        node.append(img, pages);
      } else {
        missing += cached === undefined ? 1 : 0;
        failed += cached === null ? 1 : 0;
        node = document.createElement('div');
        node.className = `seed-thumb ${cached === null ? 'is-error' : 'is-loading'}`;
        node.textContent = cached === null ? '读取失败' : '…';
        node.title = cached === null ? `作品 ${id} 读取失败` : `作品 ${id} 读取中`;
      }
      els.seedGrid.appendChild(node);
    });
    if (missing > 0) {
      els.seedPreviewState.textContent = state.seedError || '读取中…';
    } else if (failed > 0) {
      els.seedPreviewState.textContent = `${failed} 个读取失败`;
    } else {
      els.seedPreviewState.textContent = '';
    }
  }

  function captureSearch() {
    return {
      mode: state.mode,
      tags: [...state.tags],
      ids: [...state.ids],
      r18: els.r18Toggle.checked,
      workType: getWorkType(),
      sort: els.sortSelect.value,
      limit: Number(els.limitSelect.value),
      bookmark: Math.max(0, Number(els.bookmarkInput.value) || 0),
      includeRelated: els.includeRelated.checked,
      seedTagLimit: Number(els.seedTagLimit.value),
    };
  }

  function searchName(cfg) {
    return cfg.mode === 'tag' ? cfg.tags.join(' + ') : `ID ${cfg.ids.join(', ')}`;
  }

  function searchSignature(cfg) {
    return JSON.stringify({
      m: cfg.mode, t: cfg.tags, i: cfg.ids, r: cfg.r18, w: cfg.workType,
      s: cfg.sort, l: cfg.limit, b: cfg.bookmark, ir: cfg.includeRelated, st: cfg.seedTagLimit,
    });
  }

  function trimText(text, max) {
    const value = String(text || '');
    return value.length > max ? `${value.slice(0, max)}…` : value;
  }

  function loadSavedSearches() {
    try {
      const raw = JSON.parse(localStorage.getItem(SAVED_KEY) || '[]');
      state.saved = Array.isArray(raw)
        ? raw.filter((entry) => entry && Array.isArray(entry.tags) && Array.isArray(entry.ids)).slice(0, 12)
        : [];
    } catch {
      state.saved = [];
    }
    renderSavedSearches();
  }

  function persistSavedSearches() {
    try {
      localStorage.setItem(SAVED_KEY, JSON.stringify(state.saved));
    } catch { /* 忽略存储失败 */ }
  }

  function saveCurrentSearch() {
    const cfg = captureSearch();
    const hasQuery = cfg.mode === 'tag' ? cfg.tags.length > 0 : cfg.ids.length > 0;
    if (!hasQuery) {
      showToast('先填写标签或作品 ID 再保存', 'error');
      return;
    }
    const signature = searchSignature(cfg);
    const oldIndex = state.saved.findIndex((entry) => searchSignature(entry) === signature);
    if (oldIndex >= 0) state.saved.splice(oldIndex, 1);
    state.saved.unshift({ id: Date.now(), name: searchName(cfg), ...cfg });
    state.saved = state.saved.slice(0, 12);
    persistSavedSearches();
    renderSavedSearches();
    showToast(oldIndex >= 0 ? '这条搜索已经保存过，已移到最前' : '已保存这次搜索');
  }

  function restoreSavedSearch(entry) {
    if (!entry) return;
    setMode(entry.mode === 'similar' ? 'similar' : 'tag');
    state.tags = Array.isArray(entry.tags) ? entry.tags.slice(0, 20) : [];
    renderTags();
    els.idInput.value = (entry.ids || []).join('\n');
    renderIdChips();
    els.r18Toggle.checked = Boolean(entry.r18);
    const radio = document.querySelector(`input[name="workType"][value="${entry.workType}"]`);
    if (radio) radio.checked = true;
    if (SORTS.has(entry.sort)) els.sortSelect.value = entry.sort;
    if (entry.limit) els.limitSelect.value = String(entry.limit);
    els.bookmarkInput.value = String(entry.bookmark || 0);
    els.includeRelated.checked = entry.includeRelated !== false;
    els.seedTagLimit.value = String(entry.seedTagLimit || 6);
    saveSettings();
    updateSaveButton();
    setScanState(`已恢复保存的搜索：${trimText(searchName(entry), 40)}`);
    showToast('搜索条件已恢复，点「扫描匹配作品」重新抓取');
  }

  function removeSavedSearch(id) {
    state.saved = state.saved.filter((entry) => entry.id !== id);
    persistSavedSearches();
    renderSavedSearches();
  }

  function renderSavedSearches() {
    els.savedChips.textContent = '';
    els.savedRow.hidden = state.saved.length === 0;
    state.saved.forEach((entry) => {
      const chip = document.createElement('span');
      chip.className = 'chip saved-chip';
      chip.title = `恢复这条搜索：${entry.name}`;
      chip.tabIndex = 0;
      chip.setAttribute('role', 'button');
      const label = document.createElement('span');
      label.textContent = trimText(entry.name, 34);
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.setAttribute('aria-label', `删除保存的搜索 ${trimText(entry.name, 20)}`);
      remove.textContent = '×';
      remove.addEventListener('click', (ev) => {
        ev.stopPropagation();
        removeSavedSearch(entry.id);
      });
      chip.addEventListener('click', () => restoreSavedSearch(entry));
      chip.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          restoreSavedSearch(entry);
        }
      });
      chip.append(label, remove);
      els.savedChips.appendChild(chip);
    });
  }

  function updateSaveButton() {
    const hasQuery = state.mode === 'tag' ? state.tags.length > 0 : state.ids.length > 0;
    if (els.saveSearchBtn) els.saveSearchBtn.disabled = !hasQuery;
  }

  /* ── 扫描 ───────────────────────────────────────── */

  function currentPreviewPayload() {
    return {
      mode: state.mode,
      tags: state.mode === 'tag' ? state.tags : [],
      ids: (state.mode === 'similar' || state.mode === 'related') ? state.ids : [],
      r18: els.r18Toggle.checked,
      work_type: getWorkType(),
      sort: els.sortSelect.value,
      limit: Number(els.limitSelect.value),
      min_bookmarks: Math.max(0, Number(els.bookmarkInput.value) || 0),
      pages: 5,
      seed_tag_limit: Number(els.seedTagLimit.value),
      include_related: els.includeRelated.checked,
      skip_existing: els.skipExisting.checked,
    };
  }

  async function scan() {
    if (state.mode === 'related') {
      startRelatedCrawl();
      return;
    }
    if (state.scanning || state.jobId || isScanRunning()) return;
    if (!state.connected) {
      setScanState('请先连接账号后再扫描。', 'error');
      els.tokenInput.focus();
      return;
    }
    if (state.mode === 'tag' && !state.tags.length) {
      setScanState('请先添加至少一个标签。', 'error');
      els.tagInput.focus();
      return;
    }
    if (state.mode === 'similar' && !state.ids.length) {
      setScanState('请先填写至少一个作品 ID。', 'error');
      els.idInput.focus();
      return;
    }
    if (state.scan.view) {
      state.scan.view = false;
      applyWorkspaceView();
    }
    state.scanning = true;
    els.scanBtn.disabled = true;
    const oldLabel = els.scanBtn.innerHTML;
    els.scanBtn.textContent = '扫描中…';
    const started = performance.now();
    setScanState(state.mode === 'similar' ? '正在提取画风标签并检索相似作品…' : '正在按标签检索作品…');
    try {
      const data = await api('/api/preview', { method: 'POST', body: currentPreviewPayload() });
      const items = Array.isArray(data.items) ? data.items : [];
      const elapsed = ((performance.now() - started) / 1000).toFixed(1);
      applyPreview(items, data);
      const stats = data.stats || {};
      setScanState(itemSummaryText(items, stats, elapsed), items.length ? 'ok' : '');
      if (!items.length) showToast('这次没有匹配到作品，试试放宽筛选条件', 'error');
    } catch (err) {
      setScanState(err.message, 'error');
      showToast(err.message, 'error');
    } finally {
      state.scanning = false;
      els.scanBtn.disabled = false;
      els.scanBtn.innerHTML = oldLabel;
    }
  }

  function updateNextButton() {
    const isTag = state.mode === 'tag';
    const canNext = state.itemsMode === state.mode && (isTag
      ? Boolean(state.tagCursor) && state.items.length > 0
      : (state.mode === 'similar' || state.mode === 'related') && state.items.length > 0);
    const exhausted = isTag ? !state.tagCursor : state.relatedExhausted;
    [els.relatedNextBtn, els.relatedNextTop].forEach((button) => {
      if (!button) return;
      button.hidden = !canNext;
      button.disabled = Boolean(state.nextBusy || state.relatedBusy || exhausted);
    });
    if (els.relatedNextBtn) {
      els.relatedNextBtn.textContent = state.nextBusy
        ? '正在加载下一批…'
        : (exhausted ? '没有更多了' : '下一批（换一批）');
    }
    if (els.relatedNextTop) {
      els.relatedNextTop.textContent = exhausted ? '没有更多了' : '下一批';
    }
  }

  function appendItems(incoming, summaryLabel) {
    state.itemsMode = state.mode;
    const existing = new Set(state.items.map((item) => item.id));
    const fresh = incoming.filter((item) => !existing.has(item.id));
    state.items = state.items.concat(fresh);
    fresh.forEach((item) => state.picked.set(item.id, true));
    renderGrid();
    els.emptyState.hidden = true;
    els.grid.hidden = state.items.length === 0;
    els.selectAllWrap.hidden = state.items.length === 0;
    const summaryText = `${summaryLabel}：本批 ${fresh.length} 个，共 ${state.items.length} 个。左键点图片选中，${rightClickHint()}。`;
    state.resultSummaryText = summaryText;
    els.resultSummary.textContent = summaryText;
    syncSelectAll();
    updateDownloadButton();
    return fresh.length;
  }

  async function nextTagBatch() {
    if (state.nextBusy || !state.tagCursor) return;
    state.nextBusy = true;
    updateNextButton();
    try {
      const payload = currentPreviewPayload();
      payload.cursor = state.tagCursor;
      payload.pages = 1;
      const data = await api('/api/preview', { method: 'POST', body: payload });
      state.tagCursor = data.next_cursor || '';
      const added = appendItems(data.items || [], '标签下一批');
      setScanState(
        added ? `已加载下一批：新增 ${added} 个，共 ${state.items.length} 个`
          : '没有更多结果了，可以换个标签或放宽筛选。',
        added ? 'ok' : '',
      );
      if (!added) showToast('没有更多结果了');
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      state.nextBusy = false;
      updateNextButton();
    }
  }

  async function nextSimilarBatch() {
    if (state.nextBusy || !state.items.length) return;
    if (state.relatedSession) {
      await nextRelatedBatch();
      return;
    }
    state.nextBusy = true;
    updateNextButton();
    try {
      const payload = relatedPayload();
      payload.exclude_ids = state.items.map((item) => item.id);
      const data = await api('/api/related/start', { method: 'POST', body: payload });
      applyRelatedBatch(data, true);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      state.nextBusy = false;
      updateNextButton();
    }
  }

  async function nextBatch() {
    if (state.mode === 'tag') return nextTagBatch();
    if (state.mode === 'similar') return nextSimilarBatch();
    return nextRelatedBatch();
  }

  function relatedPayload() {
    return {
      ids: state.ids,
      r18: els.r18Toggle.checked,
      work_type: getWorkType(),
      min_bookmarks: Math.max(0, Number(els.bookmarkInput.value) || 0),
      batch_size: Number(els.relatedBatch.value) || 20,
      skip_existing: els.skipExisting.checked,
    };
  }

  function applyRelatedBatch(data, append) {
    state.itemsMode = state.mode;
    const incoming = Array.isArray(data.items) ? data.items : [];
    state.relatedSession = data.session_id || state.relatedSession;
    state.relatedBatchNo = Number(data.batch) || (state.relatedBatchNo + 1);
    state.relatedExhausted = Boolean(data.exhausted);
    if (!append) {
      state.items = incoming;
      state.picked = new Map();
      incoming.forEach((item) => state.picked.set(item.id, true));
    } else {
      const existing = new Set(state.items.map((item) => item.id));
      state.items = state.items.concat(incoming.filter((item) => !existing.has(item.id)));
      incoming.forEach((item) => {
        if (!state.picked.has(item.id)) state.picked.set(item.id, true);
      });
    }
    renderGrid();
    els.emptyState.hidden = true;
    els.grid.hidden = state.items.length === 0;
    els.selectAllWrap.hidden = state.items.length === 0;
    const added = append ? incoming.length : state.items.length;
    const batchLabel = state.mode === 'related' ? '相关推荐' : '相似相关';
    const summaryText = state.items.length
      ? `${batchLabel}第 ${state.relatedBatchNo} 批：本批 ${added} 个，共 ${state.items.length} 个。左键点图片选中，${rightClickHint()}。`
      : '没有找到相关推荐。';
    state.resultSummaryText = summaryText;
    els.resultSummary.textContent = summaryText;
    syncSelectAll();
    updateDownloadButton();
    const stats = data.stats || {};
    setScanState(
      `第 ${state.relatedBatchNo} 批 · 已发现 ${state.items.length} 个 · 待展开 ${stats.frontier || 0} 个`,
      state.items.length ? 'ok' : '',
    );
    updateNextButton();
    if (data.warnings && data.warnings.length) {
      showToast(data.warnings[data.warnings.length - 1], 'error');
    }
    if (!append && !state.items.length) {
      showToast('没有找到相关推荐，试试换种子作品或放宽筛选', 'error');
    }
  }

  async function startRelatedCrawl() {
    if (state.relatedBusy) return;
    if (!state.connected) {
      setScanState('请先连接账号后再搜索。', 'error');
      els.tokenInput.focus();
      return;
    }
    if (!state.ids.length) {
      setScanState('请先填写至少一个作品 ID。', 'error');
      els.idInput.focus();
      return;
    }
    state.relatedBusy = true;
    state.relatedSession = null;
    state.relatedBatchNo = 0;
    state.relatedExhausted = false;
    els.relatedStartBtn.disabled = true;
    els.relatedStartBtn.textContent = '正在收集相关推荐…';
    els.relatedNextBtn.hidden = true;
    if (els.relatedNextTop) els.relatedNextTop.hidden = true;
    if (state.scan.view) {
      state.scan.view = false;
      applyWorkspaceView();
    }
    try {
      const data = await api('/api/related/start', { method: 'POST', body: relatedPayload() });
      applyRelatedBatch(data, false);
    } catch (err) {
      setScanState(err.message, 'error');
      showToast(err.message, 'error');
    } finally {
      state.relatedBusy = false;
      els.relatedStartBtn.disabled = false;
      els.relatedStartBtn.textContent = '按相关推荐往下搜';
      updateNextButton();
    }
  }

  async function nextRelatedBatch() {
    if (state.relatedBusy || !state.relatedSession || state.relatedExhausted) return;
    state.relatedBusy = true;
    els.relatedNextBtn.disabled = true;
    els.relatedNextBtn.textContent = '正在加载下一批…';
    try {
      const data = await api('/api/related/next', {
        method: 'POST',
        body: {
          session_id: state.relatedSession,
          batch_size: Number(els.relatedBatch.value) || 20,
        },
      });
      applyRelatedBatch(data, true);
      if (!data.items || !data.items.length) {
        showToast(data.exhausted ? '相关推荐已经走完了' : '这一批没有新的作品');
      }
    } catch (err) {
      setScanState(err.message, 'error');
      showToast(err.message, 'error');
    } finally {
      state.relatedBusy = false;
      updateNextButton();
    }
  }


  function itemSummaryText(items, stats, elapsed) {
    if (!items.length) return '没有匹配结果。可以减少筛选条件后重试。';
    const parts = [`匹配 ${items.length} 个作品`];
    if (stats.candidates) parts.push(`候选 ${stats.candidates} 个`);
    if (stats.api_calls) parts.push(`接口调用 ${stats.api_calls} 次`);
    if (elapsed) parts.push(`耗时 ${elapsed} 秒`);
    const summary = parts.join('，');
    const limit = Number(els.limitSelect.value) || 20;
    if (items.length < Math.max(3, limit * 0.4)) {
      return `${summary}。符合筛选的作品偏少，可把作品类型切到「全部」或降低最低收藏数。`;
    }
    return summary;
  }

  function applyPreview(items, data) {
    state.items = items;
    state.itemsMode = state.mode;
    state.picked = new Map();
    items.forEach((item) => state.picked.set(item.id, true));
    state.tagCursor = state.mode === 'tag' ? (data.next_cursor || '') : '';
    if (state.mode === 'similar') {
      state.relatedSession = null;
      state.relatedExhausted = false;
      state.relatedBatchNo = 0;
    }
    renderGrid();
    renderSeed(data.seed);
    els.emptyState.hidden = true;
    els.grid.hidden = items.length === 0;
    els.selectAllWrap.hidden = items.length === 0;
    const summaryText = items.length
      ? `共 ${items.length} 个作品，按匹配度排序。左键点图片选中，${rightClickHint()}。`
      : '没有结果';    state.resultSummaryText = summaryText;
    els.resultSummary.textContent = summaryText;
    syncSelectAll();
    updateDownloadButton();
    updateNextButton();
  }

  function renderSeed(seed) {
    if (!seed || !Array.isArray(seed.tags) || !seed.tags.length) {
      els.seedNote.hidden = true;
      els.seedNote.textContent = '';
      return;
    }
    const tags = seed.tags.slice(0, 10);
    els.seedNote.hidden = false;
    els.seedNote.textContent = '';
    const label = document.createElement('span');
    label.className = 'seed-label';
    label.textContent = '种子画风标签';
    els.seedNote.appendChild(label);
    tags.forEach((tag) => {
      const chip = document.createElement('span');
      chip.className = 'chip chip-seed';
      if (tag.style) {
        chip.classList.add('is-style');
        chip.title = `画风关键词，权重 ${Number(tag.weight || 0).toFixed(2)}，${tag.count || 1} 个种子作品命中`;
      } else {
        chip.title = `权重 ${Number(tag.weight || 0).toFixed(2)}，${tag.count || 1} 个种子作品命中`;
      }
      const name = document.createElement('span');
      name.textContent = tag.name;
      const weight = document.createElement('span');
      weight.className = 'weight';
      weight.textContent = Number(tag.weight || 0).toFixed(1);
      chip.append(name, weight);
      els.seedNote.appendChild(chip);
    });
  }

  /* ── 结果网格 ───────────────────────────────────── */

  function renderGrid() {
    els.grid.textContent = '';
    const frag = document.createDocumentFragment();
    state.items.forEach((item) => frag.appendChild(buildCard(item)));
    els.grid.appendChild(frag);
  }

  function buildCard(item) {
    const card = document.createElement('article');
    card.className = 'card';
    card.dataset.id = String(item.id);
    card.dataset.picked = 'true';

    const pick = document.createElement('label');
    pick.className = 'pick';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = true;
    cb.setAttribute('aria-label', `选择作品 ${item.title || item.id}`);
    const setCardPicked = (on) => {
      state.picked.set(item.id, on);
      card.dataset.picked = String(on);
      cb.checked = on;
      syncSelectAll();
      updateDownloadButton();
    };
    cb.addEventListener('change', () => setCardPicked(cb.checked));
    const box = document.createElement('span');
    box.className = 'check-box';
    pick.append(cb, box);

    const thumbWrap = document.createElement('div');
    thumbWrap.className = 'thumb-wrap';
    thumbWrap.title = `左键点图片选中或取消，${rightClickHint()}`;
    thumbWrap.addEventListener('click', () => setCardPicked(!state.picked.get(item.id)));
    thumbWrap.addEventListener('contextmenu', (ev) => {
      ev.preventDefault();
      openCardMenu(item, ev.clientX, ev.clientY);
    });
    if (item.thumb_url) {
      const img = document.createElement('img');
      img.loading = 'lazy';
      img.decoding = 'async';
      img.alt = '';
      img.draggable = false;
      img.src = item.thumb_url;
      img.addEventListener('error', () => {
        img.dataset.state = 'error';
        img.removeAttribute('src');
      });
      thumbWrap.appendChild(img);
    }
    if (Number(item.x_restrict) > 0) {
      const badge = document.createElement('span');
      badge.className = 'r18-badge';
      badge.textContent = 'R-18';
      thumbWrap.appendChild(badge);
    }
    const score = document.createElement('span');
    score.className = 'score-badge';
    score.textContent = `${Math.round((Number(item.score) || 0) * 100)}%`;
    score.title = '与抓取方向的匹配度';
    thumbWrap.appendChild(score);

    const body = document.createElement('div');
    body.className = 'card-body';

    const title = document.createElement('h3');
    title.className = 'card-title';
    title.textContent = item.title || `作品 ${item.id}`;
    title.title = item.title || '';

    const meta = document.createElement('p');
    meta.className = 'card-meta';
    const author = document.createElement('span');
    author.textContent = item.author?.name || '未知作者';
    const pages = document.createElement('span');
    pages.textContent = `${Number(item.page_count) || 1} 页`;
    const marks = document.createElement('span');
    marks.className = 'mono';
    marks.textContent = `收藏 ${formatCount(item.bookmarks)}`;
    meta.append(author, pages, marks);

    const tags = document.createElement('div');
    tags.className = 'card-tags';
    const shown = (item.match_tags && item.match_tags.length ? item.match_tags : item.tags || []).slice(0, 3);
    shown.forEach((tag) => {
      const tagEl = document.createElement('span');
      tagEl.textContent = typeof tag === 'string' ? tag : tag.name;
      tagEl.title = tagEl.textContent;
      tags.appendChild(tagEl);
    });

    body.append(title, meta, tags);

    const foot = document.createElement('div');
    foot.className = 'card-foot';
    const detail = document.createElement('a');
    detail.className = 'detail-link';
    detail.href = `https://www.pixiv.net/artworks/${item.id}`;
    detail.target = '_blank';
    detail.rel = 'noopener noreferrer';
    detail.title = '在 Pixiv 打开详细页';
    detail.innerHTML = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M11 4h5v5"/><path d="m16 4-6.5 6.5"/><path d="M15 12v3.5a1 1 0 0 1-1 1H5.5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1H9"/></svg><span>详细页</span>';
    foot.appendChild(detail);
    body.appendChild(foot);

    const status = document.createElement('span');
    status.className = 'card-state';
    status.textContent = '';

    card.append(pick, status, thumbWrap, body);
    return card;
  }

  /* ── 选择 ───────────────────────────────────────── */

  function syncSelectAll() {
    const total = state.items.length;
    const picked = state.items.reduce((n, item) => n + (state.picked.get(item.id) ? 1 : 0), 0);
    els.selectAll.checked = total > 0 && picked === total;
    els.selectAll.indeterminate = picked > 0 && picked < total;
    els.selectAllLabel.textContent = total ? `已选 ${picked} / ${total}` : '全选';
    $$('.card', els.grid).forEach((card) => {
      const on = state.picked.get(Number(card.dataset.id));
      card.dataset.picked = String(Boolean(on));
      const cb = $('.pick input', card);
      if (cb) cb.checked = Boolean(on);
    });
  }

  function bindSelectAll() {
    els.selectAll.addEventListener('change', () => {
      const on = els.selectAll.checked;
      state.items.forEach((item) => state.picked.set(item.id, on));
      syncSelectAll();
      updateDownloadButton();
    });
  }

  function updateDownloadButton() {
    const running = Boolean(state.jobId);
    const scanRunning = isScanRunning();
    const count = state.items.reduce((n, item) => n + (state.picked.get(item.id) ? 1 : 0), 0);
    els.downloadBtn.disabled = running || scanRunning || !state.connected || count === 0;
    if (!state.scanning) els.scanBtn.disabled = running || scanRunning;
    els.downloadBtn.innerHTML = count > 0 && !running
      ? `<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 3v9"/><path d="m6.2 8.6 3.8 3.8 3.8-3.8"/><path d="M4 15.5h12"/></svg>下载所选 ${count} 个`
      : '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 3v9"/><path d="m6.2 8.6 3.8 3.8 3.8-3.8"/><path d="M4 15.5h12"/></svg>下载所选';
    els.cancelBtn.hidden = !running;
  }

  /* ── 下载任务 ───────────────────────────────────── */

  async function startDownload() {
    if (!state.connected) {
      showToast('请先连接账号', 'error');
      return;
    }
    if (state.jobId) return;
    if (isScanRunning()) {
      showToast('AI 扫描进行中，请先关闭扫描', 'error');
      return;
    }
    const pickedItems = state.items.filter((item) => state.picked.get(item.id));
    if (!pickedItems.length) {
      showToast('还没有勾选作品', 'error');
      return;
    }
    els.downloadBtn.disabled = true;
    setScanState(`准备下载 ${pickedItems.length} 个作品…`);
    try {
      const data = await api('/api/download', {
        method: 'POST',
        body: {
          items: pickedItems.map((item) => ({
            id: item.id,
            title: item.title,
            page_count: item.page_count,
            type: item.type,
            x_restrict: item.x_restrict,
            bookmarks: item.bookmarks,
            tags: item.tags,
            thumb_url: item.thumb_url,
            author: item.author,
          })),
          concurrency: Number(els.concurrencyInput.value),
          pages_limit: Number(els.pagesSelect.value) || 0,
          skip_existing: els.skipExisting.checked,
        },
      });
      state.jobId = data.job_id;
      els.dock.dataset.state = 'running';
      els.openOutputBtn.hidden = true;
      els.cancelBtn.hidden = false;
      els.retryFailedBtn.hidden = true;
      els.sparkNote.hidden = true;
      els.logWrap.hidden = false;
      state.sparkPoints = [];
      resetProgress(pickedItems.length);
      showToast('下载任务已开始');
      pollJob();
    } catch (err) {
      showToast(err.message, 'error');
      setScanState(err.message, 'error');
      updateDownloadButton();
    }
  }

  function resetProgress(totalWorks) {
    els.speedValue.textContent = '0.00';
    els.speedPages.textContent = '0.0 页/秒';
    els.speedWorks.textContent = `0 / ${totalWorks} 作品`;
    els.speedEta.textContent = '剩余时间未知';
    els.barFill.style.width = '0%';
    els.pageCounter.textContent = '0 / 0 页';
    els.byteCounter.textContent = '0 B';
    els.currentList.innerHTML = '<p class="current-empty">正在准备工作目录…</p>';
    els.jobLog.textContent = '';
    drawSpark([], 0);
  }

  function pollJob() {
    clearTimeout(state.pollTimer);
    const jobId = state.jobId;
    if (!jobId) return;
    state.pollTimer = setTimeout(async () => {
      try {
        const data = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
        state.pollFailures = 0;
        applyJob(data.job);
        if (data.job && ['done', 'cancelled', 'error'].includes(data.job.state)) {
          finishJob(data.job);
        } else {
          pollJob();
        }
      } catch (err) {
        state.pollFailures += 1;
        if (state.pollFailures >= 4) {
          state.jobId = null;
          els.dock.dataset.state = 'idle';
          setScanState(`任务状态读取失败：${err.message}`, 'error');
          showToast(err.message, 'error');
          updateDownloadButton();
        } else {
          pollJob();
        }
      }
    }, 500);
  }

  function applyJob(job) {
    if (!job) return;
    state.job = job;
    const totalWorks = Number(job.total_works) || 0;
    const doneWorks = Number(job.done_works) || 0;
    const totalPages = Number(job.total_pages) || 0;
    const donePages = Number(job.done_pages) || 0;
    const speedBps = Number(job.speed_bps) || 0;

    els.speedValue.textContent = (speedBps / (1024 * 1024)).toFixed(2);
    els.speedPages.textContent = `${(Number(job.speed_pages) || 0).toFixed(1)} 页/秒`;
    els.speedWorks.textContent = `${doneWorks} / ${totalWorks} 作品`;
    let etaText = '剩余时间计算中';
    const etaRaw = Number(job.eta_seconds);
    if (job.state === 'done') {
      etaText = '全部完成';
    } else if (Number.isFinite(etaRaw) && etaRaw > 0.5) {
      etaText = formatEta(etaRaw);
    } else if (totalPages > donePages && Number(job.speed_pages) > 0.05) {
      etaText = formatEta((totalPages - donePages) / Number(job.speed_pages));
    }
    els.speedEta.textContent = etaText;
    els.pageCounter.textContent = `${donePages} / ${totalPages} 页`;
    els.byteCounter.textContent = humanBytes(job.total_bytes);

    let ratio = 0;
    if (totalPages > 0) ratio = donePages / totalPages;
    else if (totalWorks > 0) ratio = doneWorks / totalWorks;
    els.barFill.style.width = `${Math.min(100, Math.max(0, ratio * 100)).toFixed(1)}%`;

    const series = Array.isArray(job.speed_series) ? job.speed_series : [];
    state.sparkPoints = series.map((p) => ({ bps: Number(p.bps) || 0, t: Number(p.t) || 0 }));
    drawSpark(state.sparkPoints, speedBps);

    renderCurrent(job.current, totalPages, donePages);
    renderLog(job.log);
    updateCardsFromJob(job.items);

    if (job.state === 'running') {
      els.dock.dataset.state = 'running';
      setScanState(`下载中 · ${doneWorks} / ${totalWorks} 作品`, 'ok');
    }
  }

  function renderCurrent(current, totalPages, donePages) {
    if (!Array.isArray(current) || !current.length) {
      if (!state.items.length) return;
      els.currentList.innerHTML = `<p class="current-empty">${donePages} / ${totalPages} 页完成</p>`;
      return;
    }
    els.currentList.textContent = '';
    current.slice(0, 3).forEach((item) => {
      const row = document.createElement('div');
      row.className = 'current-item';
      const name = document.createElement('span');
      name.className = 'ci-name';
      name.textContent = item.title || `作品 ${item.id}`;
      name.title = name.textContent;
      const bar = document.createElement('span');
      bar.className = 'ci-bar';
      const fill = document.createElement('span');
      const pagesTotal = Number(item.pages_total) || 0;
      const pagesDone = Number(item.pages_done) || 0;
      const pct = pagesTotal > 0 ? Math.min(100, (pagesDone / pagesTotal) * 100) : 0;
      fill.style.width = `${pct.toFixed(1)}%`;
      bar.appendChild(fill);
      row.append(name, bar);
      els.currentList.appendChild(row);
    });
  }

  function renderLog(log) {
    if (!Array.isArray(log) || !log.length) {
      els.jobLog.textContent = '';
      return;
    }
    const lines = log.slice(-40);
    els.jobLog.textContent = '';
    lines.forEach((entry) => {
      const line = document.createElement('div');
      if (entry.level === 'error') line.className = 'log-error';
      else if (entry.level === 'warn') line.className = 'log-warn';
      const time = entry.t ? new Date(entry.t).toLocaleTimeString('zh-CN', { hour12: false }) : '';
      line.textContent = `${time}  ${entry.text || ''}`;
      els.jobLog.appendChild(line);
    });
    els.jobLog.scrollTop = els.jobLog.scrollHeight;
  }

  function updateCardsFromJob(items) {
    if (!Array.isArray(items)) return;
    items.forEach((item) => {
      const card = els.grid.querySelector(`.card[data-id="${item.id}"]`);
      if (!card) return;
      const status = $('.card-state', card);
      const textMap = { done: '已下载', skipped: '已存在', failed: '失败' };
      if (item.state && textMap[item.state]) {
        card.dataset.download = item.state;
        if (status) {
          status.textContent = textMap[item.state];
          if (item.state === 'failed' && item.error) status.title = item.error;
        }
        if (item.state === 'failed') card.dataset.picked = 'false';
      }
    });
  }

  function finishJob(job) {
    state.jobId = null;
    clearTimeout(state.pollTimer);
    els.dock.dataset.state = 'idle';
    els.cancelBtn.hidden = true;
    els.openOutputBtn.hidden = false;
    els.sparkNote.hidden = false;
    els.sparkNote.textContent = '任务结束，速度曲线已定格';
    updateDownloadButton();

    const done = Number(job.done_works) || 0;
    const skipped = Number(job.skipped_works) || 0;
    const failed = Number(job.failed_works) || 0;
    els.retryFailedBtn.hidden = failed === 0;
    const bytes = humanBytes(job.total_bytes);
    const summary = `完成 ${done} 个作品${skipped ? `，跳过 ${skipped} 个` : ''}${failed ? `，失败 ${failed} 个` : ''}，共 ${bytes}`;
    if (job.state === 'cancelled') {
      setScanState('任务已停止。' + summary);
      showToast('任务已停止');
    } else if (job.state === 'error') {
      setScanState(`任务出错：${job.errors?.[0]?.message || '未知错误'}`, 'error');
      showToast('任务出错，请查看日志', 'error');
    } else {
      setScanState(summary, failed ? 'error' : 'ok');
      showToast(summary);
    }
    if (job.state === 'done') {
      els.speedValue.textContent = '0.00';
      els.speedPages.textContent = '0.0 页/秒';
      els.speedEta.textContent = '全部完成';
    }
    if (Array.isArray(job.items)) {
      job.items.forEach((item) => {
        if (item.state === 'failed') {
          const line = document.createElement('p');
          line.className = 'current-empty';
          line.textContent = `失败：${item.title || item.id} ${item.error || ''}`;
          els.currentList.appendChild(line);
        }
      });
    }
  }

  async function retryFailedDownloads() {
    const job = state.job;
    if (!job || !job.id) {
      showToast('没有可重试的任务', 'error');
      return;
    }
    if (Number(job.failed_works) <= 0) {
      showToast('这个任务没有失败作品');
      return;
    }
    els.retryFailedBtn.disabled = true;
    try {
      const data = await api(`/api/jobs/${encodeURIComponent(job.id)}/retry`, { method: 'POST', body: {} });
      state.jobId = data.job_id;
      els.retryFailedBtn.hidden = true;
      els.dock.dataset.state = 'running';
      els.openOutputBtn.hidden = true;
      els.cancelBtn.hidden = false;
      els.sparkNote.hidden = true;
      state.sparkPoints = [];
      resetProgress(Number(data.retry_count) || 1);
      showToast(`开始重试 ${data.retry_count} 个失败作品`);
      pollJob();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      els.retryFailedBtn.disabled = false;
    }
  }

  async function cancelJob() {
    if (!state.jobId) return;
    els.cancelBtn.disabled = true;
    try {
      await api(`/api/jobs/${encodeURIComponent(state.jobId)}/cancel`, { method: 'POST', body: {} });
      showToast('已请求停止，正在收尾');
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      els.cancelBtn.disabled = false;
    }
  }

  /* ── AI 元数据扫描 ─────────────────────────────── */

  function getScanBatchSize() {
    const value = Number(els.scanBatchSelect && els.scanBatchSelect.value);
    return [5, 10, 20, 30, 50].includes(value) ? value : 10;
  }

  function setScanStatus(text, tone = '') {
    els.aiScanStatus.textContent = text;
    if (tone) els.aiScanStatus.dataset.tone = tone;
    else delete els.aiScanStatus.dataset.tone;
  }

  function isScanRunning() {
    return Boolean(state.scan.snapshot && state.scan.snapshot.state === 'running');
  }

  function scanConfigPayload() {
    const payload = currentPreviewPayload();
    return {
      mode: payload.mode,
      tags: payload.tags,
      ids: payload.ids,
      r18: payload.r18,
      min_bookmarks: payload.min_bookmarks,
      seed_tag_limit: payload.seed_tag_limit,
      include_related: payload.include_related,
      pages_limit: Number(els.pagesSelect.value) || 0,
      concurrency: Number(els.concurrencyInput.value),
      batch_size: getScanBatchSize(),
    };
  }

  function applyWorkspaceView() {
    const scanning = state.scan.view;
    els.scanPanel.hidden = !scanning;
    els.emptyState.hidden = scanning || state.items.length > 0;
    els.grid.hidden = scanning || state.items.length === 0;
    els.dock.hidden = scanning;
    els.selectAllWrap.hidden = scanning || state.items.length === 0;
    els.savedRow.hidden = scanning || state.saved.length === 0;
    els.saveSearchBtn.hidden = scanning;
    const hasSeedNote = els.seedNote.textContent.trim() !== '';
    els.seedNote.hidden = scanning || !(state.mode === 'similar' && hasSeedNote);
    els.scanBackBtn.hidden = !scanning || isScanRunning();
    if (scanning) {
      els.wsTitle.textContent = 'AI 扫描结果';
      els.resultSummary.textContent = !state.scan.snapshot
        ? '正在启动扫描…'
        : (isScanRunning()
          ? '持续扫描中，命中的作品会实时出现在下方。'
          : '扫描已结束，命中结果如下。');
    } else {
      els.wsTitle.textContent = '匹配结果';
      els.resultSummary.textContent = state.resultSummaryText;
    }
  }

  function resetScanPanel() {
    state.scan.lastHits = 0;
    state.scan.lastHitKey = '';
    state.scan.expanded.clear();
    state.scan.hitDetails.clear();
    els.scanMetrics.hidden = false;
    els.scanBatchValue.textContent = '0';
    els.scanDownloadValue.textContent = '0';
    els.scanHitValue.textContent = '0';
    els.scanProgressValue.textContent = `0/${getScanBatchSize()}`;
    els.scanPanelSummary.textContent = '正在准备扫描…';
    els.scanBarFill.style.width = '0%';
    els.scanProgressText.textContent = '准备中';
    els.scanSpeedText.textContent = '';
    els.scanHitHint.hidden = true;
    els.scanHits.textContent = '';
    els.scanHitsEmpty.hidden = false;
    els.scanLog.textContent = '';
    els.scanFolderRow.hidden = true;
    els.scanSessionHint.textContent = '';
    els.aiScanStopBtn.hidden = false;
    els.scanBackBtn.hidden = true;
  }

  async function startAiScan() {
    if (state.scan.starting) return;
    if (!state.connected) {
      els.aiScanToggle.checked = false;
      setScanStatus('请先连接账号', 'error');
      showToast('请先连接账号再开启 AI 扫描', 'error');
      return;
    }
    if (state.mode === 'tag' && !state.tags.length) {
      els.aiScanToggle.checked = false;
      setScanStatus('请先添加标签', 'error');
      showToast('请先添加至少一个标签', 'error');
      els.tagInput.focus();
      return;
    }
    if ((state.mode === 'similar' || state.mode === 'related') && !state.ids.length) {
      els.aiScanToggle.checked = false;
      setScanStatus('请先填写种子作品 ID', 'error');
      showToast('请先填写至少一个作品 ID', 'error');
      els.idInput.focus();
      return;
    }
    state.scan.starting = true;
    setScanStatus('正在启动…');
    try {
      const data = await api('/api/scan/start', { method: 'POST', body: scanConfigPayload() });
      state.scan.id = data.scan_id;
      state.scan.snapshot = null;
      state.scan.view = true;
      els.aiScanToggle.checked = true;
      resetScanPanel();
      applyWorkspaceView();
      updateDownloadButton();
      startScanPolling();
      maybeRequestNotificationPermission();
      showToast('AI 元数据扫描已开始');
    } catch (err) {
      els.aiScanToggle.checked = false;
      state.scan.view = false;
      setScanStatus(err.message, 'error');
      showToast(err.message, 'error');
      applyWorkspaceView();
    } finally {
      state.scan.starting = false;
    }
  }

  async function stopAiScan() {
    const scanId = state.scan.id;
    if (!scanId) {
      setScanStatus('未开启');
      return;
    }
    els.aiScanStopBtn.disabled = true;
    setScanStatus('正在停止…');
    try {
      await api(`/api/scan/${encodeURIComponent(scanId)}/stop`, { method: 'POST', body: {} });
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      els.aiScanStopBtn.disabled = false;
    }
  }

  function startScanPolling() {
    clearTimeout(state.scan.timer);
    if (!state.scan.id) return;
    state.scan.timer = setTimeout(pollScan, 700);
  }

  async function pollScan() {
    const scanId = state.scan.id;
    if (!scanId) return;
    try {
      const data = await api(`/api/scan/${encodeURIComponent(scanId)}`);
      const scan = data.scan;
      applyScanSnapshot(scan);
      if (scan && scan.state === 'running') {
        startScanPolling();
      } else {
        finishAiScan(scan);
      }
    } catch (err) {
      clearTimeout(state.scan.timer);
      state.scan.id = null;
      state.scan.view = false;
      els.aiScanToggle.checked = false;
      setScanStatus(`读取扫描状态失败：${err.message}`, 'error');
      showToast(err.message, 'error');
      applyWorkspaceView();
      updateDownloadButton();
    }
  }

  function applyScanSnapshot(scan) {
    if (!scan) return;
    state.scan.snapshot = scan;
    state.scan.view = true;
    els.scanMetrics.hidden = false;
    els.wsTitle.textContent = 'AI 扫描结果';
    els.resultSummary.textContent = scan.state === 'running'
      ? '持续扫描中，命中的作品会实时出现在下方。'
      : '扫描已结束，命中结果如下。';
    if (scan.session_rel) {
      els.scanFolderRow.hidden = false;
      els.scanSessionHint.textContent = scan.session_rel;
    }
    const batchSize = Number(scan.batch_size) || getScanBatchSize();
    const current = Array.isArray(scan.current_batch) ? scan.current_batch : [];
    const doneStates = new Set(['done', 'hit', 'skipped', 'failed']);
    const doneInBatch = current.filter((entry) => doneStates.has(entry.state)).length;
    const download = scan.download || null;
    const donePages = download ? Number(download.done_pages) || 0 : 0;
    const totalPages = download ? Number(download.total_pages) || 0 : 0;
    const speedBps = download ? Number(download.speed_bps) || 0 : 0;
    const speedPages = download ? Number(download.speed_pages) || 0 : 0;
    const downloadDoneWorks = download ? Number(download.done_works) || 0 : 0;
    const worksDone = Math.min(batchSize, Math.max(doneInBatch, downloadDoneWorks));

    els.scanBatchValue.textContent = String(scan.batch_index || 0);
    els.scanDownloadValue.textContent = String((Number(scan.downloaded_total) || 0) + downloadDoneWorks);
    els.scanHitValue.textContent = String(scan.hits_total || 0);
    els.scanProgressValue.textContent = `${worksDone}/${batchSize}`;

    let ratio = 0;
    if (download && totalPages > 0) ratio = donePages / totalPages;
    else if (current.length) ratio = worksDone / batchSize;
    els.scanBarFill.style.width = `${Math.min(100, Math.max(0, ratio * 100)).toFixed(1)}%`;

    let progressText = current.length
      ? `第 ${scan.batch_index || 1} 批 ${worksDone}/${batchSize} 个作品`
      : `第 ${scan.batch_index || 0} 批`;
    if (download && totalPages > 0) progressText += ` · 页 ${donePages}/${totalPages}`;
    els.scanProgressText.textContent = progressText;
    const speedParts = [];
    if (speedBps > 0) speedParts.push(`${(speedBps / (1024 * 1024)).toFixed(2)} MB/s`);
    if (speedPages > 0.05) speedParts.push(`${speedPages.toFixed(1)} 页/秒`);
    els.scanSpeedText.textContent = speedParts.length
      ? speedParts.join(' · ')
      : (scan.state === 'running' ? '等待下载' : '');

    els.scanPanelSummary.textContent = `第 ${scan.batch_index || 0} 批 · 下载 ${(Number(scan.downloaded_total) || 0) + downloadDoneWorks} 个 · 检查 ${scan.inspected_total || 0} 个 · 命中 ${scan.hits_total || 0} 个`;
    setScanStatus(scanStatusText(scan), scan.state === 'error' ? 'error' : (scan.state === 'running' ? '' : 'ok'));
    els.aiScanStopBtn.hidden = scan.state !== 'running';
    els.scanBackBtn.hidden = scan.state === 'running';
    if (scan.state !== 'running') els.aiScanToggle.checked = false;

    const hits = Array.isArray(scan.hits) ? scan.hits : [];
    const hitKey = hits.map((hit) => `${hit.id}:${(hit.field_keys || []).join(',')}`).join('|');
    if (hitKey !== state.scan.lastHitKey) {
      renderScanHits(hits);
      state.scan.lastHitKey = hitKey;
    }
    els.scanHitsEmpty.hidden = hits.length > 0;
    els.scanHitHint.hidden = !((Number(scan.hits_total) || 0) > 0 || hits.length > 0);

    if (Number(scan.hits_total) > state.scan.lastHits && state.scan.lastHits > 0 && hits.length) {
      const latest = hits[hits.length - 1];
      showToast(`发现元数据命中：${trimText(latest.title || latest.id, 26)}`);
      notifyHit(trimText(latest.title || String(latest.id), 40));
    }
    state.scan.lastHits = Number(scan.hits_total) || 0;

    renderScanLog(scan.log);
    updateDownloadButton();
  }

  function scanStatusText(scan) {
    if (scan.state === 'error') return `出错：${scan.error || '未知错误'}`;
    if (scan.state === 'stopped') return `已停止 · 命中 ${scan.hits_total || 0}`;
    if (scan.state === 'done') return `扫描结束 · 命中 ${scan.hits_total || 0}`;
    const phaseText = {
      preparing: '准备中',
      discovering: '寻找 AI 作品',
      waiting: '等待新作品',
      downloading: '下载中',
      inspecting: '检查元数据',
      finished: '收尾中',
    }[scan.phase] || '运行中';
    return `运行中 · 第 ${Math.max(1, scan.batch_index || 1)} 批 · ${phaseText}`;
  }

  function renderScanHits(hits) {
    els.scanHits.textContent = '';
    const recent = hits.slice(-20).reverse();
    recent.forEach((hit) => {
      const card = document.createElement('article');
      card.className = 'scan-hit';

      const thumb = document.createElement('a');
      thumb.className = 'scan-hit-thumb';
      thumb.href = `https://www.pixiv.net/artworks/${hit.id}`;
      thumb.target = '_blank';
      thumb.rel = 'noopener noreferrer';
      if (hit.thumb_url) {
        const img = document.createElement('img');
        img.loading = 'lazy';
        img.alt = '';
        img.src = hit.thumb_url;
        thumb.appendChild(img);
      }

      const body = document.createElement('div');
      body.className = 'scan-hit-body';
      const title = document.createElement('a');
      title.className = 'scan-hit-title';
      title.href = `https://www.pixiv.net/artworks/${hit.id}`;
      title.target = '_blank';
      title.rel = 'noopener noreferrer';
      title.textContent = hit.title || `作品 ${hit.id}`;

      const meta = document.createElement('p');
      meta.className = 'scan-hit-meta';
      const author = document.createElement('span');
      author.textContent = hit.author?.name || '未知作者';
      const batch = document.createElement('span');
      batch.textContent = `第 ${hit.batch || '?'} 批`;
      const pages = document.createElement('span');
      pages.textContent = `${Number(hit.page_count) || 1} 页`;
      meta.append(author, batch, pages);

      const keys = document.createElement('p');
      keys.className = 'scan-hit-keys';
      const label = document.createElement('strong');
      label.textContent = '命中字段 ';
      keys.appendChild(label);
      const cleanedKeys = Array.from(new Set((hit.field_keys || []).map((key) => (
        String(key).replace(/^\d+_p\d+\.(?:jpg|jpeg|png|webp|gif):/i, '')
      ))));
      const keyText = cleanedKeys.length
        ? `${cleanedKeys.slice(0, 3).join('、')}${cleanedKeys.length > 3 ? ` 等 ${cleanedKeys.length} 个字段` : ''}`
        : ((hit.markers || []).join('、') || '已检测到元数据');
      keys.appendChild(document.createTextNode(keyText));

      const evidence = document.createElement('p');
      evidence.className = 'scan-hit-evidence';
      evidence.textContent = hit.evidence || '';
      evidence.title = hit.evidence || '';

      const exposure = hit.exposure || {};
      let exposureLine = null;
      if (exposure.summary) {
        exposureLine = document.createElement('p');
        exposureLine.className = 'scan-hit-exposure';
        if (exposure.level) exposureLine.dataset.level = exposure.level;
        exposureLine.textContent = `暴露情况（${exposure.level || '?'}）：${exposure.summary}`;
      }

      const details = document.createElement('details');
      details.className = 'scan-exposure';
      details.dataset.hitId = String(hit.id);
      const expSummary = document.createElement('summary');
      const fieldCount = Number(hit.field_count) || (hit.field_keys || []).length;
      expSummary.textContent = `展开暴露的数据（${fieldCount} 个字段）`;
      const expBody = document.createElement('div');
      expBody.className = 'exposure-body';
      expBody.textContent = '展开后加载…';
      details.append(expSummary, expBody);
      details.addEventListener('toggle', () => {
        if (details.open) {
          state.scan.expanded.add(hit.id);
          loadHitExposure(hit.id, expBody);
        } else {
          state.scan.expanded.delete(hit.id);
        }
      });

      const actions = document.createElement('div');
      actions.className = 'scan-hit-actions';
      const detail = document.createElement('a');
      detail.href = `https://www.pixiv.net/artworks/${hit.id}`;
      detail.target = '_blank';
      detail.rel = 'noopener noreferrer';
      detail.textContent = '详细页';
      const openDir = document.createElement('button');
      openDir.type = 'button';
      openDir.textContent = '打开作品文件夹';
      openDir.addEventListener('click', () => openScanSubdir(hit.dir));
      actions.append(detail, openDir);

      body.append(title, meta);
      if (exposureLine) body.append(exposureLine);
      body.append(keys, evidence, details, actions);
      card.append(thumb, body);
      els.scanHits.appendChild(card);
      if (state.scan.expanded.has(hit.id)) {
        details.open = true;
        loadHitExposure(hit.id, expBody);
      }
    });
    if (hits.length > recent.length) {
      const more = document.createElement('p');
      more.className = 'scan-empty';
      more.textContent = `只显示最近 ${recent.length} 个命中，完整结果在扫描文件夹的 report.json / report.md。`;
      els.scanHits.appendChild(more);
    }
    els.scanHitsEmpty.hidden = hits.length > 0;
  }

  async function loadHitExposure(hitId, container) {
    if (!container) return;
    const cached = state.scan.hitDetails.get(hitId);
    if (cached) {
      renderHitExposure(container, cached);
      return;
    }
    if (container.dataset.loading === '1') return;
    container.dataset.loading = '1';
    container.textContent = '读取中…';
    const scanId = state.scan.snapshot && state.scan.snapshot.id;
    if (!scanId) {
      container.textContent = '扫描会话已结束，无法读取原始字段';
      container.dataset.loading = '0';
      return;
    }
    try {
      const data = await api(`/api/scan/${encodeURIComponent(scanId)}/hit/${hitId}`);
      state.scan.hitDetails.set(hitId, data.hit);
      renderHitExposure(container, data.hit);
    } catch (err) {
      container.textContent = `读取失败：${err.message}`;
    } finally {
      container.dataset.loading = '0';
    }
  }

  function renderHitExposure(container, hit) {
    container.textContent = '';
    const fields = hit.fields || {};
    const entries = Object.entries(fields);
    if (!entries.length) {
      const empty = document.createElement('p');
      empty.className = 'exposure-empty';
      empty.textContent = '这个作品没有可展示的原始字段。';
      container.appendChild(empty);
      return;
    }
    entries.forEach(([key, value]) => {
      const field = document.createElement('dl');
      field.className = 'exposure-field';
      const term = document.createElement('dt');
      term.textContent = key;
      const desc = document.createElement('dd');
      desc.textContent = String(value);
      field.append(term, desc);
      container.appendChild(field);
    });
  }

  function renderScanLog(log) {
    if (!Array.isArray(log) || !log.length) {
      els.scanLog.textContent = '';
      return;
    }
    els.scanLog.textContent = '';
    log.slice(-40).forEach((entry) => {
      const line = document.createElement('div');
      if (entry.level === 'error') line.className = 'log-error';
      else if (entry.level === 'warn') line.className = 'log-warn';
      const stamp = entry.t ? new Date(entry.t).toLocaleTimeString('zh-CN', { hour12: false }) : '';
      line.textContent = `${stamp}  ${entry.text || ''}`;
      els.scanLog.appendChild(line);
    });
    els.scanLog.scrollTop = els.scanLog.scrollHeight;
  }

  function finishAiScan(scan) {
    clearTimeout(state.scan.timer);
    state.scan.id = null;
    els.aiScanToggle.checked = false;
    els.aiScanStopBtn.hidden = true;
    els.scanBackBtn.hidden = false;
    els.scanBtn.disabled = false;
    updateDownloadButton();
    const tone = scan && scan.state === 'error' ? 'error' : 'ok';
    setScanStatus(scan ? scanStatusText(scan) : '已停止', tone);
    applyWorkspaceView();
    if (scan) {
      const head = scan.state === 'error' ? '扫描出错' : '扫描结束';
      els.scanPanelSummary.textContent = `${head} · ${scan.batch_index || 0} 批 · 下载 ${scan.downloaded_total || 0} 个 · 检查 ${scan.inspected_total || 0} 个 · 命中 ${scan.hits_total || 0} 个`;
      if (scan.state === 'error') {
        showToast(`扫描出错：${scan.error || '未知错误'}`, 'error');
      } else if (Number(scan.hits_total) > 0) {
        showToast(`扫描结束，命中 ${scan.hits_total} 个带残留元数据的作品`);
      } else {
        showToast('扫描结束，没有发现残留元数据');
      }
    }
  }

  async function openScanSubdir(subdir) {
    if (!subdir) {
      showToast('还没有可打开的扫描文件夹', 'error');
      return;
    }
    try {
      await api('/api/open-output', { method: 'POST', body: { subdir } });
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  function openScanRoot() {
    const rel = state.scan.snapshot && state.scan.snapshot.session_rel;
    openScanSubdir(rel);
  }

  async function adoptActiveScan() {
    try {
      const data = await api('/api/scan/active');
      if (!data.scan || data.scan.state !== 'running') return;
      state.scan.id = data.scan_id;
      state.scan.view = true;
      state.scan.lastHits = Number(data.scan.hits_total) || 0;
      els.aiScanToggle.checked = true;
      applyScanSnapshot(data.scan);
      applyWorkspaceView();
      startScanPolling();
      showToast('已恢复正在运行的 AI 元数据扫描');
    } catch {
      /* 旧后端没有该接口时忽略 */
    }
  }

  /* ── 速度曲线 ───────────────────────────────────── */

  function drawSpark(points, currentBps = 0) {
    const canvas = els.spark;
    if (!canvas) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const cssW = canvas.clientWidth || 520;
    const cssH = 64;
    if (canvas.width !== Math.round(cssW * dpr) || canvas.height !== Math.round(cssH * dpr)) {
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
    }
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const styles = getComputedStyle(document.documentElement);
    const accent = styles.getPropertyValue('--accent').trim() || '#b4402a';
    const soft = styles.getPropertyValue('--accent-soft').trim() || '#f0d8d0';
    const line = styles.getPropertyValue('--line').trim() || '#ddd0b9';
    const pad = 2;
    const w = cssW;
    const h = cssH;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    ctx.strokeStyle = line;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad, h - pad);
    ctx.lineTo(w - pad, h - pad);
    ctx.stroke();

    const series = points.slice(-60);
    const values = series.map((p) => p.bps);
    if (currentBps > 0) values.push(currentBps);
    if (!values.length) {
      ctx.strokeStyle = accent;
      ctx.globalAlpha = 0.5;
      ctx.beginPath();
      ctx.moveTo(pad, h - pad);
      ctx.lineTo(w - pad, h - pad);
      ctx.stroke();
      ctx.globalAlpha = 1;
      return;
    }
    const max = Math.max(1, ...values);
    const stepX = (w - pad * 2) / Math.max(1, values.length - 1);
    const pointsXY = values.map((v, i) => ({
      x: pad + i * stepX,
      y: h - pad - (Math.max(0, v) / max) * (h - pad * 2),
    }));

    ctx.beginPath();
    ctx.moveTo(pointsXY[0].x, h - pad);
    pointsXY.forEach((p) => ctx.lineTo(p.x, p.y));
    ctx.lineTo(pointsXY[pointsXY.length - 1].x, h - pad);
    ctx.closePath();
    ctx.fillStyle = soft;
    ctx.globalAlpha = 0.75;
    ctx.fill();
    ctx.globalAlpha = 1;

    ctx.beginPath();
    pointsXY.forEach((p, i) => {
      if (i === 0) ctx.moveTo(p.x, p.y);
      else ctx.lineTo(p.x, p.y);
    });
    ctx.strokeStyle = accent;
    ctx.lineWidth = 1.8;
    ctx.stroke();
  }

  /* ── 打开文件夹 ─────────────────────────────────── */

  async function openOutput() {
    try {
      await api('/api/open-output', { method: 'POST', body: { subdir: '' } });
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  /* ── 初始化 ─────────────────────────────────────── */

  async function init() {
    loadSettings();
    loadSavedSearches();
    bindTabs();
    bindTagInput();
    bindSelectAll();
    renderPresets();
    renderIdChips();
    renderAccount();
    drawSpark([], 0);

    els.tokenInput.addEventListener('input', () => {
      if (!state.connected) {
        els.connectNote.textContent = '密钥仅保存在本机，不会上传到任何第三方。';
        delete els.connectNote.dataset.tone;
      }
    });
    els.toggleToken.addEventListener('click', () => {
      const showing = els.tokenInput.type === 'text';
      els.tokenInput.type = showing ? 'password' : 'text';
      els.toggleToken.setAttribute('aria-label', showing ? '显示密钥' : '隐藏密钥');
      els.toggleToken.title = showing ? '显示密钥' : '隐藏密钥';
    });
    els.connectBtn.addEventListener('click', connect);
    els.extractKeyBtn.addEventListener('click', openExtractDialog);
    els.autoLoginBtn.addEventListener('click', startAutoLogin);
    els.libraryBtn.addEventListener('click', openLibraryDialog);
    els.libraryClose.addEventListener('click', closeLibraryDialog);
    els.libraryDialog.addEventListener('click', (ev) => {
      if (ev.target === els.libraryDialog) closeLibraryDialog();
    });
    els.libSearch.addEventListener('input', () => {
      clearTimeout(state.library.timer);
      state.library.timer = setTimeout(() => loadLibrary(true), 350);
    });
    [els.libSource, els.libType, els.libR18, els.libHit, els.libTag, els.libAuthor, els.libSession, els.libSort].forEach((select) => {
      select.addEventListener('change', () => loadLibrary(true));
    });
    els.libGroup.addEventListener('change', renderLibrary);
    els.libRefresh.addEventListener('click', () => loadLibrary(true, true));
    els.libMore.addEventListener('click', () => loadLibrary(false));
    els.libViewerClose.addEventListener('click', closeLibraryViewer);
    els.libViewerPrev.addEventListener('click', () => showLibraryPage(state.library.page - 1));
    els.libViewerNext.addEventListener('click', () => showLibraryPage(state.library.page + 1));
    els.libViewerFolder.addEventListener('click', openLibraryFolder);
    els.libViewerPixiv.addEventListener('click', openLibraryPixiv);
    document.addEventListener('keydown', (ev) => {
      if (els.libViewer.hidden) return;
      if (ev.key === 'Escape') {
        ev.preventDefault();
        ev.stopPropagation();
        closeLibraryViewer();
      } else if (ev.key === 'ArrowLeft') {
        ev.preventDefault();
        showLibraryPage(state.library.page - 1);
      } else if (ev.key === 'ArrowRight') {
        ev.preventDefault();
        showLibraryPage(state.library.page + 1);
      }
    });
    els.networkBtn.addEventListener('click', openSettingsDialog);
    els.settingsClose.addEventListener('click', closeSettingsDialog);
    els.settingsDialog.addEventListener('click', (ev) => {
      if (ev.target === els.settingsDialog) closeSettingsDialog();
    });
    els.proxyMode.addEventListener('change', syncProxyInputState);
    els.runSpeedtestBtn.addEventListener('click', runSpeedtest);
    els.saveSettingsBtn.addEventListener('click', saveSettingsFromForm);
    els.historyClose.addEventListener('click', closeHistoryDialog);
    els.scanHistoryBtn.addEventListener('click', openHistoryDialog);
    els.historyBackBtn.addEventListener('click', showHistoryList);
    els.historySearch.addEventListener('input', () => {
      clearTimeout(state.history.timer);
      state.history.timer = setTimeout(() => loadHistoryHits(true), 350);
    });
    els.historyLevel.addEventListener('change', () => loadHistoryHits(true));
    els.historyMore.addEventListener('click', () => loadHistoryHits(false));
    els.historyExportCsv.addEventListener('click', () => exportHistory('csv'));
    els.historyExportJson.addEventListener('click', () => exportHistory('json'));
    els.historyOpenFolder.addEventListener('click', openHistoryFolder);
    els.historyDialog.addEventListener('click', (ev) => {
      if (ev.target === els.historyDialog) closeHistoryDialog();
    });
    document.addEventListener('click', (ev) => {
      if (!els.cardMenu.hidden && !els.cardMenu.contains(ev.target)) closeCardMenu();
    });
    document.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' && !els.cardMenu.hidden) closeCardMenu();
    });
    window.addEventListener('scroll', closeCardMenu, true);
    els.scanBatchSelect.addEventListener('change', () => {
      if (state.settings) state.settings.scan_batch_size = Number(els.scanBatchSelect.value);
    });
    els.keyDialogClose.addEventListener('click', closeExtractDialog);
    els.extractOpenBtn.addEventListener('click', openPixivLogin);
    els.extractPasteBtn.addEventListener('click', pasteExtractCode);
    els.extractFinishBtn.addEventListener('click', finishExtract);
    els.refreshSourcesBtn.addEventListener('click', refreshTokenSources);
    els.extractCode.addEventListener('keydown', (ev) => {
      if ((ev.ctrlKey || ev.metaKey) && ev.key === 'Enter') {
        ev.preventDefault();
        finishExtract();
      }
    });
    els.keyDialog.addEventListener('click', (ev) => {
      if (ev.target === els.keyDialog) closeExtractDialog();
    });
    els.tokenInput.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') connect();
    });
    els.scanBtn.addEventListener('click', scan);
    els.relatedStartBtn.addEventListener('click', startRelatedCrawl);
    els.relatedNextBtn.addEventListener('click', nextBatch);
    els.relatedNextTop.addEventListener('click', nextBatch);
    els.relatedBatch.addEventListener('change', saveSettings);
    els.aiScanToggle.addEventListener('change', () => {
      if (els.aiScanToggle.checked) {
        if (state.scan.id || isScanRunning()) return;
        startAiScan();
      } else if (state.scan.id) {
        stopAiScan();
      } else {
        setScanStatus('未开启');
      }
    });
    els.aiScanStopBtn.addEventListener('click', () => {
      els.aiScanToggle.checked = false;
      stopAiScan();
    });
    els.scanBackBtn.addEventListener('click', () => {
      state.scan.view = false;
      applyWorkspaceView();
    });
    els.openScanFolderBtn.addEventListener('click', openScanRoot);
    els.saveSearchBtn.addEventListener('click', saveCurrentSearch);
    els.downloadBtn.addEventListener('click', startDownload);
    els.cancelBtn.addEventListener('click', cancelJob);
    els.retryFailedBtn.addEventListener('click', retryFailedDownloads);
    els.openOutputBtn.addEventListener('click', openOutput);
    els.openOutputTop.addEventListener('click', openOutput);
    els.concurrencyInput.addEventListener('input', () => {
      syncConcurrency();
      saveSettings();
    });
    [els.r18Toggle, els.sortSelect, els.limitSelect, els.pagesSelect, els.skipExisting, els.includeRelated, els.seedTagLimit]
      .forEach((el) => el.addEventListener('change', saveSettings));
    els.bookmarkInput.addEventListener('change', saveSettings);
    $$('input[name="workType"]').forEach((el) => el.addEventListener('change', saveSettings));
    els.idInput.addEventListener('input', renderIdChips);
    window.addEventListener('resize', () => drawSpark(state.sparkPoints, 0));

    try {
      const cfg = await api('/api/config');
      state.apiToken = cfg.api_token || '';
      state.outputDir = cfg.output_dir || '';
      applySettingsToUi(cfg.settings || null);
      if (cfg.default_token) els.tokenInput.value = cfg.default_token;
      if (cfg.has_key) {
        els.keySource.textContent = '已从密钥文件读取';
        els.keySource.title = cfg.key_file || '';
        els.rememberKey.checked = false;
      } else {
        els.keySource.textContent = '未找到密钥文件';
      }
      if (cfg.user) {
        state.connected = true;
        state.user = cfg.user;
        renderAccount();
      }
      updateDownloadButton();
      if (state.outputDir) {
        els.openOutputBtn.title = state.outputDir;
        els.openOutputTop.title = state.outputDir;
      }
    } catch (err) {
      els.keySource.textContent = '服务未就绪';
      els.keySource.title = err.message;
      setScanState(err.message, 'error');
    }

    await adoptActiveScan();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
