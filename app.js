/**
 * StockLens – Frontend App
 * Calls the Flask /api/search endpoint instead of loading the CSV directly.
 */

/* ─────────────────────────────────────────────
   Search
   ───────────────────────────────────────────── */
async function searchData() {
  const dateInput = document.getElementById('date-input');
  const selectedDate = dateInput.value; // YYYY-MM-DD

  if (!selectedDate) {
    showStatus('📅 Please select a date first.', 'error');
    hideResults();
    return;
  }

  const btn = document.getElementById('search-btn');
  btn.classList.add('loading');
  btn.disabled = true;

  hideStatus();

  try {
    const res  = await fetch(`/api/search?date=${selectedDate}`);
    const body = await res.json();

    if (res.status === 404 || !body.found) {
      showStatus(
        `❌ No data found for <strong>${formatDateDisplay(selectedDate)}</strong>. ` +
        `This may be a weekend or public holiday.`,
        'error'
      );
      hideResults();
      return;
    }

    if (!res.ok) {
      showStatus(`⚠️ Server error: ${body.error || res.statusText}`, 'error');
      hideResults();
      return;
    }

    hideStatus();
    renderResults(body.data, selectedDate);

  } catch (err) {
    showStatus(
      `🔌 Cannot reach the Flask server. Make sure it is running on port 5000 or 8000.<br>` +
      `<small style="font-family:monospace">${err.message}</small>`,
      'error'
    );
    hideResults();
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

/* ─────────────────────────────────────────────
   Init
   ───────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  // Search keyboard shortcut
  document.getElementById('date-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') searchData();
  });

  // Load git status into header bar
  loadGitStatus();

  // Drag-and-drop wiring
  const dropZone  = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) setDropFile(fileInput.files[0]);
  });

  dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', ()  => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) setDropFile(file);
  });
});

/* ─────────────────────────────────────────────
   Git Status Bar
   ───────────────────────────────────────────── */
async function loadGitStatus() {
  try {
    const res  = await fetch('/api/git-status');
    const data = await res.json();
    if (data.branch) document.getElementById('git-branch').textContent = data.branch;
    if (data.hash)   document.getElementById('git-hash').textContent   = data.hash;
    if (data.message) document.getElementById('git-msg').textContent   = '· ' + data.message;
    if (data.repo)   document.getElementById('git-status-bar').href    = data.repo;
  } catch (_) {}
}

/* ─────────────────────────────────────────────
   Upload & Deploy
   ───────────────────────────────────────────── */
let _selectedFile = null;

function setDropFile(file) {
  _selectedFile = file;
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['csv', 'xlsx', 'xls'].includes(ext)) {
    showUploadResult(`❌ Unsupported file type: .${ext}. Use .csv or .xlsx`, 'error');
    _selectedFile = null;
    return;
  }
  const label = document.getElementById('drop-filename');
  label.textContent = `📄 ${file.name}  (${(file.size / 1024).toFixed(1)} KB)`;
  label.classList.remove('hidden');
  document.getElementById('upload-btn').disabled = false;
  document.getElementById('upload-result').classList.add('hidden');
}

async function uploadDataset() {
  if (!_selectedFile) return;

  const btn       = document.getElementById('upload-btn');
  const commitMsg = document.getElementById('commit-msg').value.trim();

  btn.classList.add('uploading');
  btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="animation:spin 1s linear infinite"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Uploading...`;

  const form = new FormData();
  form.append('dataset', _selectedFile);
  if (commitMsg) form.append('commit_msg', commitMsg);

  try {
    const res  = await fetch('/api/upload', { method: 'POST', body: form });
    const data = await res.json();

    if (!res.ok || data.error) {
      showUploadResult(`❌ ${data.error || 'Upload failed'}`, 'error');
      return;
    }

    // Success
    const pushIcon  = data.push_ok ? '✅' : '⚠️';
    const pushNote  = data.push_ok
      ? 'Jenkins pipeline will auto-trigger shortly.'
      : 'Push failed — run <code>git push</code> manually to trigger Jenkins.';

    showUploadResult(`
      ✅ <strong>${data.filename}</strong> uploaded successfully<br>
      📊 ${data.rows.toLocaleString()} rows &nbsp;·&nbsp; ${data.date_range}<br>
      ${pushIcon} ${pushNote}
      <div class="git-line">${data.git_log.join('<br>')}</div>
    `, 'success');

    // Refresh git status bar
    loadGitStatus();

    // Reset file selector
    _selectedFile = null;
    document.getElementById('file-input').value = '';
    document.getElementById('drop-filename').classList.add('hidden');
    document.getElementById('upload-btn').disabled = true;

  } catch (err) {
    showUploadResult(`🔌 Cannot reach Flask server.<br><small>${err.message}</small>`, 'error');
  } finally {
    btn.classList.remove('uploading');
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/></svg> Push to Git`;
  }
}

function showUploadResult(html, type) {
  const el = document.getElementById('upload-result');
  el.innerHTML = html;
  el.className = `upload-result ${type}`;
  el.classList.remove('hidden');
}

/* Add spin animation for loading icon */
const style = document.createElement('style');
style.textContent = `@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`;
document.head.appendChild(style);


