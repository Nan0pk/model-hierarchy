import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM} from 'jsdom';
import {atlasHierarchy} from '../dashboard/hierarchy.js';
import * as helpers from '../dashboard/model.js';

const {selectRows, formatValue, boardFreshness, escapeHTML, safeURL, otherMatches} = helpers;
const baseBoard = {
  label: 'Test evaluator', version: 'Test v1', subtitle: 'Test only', metric: 'Score', unit: 'points',
  decimals: 1, published_at: null, observed_at: '2026-11-03', status: 'available',
  url: 'https://example.test/board', source: 'https://example.test/board', methodology_url: 'https://example.test/method',
  qualification: 'Fixture; not real model evaluations.', warnings: [], n_scored: 3,
  columns: [{key:'provider',label:'Creator',type:'text'}, {key:'cost_per_task',label:'$/task',type:'money'}],
  rows: [{id:'a-high',model:'Model A (high)',rank:1,score:50,provider:'Lab A',cost_per_task:null},
         {id:'a-max',model:'Model A (max)',rank:1,score:50,provider:'Lab A',cost_per_task:2},
         {id:'b',model:'Model B',rank:3,score:0,provider:'Lab B',cost_per_task:0},
         {id:'c',model:'Model C',rank:null,score:null,provider:'Lab C',cost_per_task:null}],
};
const fixture = () => ({schema_version:1, generated_at:'2026-11-03T12:00:00Z', default_board:'artificial_analysis',
  freshness:{warn_after_days:14,expire_after_days:90},
  boards:{artificial_analysis:structuredClone(baseBoard), terminal_bench:{...structuredClone(baseBoard),label:'Systems',
    columns:[{key:'harness',label:'Agent harness',type:'text'}],n_scored:1,
    rows:[{id:'a-agent',model:'Model A (max)',harness:'Agent X',rank:1,score:42}]}},
});

test('source ranks, effort settings, ties and absent data survive filtering', () => {
  const rows = selectRows(baseBoard, {query:'Model A'});
  assert.equal(rows.length, 2);
  assert.deepEqual(rows.map(r => r.rank), [1,1]);
  assert.equal(selectRows(baseBoard, {query:'model b'})[0].rank, 3);
  assert.equal(selectRows(baseBoard, {filter:'Lab B'})[0].score, 0);
  assert.equal(baseBoard.rows.length, 4);
});

test('cost sorting never turns missing cost into free', () => {
  const rows = selectRows(baseBoard, {sort:'cost_per_task:asc'});
  assert.equal(rows[0].model, 'Model B');
  assert.equal(rows[1].model, 'Model A (max)');
  assert.equal(rows.at(-1).cost_per_task, null);
  assert.equal(formatValue(null, 'money'), '—');
  assert.equal(formatValue(0, 'number'), '0.0');
});

test('age progresses on the client even without rebuilding the static JSON', () => {
  const policy = {warn_after_days:14,expire_after_days:90};
  assert.equal(boardFreshness(baseBoard, policy, new Date('2026-11-03T23:00:00Z')), 'available');
  assert.equal(boardFreshness(baseBoard, policy, new Date('2026-11-18T00:00:00Z')), 'stale');
  assert.equal(boardFreshness(baseBoard, policy, new Date('2027-03-01T00:00:00Z')), 'expired');
  assert.equal(boardFreshness({...baseBoard, published_at:'2025-01-01'}, policy, new Date('2026-11-03')), 'expired');
  assert.equal(boardFreshness({...baseBoard, observed_at:'garbage'}, policy), 'invalid');
});

