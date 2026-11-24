// Compute from the same verified snapshots the reader can inspect in the native tabs.
import {boardFreshness} from './model.js';

const sources = ['artificial_analysis', 'arena_text', 'livebench'];
const effortPattern = /^(none|minimal|low|medium|high|xhigh|max|reasoning|non-reasoning|thinking|non-thinking)$/i;

function identity(label) {
  const match = /^(.*?)\s+\(([^()]+)\)$/.exec(label);
  if (!match) {
    // LiveBench also spells the explicit setting as a trailing "xHigh".
    const trailing = /^(.*?)\s+(xhigh)$/i.exec(label);
    return trailing ? {model: trailing[1], effort: trailing[2]} : {model: label};
  }
  const [effort, ...qualifiers] = match[2].split(',').map(part => part.trim());
  if (!effortPattern.test(effort)) return {model: label};
  // Keep dates, precision and other unknown qualifiers in the model identity.
  const fallback = qualifiers.some(q => /^default fallback$/i.test(q));
  const retained = qualifiers.filter(q => !/^default fallback$/i.test(q));
  const model = retained.length ? `${match[1]} (${retained.join(', ')})` : match[1];
  return {model, effort, fallback};
}

// Same rule as hierarchy/names.py canonical(): unify separators, then the reviewed alias table.
function canonical(name, aliases) {
  const key = name.toLowerCase().replace(/[\s\-_]+/g, ' ').trim();
  return aliases[key] ?? key;
}

// 100 × (scores strictly below + half the tied others) / others; the same rule for every row.
function percentileOf(value, others) {
  if (!others.length) return null;
  const below = others.filter(v => v < value).length;
  const tied = others.filter(v => v === value).length;
  return 100 * (below + tied / 2) / others.length;
}

function median(values) {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
}

function standings(board, byEffort, aliases) {
  const groups = new Map();
  for (const row of board.rows) {
    if (!Number.isFinite(row.score)) continue;
    const {model, effort, fallback} = identity(row.model);
    if (byEffort && !effort) continue;
    const key = byEffort
      ? `${canonical(model, aliases)} (${effort.toLowerCase()}${fallback ? ', default fallback' : ''})`
      : canonical(model, aliases);
    if (!groups.has(key)) groups.set(key, {key, label: byEffort ? row.model : model, effort, observations: []});
    groups.get(key).observations.push(row);
  }
  for (const group of groups.values()) group.score = median(group.observations.map(r => r.score));
  return [...groups.values()];
}

export function atlasHierarchy(boards, freshness, byEffort, now = new Date(), aliases = {}) {
  const combined = new Map();
  const columns = [];
  const availability = [];
  const perBoard = [];
  for (const id of sources) {
    const board = boards[id];
    if (!board) continue;
    const status = boardFreshness(board, freshness, now);
    availability.push({label: board.label, status, failed: board.last_fetch?.status === 'failed'});
    if (status !== 'available') continue;
    columns.push({key: id, label: board.label, type: 'number', decimals: 1});
    if (id === 'artificial_analysis') {
      columns.unshift({key: 'cost_per_task', label: 'AA $/task', type: 'money', decimals: 2,
        subtitle: byEffort ? 'tested setting' : 'median reported'});
    }
    const items = standings(board, byEffort, aliases);
    perBoard.push([id, items]);
    for (const item of items) {
      if (!combined.has(item.key)) combined.set(item.key, {
        id: item.key, model: item.label, evidence: [], score: null, rank: null,
      });
      const row = combined.get(item.key);
      if (id === 'artificial_analysis') {
        const costs = item.observations.map(r => r.cost_per_task).filter(Number.isFinite);
        row.cost_per_task = costs.length ? median(costs) : null;
      }
      row.evidence.push({source: id, observations: item.observations});
    }
  }
  // Percentiles only among entries on 2+ evaluators, so every board grades the same contenders:
  // a board padded with older single-board models cannot inflate the shared models' standing.
  const shared = new Set([...combined.values()].filter(r => r.evidence.length >= 2).map(r => r.id));
  for (const [id, items] of perBoard) {
    const sharedItems = items.filter(item => shared.has(item.key));
    for (const item of items) {
      const others = sharedItems.filter(other => other !== item).map(other => other.score);
      combined.get(item.key)[id] = percentileOf(item.score, others);
    }
  }
  const rows = [...combined.values()];
  for (const row of rows) {
    if (row.evidence.length < 2 || row.evidence.some(e => row[e.source] == null)) continue;
    const sum = row.evidence.reduce((total, e) => total + row[e.source], 0);
    row.score = Number((sum / row.evidence.length).toFixed(1));
  }
  const ranked = rows.filter(r => r.score !== null).sort((a, b) => b.score - a.score);
  for (const [i, row] of ranked.entries()) {
    row.rank = i > 0 && row.score === ranked[i - 1].score ? ranked[i - 1].rank : i + 1;
  }
  return {
    derived: true, label: byEffort ? 'Effort levels' : 'Atlas models',
    version: byEffort ? 'Reasoning effort hierarchy' : 'Model hierarchy',
    subtitle: byEffort ? 'Exact tested settings' : 'Across evaluators',
    description: byEffort ? 'Each explicitly labeled effort and fallback configuration has its own entry.'
      : 'Each model contributes one median tested score per evaluator, across its observed settings.',
    metric: 'Atlas score', decimals: 1, columns, rows, n_scored: ranked.length, availability,
    qualification: 'Atlas averages within-board percentiles from at least two current model evaluators. Each board ranks only the entries that appear on two or more evaluators, so padding a board with single-board entries cannot inflate them; single-evaluator entries are placed against that field. A dash in Atlas score means only one evaluator contributed. AA $/task is the reported cost per task, summarized by the median of priced settings for a model. A rounded $0.00 can represent a small cost. Expand a row for configuration prices and LiveBench cost per successful task.',
  };
}
