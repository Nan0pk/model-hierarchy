import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM} from 'jsdom';
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

async function page(data = fixture(), failing = false) {
  const html = await readFile(new URL('../dashboard/index.html', import.meta.url), 'utf8');
  const source = await readFile(new URL('../dashboard/app.js', import.meta.url), 'utf8');
  const dom = new JSDOM(html, {url:'https://atlas.test/dashboard/', runScripts:'outside-only'});
  const win = dom.window;
  Object.assign(win, helpers, {esc:helpers.escapeHTML});
  win.fetch = async url => {
    if (failing) return {ok:false,status:503};
    return {ok:true, json:async () => url.endsWith('leaderboards.json') ? structuredClone(data) : {
      quality:{status:'withheld',roster_size:8,blockers:['Math evidence is absent.']},cohort_size:3,
    }};
  };
  win.eval(source.replace(/^import .*?;\s*/s, ''));
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
  doc.querySelector('[data-board="terminal_bench"]').click();
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
