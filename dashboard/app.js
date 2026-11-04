import {PAGE_SIZE, escapeHTML as esc, safeURL, selectRows, formatValue, boardFreshness, otherMatches} from './model.js';

const $ = selector => document.querySelector(selector);
const state = {data: null, board: '', page: 0, expanded: null};
const friendlyDate = date => date ? new Date(date.slice(0, 10) + 'T00:00:00Z').toLocaleDateString('en-GB', {day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC'}) : null;
const link = (url, text) => safeURL(url) ? `<a href="${esc(safeURL(url))}" target="_blank" rel="noopener">${esc(text)} ↗</a>` : esc(text);

function changeBoard(id, keepQuery = true) {
  if (!state.data.boards[id]) return;
  state.board = id; state.page = 0; state.expanded = null;
  if (!keepQuery) $('#search').value = '';
  const url = new URL(location.href); url.searchParams.set('board', id); history.replaceState({}, '', url);
  renderBoard();
}

function renderTabs() {
  $('#board-tabs').innerHTML = Object.entries(state.data.boards).map(([id, b]) => `<button class="board-tab" type="button" data-board="${esc(id)}" aria-pressed="${id === state.board}"><span class="tab-top"><span class="tab-name">${esc(b.label)}</span><span class="tab-count">${b.n_scored}</span></span><span class="tab-sub">${esc(b.subtitle)}</span></button>`).join('');
  $('#board-tabs').querySelectorAll('button').forEach(button => button.addEventListener('click', () => changeBoard(button.dataset.board)));
}

function renderBoard() {
  const board = state.data.boards[state.board];
  renderTabs();
  $('#board-title').textContent = board.version;
  $('#board-kicker').textContent = `${board.label} / ${board.unit === 'percent' ? 'SYSTEM PERFORMANCE' : 'SOURCE-NATIVE RANKING'}`;
  $('#board-description').textContent = state.board === 'terminal_bench' ? 'A model + agent comparison. Different harnesses are different systems.' : `${board.metric} · original source scale · exact configurations retained`;
  const sourceURL = safeURL(board.url); $('#source-link').hidden = !sourceURL;
  if (sourceURL) $('#source-link').href = sourceURL;
  const status = boardFreshness(board, state.data.freshness);
  $('#freshness').innerHTML = `<span class="pill ${status !== 'available' ? 'warning' : ''}">${esc(status === 'available' ? 'SNAPSHOT AVAILABLE' : status.toUpperCase())}</span><span>Published <strong>${esc(friendlyDate(board.published_at) || 'not supplied')}</strong></span><span>Observed <strong>${esc(friendlyDate(board.observed_at) || 'not recorded')}</strong></span>${!board.published_at ? '<span class="unknown">Evaluation date unknown</span>' : ''}`;
  const warnings = (board.warnings || []).filter(message => !message.startsWith('Evaluation/publication date'));
  if (status === 'stale' || status === 'expired') warnings.unshift(`This snapshot is ${status}. It is retained for reference, not presented as a current ranking.`);
  if (board.last_fetch?.status === 'failed') warnings.push(`Refresh attempt ${board.last_fetch.attempted_at.slice(0, 10)}: ${board.last_fetch.error}`);
  $('#warnings').innerHTML = warnings.map(message => `<p>${esc(message)}</p>`).join('');
  const key = state.board === 'terminal_bench' ? 'harness' : 'provider';
  const options = [...new Set(board.rows.map(row => row[key]).filter(Boolean))].sort();
  $('#filter-label').textContent = key === 'harness' ? 'Harness' : 'Creator';
  $('#filter').innerHTML = '<option value="">All entries</option>' + options.map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join('');
  if (state.board === 'livebench') {
    $('#filter-label').textContent = 'Weights';
    $('#filter').innerHTML = '<option value="">All entries</option><option value="open">Source-labeled open</option>';
  }
  $('#filter').parentElement.hidden = !options.length && state.board !== 'livebench';
  const sortOptions = [{key:'score', label:'Score', type:'number'}, ...(board.columns || []).filter(c => ['money','number','integer'].includes(c.type))];
  $('#sort').innerHTML = sortOptions.map(c => `<option value="${esc(c.key)}:${c.type === 'money' ? 'asc' : 'desc'}">${esc(c.label)} · ${c.type === 'money' ? 'lowest' : 'highest'} first</option>`).join('');
  if (board.suites) $('#sort').innerHTML += board.suites.filter(key => !sortOptions.some(c => c.key === key)).map(key => `<option value="${key}:desc">${esc(key.replaceAll('_',' '))} · highest first</option>`).join('');
  $('#table-note').textContent = board.qualification;
  renderProvenance(board);
  renderRows();
}

function detailsHTML(row, board, colspan) {
  const cols = [
    ['Configuration', row.model], ['Source', board.label], ['Metric version', board.version],
    ['Published', friendlyDate(board.published_at) || 'Not supplied'],
    ['Observed (retrieval only)', friendlyDate(board.observed_at) || 'Not recorded'],
    ['95% interval', row.ci95 ? formatValue(row.ci95, 'interval', board.decimals) : 'Not supplied — none estimated'],
    ...board.columns.map(c => [c.label, formatValue(row[c.key], c.type, c.decimals ?? board.decimals)]),
    ...(board.suites || []).map(key => [key.replaceAll('_', ' '), formatValue(row[key])]),
  ];
  return `<tr class="detail-row"><td colspan="${colspan}"><dl class="detail-grid">${cols.map(([label,value]) => `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`).join('')}</dl>${link(board.source || board.url, 'Verify at the original source')}</td></tr>`;
}

function renderRows() {
  if (!state.data) return;
  const board = state.data.boards[state.board];
  const query = $('#search').value;
  const rows = selectRows(board, {query, filter: $('#filter').value, sort: $('#sort').value});
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  state.page = Math.min(state.page, pageCount - 1);
  const slice = rows.slice(state.page * PAGE_SIZE, (state.page + 1) * PAGE_SIZE);
  const columns = board.columns || [];
  const activeMetric = $('#sort').value.split(':')[0];
  const visibleColumns = [...columns];
  if (activeMetric !== 'score' && !columns.some(c => c.key === activeMetric)) visibleColumns.push({key: activeMetric, label: activeMetric.replaceAll('_', ' '), type: 'number'});
  $('#table-container').setAttribute('aria-busy', 'false');
  if (!rows.length) {
    $('#table-container').innerHTML = `<p class="empty">${board.rows.length ? 'No entries match these filters. Try another source — absence is not a low score.' : 'No verified snapshot is available for this board. Run a refresh or inspect the source directly.'}</p>`;
  } else {
    $('#table-container').innerHTML = `<table><caption class="sr-only">${esc(board.label)} ${esc(board.version)}. Rank is the within-source score rank; ties share a rank. Select a model to inspect evidence.</caption><thead><tr><th scope="col">Rank</th><th scope="col">Model / configuration</th><th scope="col">${esc(board.metric)}</th>${visibleColumns.map(c => `<th scope="col">${esc(c.label)}</th>`).join('')}</tr></thead><tbody>${slice.map((row, index) => `<tr class="model-row"><td class="rank">${row.rank ?? '—'}</td><td class="model-cell"><button type="button" class="model-name" data-index="${index}" aria-expanded="${state.expanded === row.id}">${esc(row.model)}<span aria-hidden="true">${state.expanded === row.id ? '−' : '+'}</span></button>${row.open_weights === true ? '<span class="entry-tag">OPEN</span>' : ''}</td><td class="score-cell">${formatValue(row.score, 'number', board.decimals)}${board.unit === 'percent' && row.score != null ? '<small>%</small>' : ''}</td>${visibleColumns.map(c => `<td class="${row[c.key] == null ? 'zero-null' : ''}">${esc(formatValue(row[c.key], c.type, c.decimals ?? board.decimals))}</td>`).join('')}</tr>${state.expanded === row.id ? detailsHTML(row, board, visibleColumns.length + 3) : ''}`).join('')}</tbody></table>`;
    $('#table-container').querySelectorAll('button[data-index]').forEach(button => button.addEventListener('click', () => {
      const row = slice[Number(button.dataset.index)]; const index = button.dataset.index;
      state.expanded = state.expanded === row.id ? null : row.id;
      renderRows(); $('#table-container').querySelector(`button[data-index="${index}"]`)?.focus({preventScroll:true});
    }));
  }
  $('#result-count').textContent = rows.length ? `${state.page * PAGE_SIZE + 1}–${Math.min((state.page + 1) * PAGE_SIZE, rows.length)} of ${rows.length} entries · source ranks preserved` : '0 matching entries';
  $('#page-number').textContent = `${state.page + 1} / ${pageCount}`;
  $('#previous').disabled = state.page === 0; $('#next').disabled = state.page + 1 >= pageCount;
  const matches = otherMatches(state.data.boards, state.board, query);
  $('#discovery').innerHTML = matches.length ? 'Also found in: ' + matches.map(item => `<button type="button" data-board="${esc(item.id)}">${esc(item.label)} (${item.count}) ↗</button>`).join('') : '';
  $('#discovery').querySelectorAll('button').forEach(button => button.addEventListener('click', () => changeBoard(button.dataset.board)));
}

function renderProvenance(board) {
  $('#provenance').innerHTML = `<p>${esc(board.qualification)}</p><p>${link(board.source || board.url, 'Original data')} · ${link(board.methodology_url, 'Source methodology')}</p><p><strong>Scope:</strong> ${esc(board.scope || 'No valid snapshot')}<br><strong>Collection:</strong> ${esc((board.retrieval_method || 'unknown').replaceAll('_', ' '))}<br><strong>Data fingerprint:</strong> <code>${esc(board.data_hash || '—')}</code><br><strong>Last refresh:</strong> ${esc(board.last_fetch ? `${board.last_fetch.status} · ${board.last_fetch.attempted_at}` : 'No automatic attempt recorded for this snapshot')}</p><p>Source-native scores are never added to their component benchmarks in the composite. Shared ranks reflect equal supplied scores, not proof of equal ability. The source’s roster can include restricted, preview, or historical models.</p>`;
}

async function load() {
  $('#reload').disabled = true;
  try {
    const response = await fetch('../output/leaderboards.json', {cache:'no-store'});
    if (!response.ok) throw new Error(`Could not load leaderboard snapshots (HTTP ${response.status}).`);
    const data = await response.json();
    if (data.schema_version !== 1 || !data.boards || !data.boards[data.default_board]) throw new Error('Unsupported or incomplete leaderboard data. Rebuild with python -m hierarchy boards.');
    state.data = data;
    $('#entry-count').textContent = Object.values(data.boards).reduce((total,b) => total + b.n_scored, 0).toLocaleString('en-US');
    $('#source-count').textContent = Object.keys(data.boards).length;
    $('#snapshot-date').textContent = friendlyDate(data.generated_at);
    const requested = state.board || new URLSearchParams(location.search).get('board');
    changeBoard(data.boards[requested] ? requested : data.default_board);
  } catch (error) {
    state.data = null;
    $('#board-title').textContent = 'Snapshot unavailable';
    $('#board-tabs').replaceChildren(); $('#warnings').replaceChildren(); $('#freshness').replaceChildren();
    $('#source-link').hidden = true; $('#provenance').replaceChildren(); $('#discovery').replaceChildren();
    $('#table-container').innerHTML = `<p class="empty error">${esc(error.message)}\nNo synthetic or cached rankings have been substituted. Use Reload snapshot to retry.</p>`;
    $('#table-container').setAttribute('aria-busy', 'false');
    $('#result-count').textContent = ''; $('#page-number').textContent = '';
    $('#entry-count').textContent = '—'; $('#previous').disabled = true; $('#next').disabled = true;
  } finally { $('#reload').disabled = false; }
}

async function loadAudit() {
  try {
    const response = await fetch('../output/leaderboard.json', {cache:'no-store'});
    if (!response.ok) throw new Error('Audit unavailable');
    const composite = await response.json(); const quality = composite.quality;
    if (!quality || composite.demo) throw new Error('No live audit available');
    $('#composite-audit').innerHTML = `<p><strong>Experimental composite: ${esc(quality.status)}.</strong> ${quality.roster_size} models in its evidence roster; ${composite.cohort_size} meet comparable-data requirements before publication gates.</p><ul>${quality.blockers.map(message => `<li>${esc(message)}</li>`).join('')}</ul><p>The legacy composite requires at least five distinct measurements across three pillars, a multi-model comparison cohort, and evidence in every capability domain across that cohort. Split aliases count once. No OpenRouter usage gate, no invented scores for missing tests, no single-model “T1”.</p><p><a href="../output/leaderboard.json">Inspect composite and unranked evidence JSON ↗</a></p>`;
  } catch {
    $('#composite-audit').textContent = 'Composite evidence audit unavailable. Source-native results above remain separate; no universal tier claims are made.';
  }
}

$('#search').addEventListener('input', () => { state.page = 0; renderRows(); });
for (const selector of ['#filter', '#sort']) $(selector).addEventListener('change', () => { state.page = 0; renderRows(); });
$('#previous').addEventListener('click', () => { state.page--; renderRows(); });
$('#next').addEventListener('click', () => { state.page++; renderRows(); });
$('#reload').addEventListener('click', () => { load(); loadAudit(); });
load(); loadAudit();