/* ─────────────────────────────────────────────
   Rendering
   ───────────────────────────────────────────── */
function renderResults(data, dateStr) {
  document.getElementById('results-date').textContent =
    `Trading session · ${formatDateDisplay(dateStr)}`;

  renderSignalBadge(data['BUY/SELL']);

  renderGrid('price-grid', [
    { label: 'Open',      value: fmtNum(data['Open']),      accent: 'accent-open'  },
    { label: 'High',      value: fmtNum(data['High']),      accent: 'accent-high'  },
    { label: 'Low',       value: fmtNum(data['Low']),       accent: 'accent-low'   },
    { label: 'Close',     value: fmtNum(data['Close']),     accent: 'accent-close' },
    { label: 'Adj Close', value: fmtNum(data['Adj Close'])                         },
  ]);

  renderGrid('volume-grid', [
    { label: 'Volume', value: fmtInt(data['Volume']) },
    { label: 'VWAP',   value: fmtNum(data['Volume Weighted Average Price']) },
  ]);

  const rsi = parseFloat(data['RSI']);
  renderGrid('momentum-grid', [
    { label: 'RSI (14)',           value: fmtNum(data['RSI']),                           colorClass: rsiColor(rsi) },
    { label: 'EMA 12',             value: fmtNum(data['EMA 12'])                          },
    { label: 'EMA 26',             value: fmtNum(data['EMA 26'])                          },
    { label: 'MACD',               value: fmtNum(data['MACD']),                           colorClass: signColor(data['MACD']) },
    { label: 'Rate of Change 10d', value: fmtNum(data['Rate of Change (10 days)']),       colorClass: signColor(data['Rate of Change (10 days)']) },
    { label: 'William %R',         value: fmtNum(data['William % R']),                    colorClass: signColor(data['William % R']) },
    { label: 'CCI',                value: fmtNum(data['Commodity Channel Index']),         colorClass: signColor(data['Commodity Channel Index']) },
  ]);

  renderGrid('bands-grid', [
    { label: 'Upper Bollinger', value: fmtNum(data['Upper Bollinger band'])              },
    { label: 'Lower Bollinger', value: fmtNum(data['Lower Bollinger band'])              },
    { label: '%K Stoch (5d)',   value: fmtNum(data['%K (5 days stochastic oscillator)']) },
    { label: '%D Average',      value: fmtNum(data['%D Average(H,3)'])                   },
  ]);

  renderGrid('trend-grid', [
    { label: 'Aroon Up',   value: fmtNum(data['Aroon Up']),   colorClass: 'positive' },
    { label: 'Aroon Down', value: fmtNum(data['Aroon Down']), colorClass: 'negative' },
  ]);

  const section = document.getElementById('results-section');
  section.classList.remove('hidden');
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderGrid(gridId, items) {
  const grid = document.getElementById(gridId);
  grid.innerHTML = '';
  items.forEach(item => {
    const card = document.createElement('div');
    card.className = `metric-card${item.accent ? ' ' + item.accent : ''}`;
    card.innerHTML = `
      <div class="metric-label">${item.label}</div>
      <div class="metric-value${item.colorClass ? ' ' + item.colorClass : ''}">${item.value}</div>
    `;
    grid.appendChild(card);
  });
}

function renderSignalBadge(rawSignal) {
  const badge = document.getElementById('signal-badge');
  const val = parseInt(rawSignal, 10);

  if (val === 1) {
    badge.className = 'signal-badge buy';
    badge.innerHTML = `<span>▲</span> BUY`;
  } else if (val === -1) {
    badge.className = 'signal-badge sell';
    badge.innerHTML = `<span>▼</span> SELL`;
  } else {
    badge.className = 'signal-badge hold';
    badge.innerHTML = `<span>━</span> HOLD / N/A`;
  }
}

/* ─────────────────────────────────────────────
   Helpers
   ───────────────────────────────────────────── */
function fmtNum(val) {
  if (val === null || val === undefined) return '—';
  const n = parseFloat(val);
  if (isNaN(n)) return String(val);
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function fmtInt(val) {
  if (val === null || val === undefined) return '—';
  const n = parseInt(val, 10);
  if (isNaN(n)) return String(val);
  return n.toLocaleString('en-US');
}

function signColor(val) {
  const n = parseFloat(val);
  if (isNaN(n)) return '';
  if (n > 0) return 'positive';
  if (n < 0) return 'negative';
  return 'neutral';
}

function rsiColor(rsi) {
  if (isNaN(rsi)) return '';
  if (rsi > 70) return 'negative';
  if (rsi < 30) return 'positive';
  return 'neutral';
}

function formatDateDisplay(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${d} ${months[parseInt(m, 10) - 1]} ${y}`;
}

function showStatus(html, type) {
  const el = document.getElementById('status-msg');
  el.innerHTML = html;
  el.className = `status-msg ${type}`;
  el.classList.remove('hidden');
}

function hideStatus() {
  document.getElementById('status-msg').classList.add('hidden');
}

function hideResults() {
  document.getElementById('results-section').classList.add('hidden');
}