test('unsafe source links and names cannot create HTML', () => {
  assert.equal(safeURL('javascript:alert(1)'), null);
  assert.equal(safeURL('https://example.test/'), 'https://example.test/');
  assert.equal(escapeHTML('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
});

test('cross-source discovery is independent of benchmark eligibility', () => {
  const data = fixture();
  assert.equal(otherMatches(data.boards, 'artificial_analysis', 'model a')[0].count, 1);
  assert.deepEqual(otherMatches(data.boards, 'artificial_analysis', ''), []);
});

async function page(data = fixture(), failing = false, query = '?board=artificial_analysis', setupWindow = () => {}) {
  const html = await readFile(new URL('../dashboard/index.html', import.meta.url), 'utf8');
  const source = await readFile(new URL('../dashboard/app.js', import.meta.url), 'utf8');
  const dom = new JSDOM(html, {url:'https://atlas.test/dashboard/' + query, runScripts:'outside-only'});
  const win = dom.window;
  setupWindow(win);
  Object.assign(win, helpers, {esc:helpers.escapeHTML, atlasHierarchy});
  win.fetch = async url => {
    if (failing) return {ok:false,status:503};
    return {ok:true, json:async () => url.endsWith('leaderboards.json') ? structuredClone(data) : {
      quality:{status:'withheld',roster_size:8,blockers:['Math evidence is absent.']},cohort_size:3,
    }};
  };
  win.eval(source.replace(/^import .*;$/gm, ''));
  await new Promise(resolve => setImmediate(resolve));
  return {dom, win, doc:win.document};
}

test('dashboard renders native ranks and explicit unknown dates, not synthetic fallback', async () => {
  const {win, doc} = await page();
  assert.equal(doc.querySelectorAll('.model-row').length, 4);
  assert.match(doc.querySelector('#freshness').textContent, /Evaluation date unknown/);
  assert.match(doc.querySelector('#composite-audit').textContent, /withheld/);
  assert.equal(doc.querySelector('#entry-count').textContent, '4');
  win.close();
});

test('source switching, searching and expanding evidence work', async () => {
  const {win, doc} = await page();
  const input = doc.querySelector('#search'); input.value = 'Model B';
  input.dispatchEvent(new win.Event('input'));
  assert.equal(doc.querySelectorAll('.model-row').length, 1);
  assert.equal(doc.querySelector('.rank').textContent, '3');
  input.value = ''; input.dispatchEvent(new win.Event('input'));
  doc.querySelector('.model-name').click();
  assert.match(doc.querySelector('.detail-row').textContent, /Not supplied — none estimated/);
  doc.querySelector('#source-choice').value = 'terminal_bench';
  doc.querySelector('#source-choice').dispatchEvent(new win.Event('change'));
  assert.equal(doc.querySelectorAll('.model-row').length, 1);
  assert.match(doc.querySelector('#table-container').textContent, /Agent X/);
  assert.match(win.location.search, /board=terminal_bench/);
  assert.equal(doc.querySelector('#filter-label').textContent, 'Harness');
  win.close();
});

test('empty search state does not masquerade as no live data', async () => {
  const {win, doc} = await page();
  const search = doc.querySelector('#search'); search.value = 'no-such-model';
  search.dispatchEvent(new win.Event('input'));
  assert.match(doc.querySelector('#table-container').textContent, /No entries match/);
  assert.equal(doc.querySelector('#next').disabled, true);
  win.close();
});

test('pagination works without re-numbering score ranks', async () => {
  const data = fixture();
  data.boards.artificial_analysis.rows = Array.from({length:31}, (_,i) => ({id:String(i),model:`Model ${i}`,rank:i+1,score:100-i}));
  data.boards.artificial_analysis.n_scored = 31;
  const {win, doc} = await page(data);
  assert.equal(doc.querySelectorAll('.model-row').length, 25);
  doc.querySelector('#next').click();
  assert.equal(doc.querySelectorAll('.model-row').length, 6);
  assert.equal(doc.querySelector('.rank').textContent, '26');
  assert.equal(doc.querySelector('#next').disabled, true);
  doc.querySelector('#previous').click();
  assert.equal(doc.querySelector('.rank').textContent, '1');
  win.close();
});

test('untrusted model markup is rendered as text', async () => {
  const data = fixture(); data.boards.artificial_analysis.rows[0].model = '<img src=x onerror="alert(1)">';
  const {win, doc} = await page(data);
  assert.equal(doc.querySelector('#table-container img'), null);
  assert.match(doc.querySelector('#table-container').textContent, /<img src=x/);
  win.close();
});

test('HTTP failure has a recoverable error and no substitute rankings', async () => {
  const {win, doc} = await page(fixture(), true);
  assert.match(doc.querySelector('.error').textContent, /HTTP 503/);
  assert.equal(doc.querySelectorAll('.model-row').length, 0);
  assert.equal(doc.querySelector('#reload').disabled, false);
  win.close();
});

test('Atlas computes tie-aware percentiles, aggregates settings once and isolates systems', () => {
  const data = fixture();
  data.boards.arena_text = structuredClone(baseBoard);
  data.boards.arena_text.rows[1].model = 'Model A (max)';
  data.boards.arena_text.rows[0].score = 100;
  data.boards.arena_text.rows.push({id:'a-fb', model:'Model A (max, Default Fallback)', rank:2, score:50, provider:'Lab A'});
  const now = new Date('2026-11-04');
  const models = atlasHierarchy(data.boards, data.freshness, false, now);
  assert.equal(models.n_scored, 2);
  assert.deepEqual(models.rows.find(r => r.model === 'Model A').evidence.map(e => e.observations.length), [2, 3]);
  assert.equal(models.rows.find(r => r.model === 'Model B').score, 0);
  const effort = atlasHierarchy(data.boards, data.freshness, true, now);
  assert.equal(effort.n_scored, 2);
  const high = effort.rows.find(r => r.model === 'Model A (high)');
  // Tied on AA (50 each side of a tie), separated on Arena: 100 beats 50.
  assert.deepEqual([high.rank, high.artificial_analysis, high.arena_text, high.score], [1, 50, 100, 75]);
  assert.equal(effort.rows.find(r => r.model === 'Model A (max)').score, 25);
  // A fallback policy is its own configuration, and one evaluator cannot rank it.
  const fallback = effort.rows.find(r => r.model === 'Model A (max, Default Fallback)');
  assert.deepEqual([fallback.rank, fallback.arena_text], [null, 25]);
  data.boards.arena_text.published_at = '2020-01-01';
  assert.equal(atlasHierarchy(data.boards, data.freshness, true, now).n_scored, 0);
});

test('Atlas joins evaluators by canonical name and reviewed aliases, never by loose matching', () => {
  const data = fixture();
  const now = new Date('2026-11-04');
  const rows = names => names.map(([model, score], i) => ({id: `r${i}`, model, rank: null, score, provider: 'Lab'}));
  data.boards.artificial_analysis.rows = rows([['MiniMax-M3.1-Flash', 10], ['Command R', 5], ['Qwen3.8-Max', 8], ['Foo-Bar (High)', 3]]);
  data.boards.arena_text = {...structuredClone(baseBoard),
    rows: rows([['MiniMax M3.1 Flash', 20], ['Command R+', 7], ['Qwen 3.8 Max', 9], ['Foo Bar (high)', 4]])};
  const aliases = {'qwen 3.8 max': 'qwen3.8 max'};
  const atlas = atlasHierarchy(data.boards, data.freshness, false, now, aliases);
  const sources = model => atlas.rows.filter(r => r.model === model).map(r => r.evidence.length);
  assert.deepEqual(sources('MiniMax-M3.1-Flash'), [2]);
  assert.deepEqual(sources('Qwen3.8-Max'), [2]);
  assert.deepEqual([sources('Command R'), sources('Command R+')], [[1], [1]]);
  assert.equal(atlasHierarchy(data.boards, data.freshness, false, now).rows.filter(r => /qwen/i.test(r.model)).length, 2);
  const effort = atlasHierarchy(data.boards, data.freshness, true, now, aliases);
  assert.deepEqual(effort.rows.map(r => r.evidence.length), [2]);
});

test('single-evaluator padding cannot move the percentiles of shared models', () => {
  const data = fixture();
  const now = new Date('2026-11-04');
  data.boards.arena_text = structuredClone(baseBoard);
  data.boards.arena_text.rows[0].score = 100;
  const before = atlasHierarchy(data.boards, data.freshness, false, now);
  for (let i = 0; i < 100; i++) data.boards.arena_text.rows.push({id: `old${i}`, model: `Old ${i}`, rank: null, score: -i, provider: 'Lab'});
  const after = atlasHierarchy(data.boards, data.freshness, false, now);
  const view = h => h.rows.filter(r => r.rank).map(r => [r.model, r.arena_text, r.score]);
  assert.deepEqual(view(after), view(before));
  // Placed against the shared field (A at 75, B at 0): ties B, so half a step above the bottom.
  assert.equal(after.rows.find(r => r.model === 'Old 0').arena_text, 25);
});

test('default dashboard shows the Atlas ranking and exact effort evidence', async () => {
  const data = fixture();
  data.boards.livebench = structuredClone(baseBoard);
  for (const board of Object.values(data.boards)) board.observed_at = new Date().toISOString().slice(0, 10);
  const {win, doc} = await page(data, false, '');
  assert.equal(doc.querySelector('#board-title').textContent, 'Model hierarchy');
  assert.equal(doc.querySelector('.model-name').textContent, 'Model A+');
  doc.querySelector('[data-board="effort"]').click();
  assert.equal(doc.querySelectorAll('.model-row').length, 2);
  assert.deepEqual([...doc.querySelectorAll('.rank')].map(td => td.textContent), ['1', '1']);
  doc.querySelector('.model-name').click();
  assert.match(doc.querySelector('.detail-row').textContent, /Model A .* · 50/);
  win.close();
});

test('ranking coverage, one-source filter, and fetch health stay distinct', async () => {
  const data = fixture();
  data.boards.arena_text = structuredClone(baseBoard);
  data.boards.arena_text.rows = data.boards.arena_text.rows.filter(r => r.model !== 'Model B');
  data.boards.arena_text.rows.push({id:'other', model:'Model D', score:20});
  // Percentiles need a shared field of at least two models.
  for (const b of [data.boards.artificial_analysis, data.boards.arena_text]) b.rows.push({id:'e', model:'Model E', score:60});
  for (const b of Object.values(data.boards)) b.observed_at = new Date().toISOString().slice(0, 10);
  data.boards.arena_text.last_fetch = {status:'failed', attempted_at:new Date().toISOString()};
  const {win, doc} = await page(data, false, '');
  assert.equal(doc.querySelectorAll('.model-row').length, 2);
  assert.equal(doc.querySelector('.coverage').textContent, '2 evaluators');
  assert.equal(doc.querySelectorAll('.heat-tile').length, 4);
  assert.match(doc.querySelector('#warnings').textContent, /available · last fetch failed/);
  assert.match(doc.querySelector('#source-health').textContent, /PublishedUnknown/);
  const filter = doc.querySelector('#filter');
  filter.value = 'single';
  filter.dispatchEvent(new win.Event('change'));
  assert.equal(doc.querySelectorAll('.model-row').length, 2);
  assert.equal(doc.querySelector('.rank').textContent, '—');
  assert.equal(doc.querySelectorAll('.heat--1').length, 2);
  assert.equal(doc.querySelectorAll('.heat-tile.heat-0').length, 2);
  assert.match(doc.querySelector('.heat-tile.heat-0').textContent, /0\.0/);
  win.close();
});

test('Atlas shows task prices, sorts missing prices last and keeps success costs separate', async () => {
  const data = fixture();
  const aa = data.boards.artificial_analysis;
  aa.rows[0].cost_per_task = 1;
  aa.rows[2].cost_per_task = null;
  data.boards.livebench = structuredClone(aa);
  data.boards.livebench.rows[0].cost_per_success = 2.345;
  for (const b of Object.values(data.boards)) b.observed_at = new Date().toISOString().slice(0, 10);
  const {win, doc} = await page(data, false, '');
  const cells = () => [...doc.querySelectorAll('td[data-source="cost_per_task"]')].map(c => c.textContent);
  assert.deepEqual(cells(), ['$1.50', '—']);
  doc.querySelector('.model-name').click();
  assert.match(doc.querySelector('.detail-row').textContent, /\$1\.00\/task/);
  assert.match(doc.querySelector('.detail-row').textContent, /\$2\.345\/successful task/);
  doc.querySelector('[data-board="effort"]').click();
  const sort = doc.querySelector('#sort');
  sort.value = 'cost_per_task:asc';
  sort.dispatchEvent(new win.Event('change'));
  assert.deepEqual(cells(), ['$1.00', '$2.00']);
  win.close();
});

test('cached pre-heatmap markup works on browsers without findLastIndex', async () => {
  const data = fixture();
  data.boards.arena_text = structuredClone(baseBoard);
  for (const b of Object.values(data.boards)) b.observed_at = new Date().toISOString().slice(0, 10);
  const {doc, win} = await page(data, false, '', browser => {
    browser.document.querySelector('#heat-key').remove();
    browser.Array.prototype.findLastIndex = undefined;
  });
  assert.ok(doc.querySelector('.model-row'));
  assert.equal(doc.querySelectorAll('#heat-key').length, 1);
  assert.ok(doc.querySelector('.heat-4'));
  doc.querySelector('[data-board="effort"]').click();
  assert.ok(doc.querySelector('.heat-tile'));
  win.close();
});
