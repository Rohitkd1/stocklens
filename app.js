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
   Keyboard support
   ───────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('date-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') searchData();
  });
});

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
