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
  const retained = qualifiers.filter(q => !/^default fallback$/i.test(q));
  const model = retained.length ? `${match[1]} (${retained.join(', ')})` : match[1];
  return {model, effort};
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
    const {model, effort} = identity(row.model);
    if (byEffort && !effort) continue;
    // AA's "Default Fallback" is Anthropic's default API fallback to an older model, which it
    // measured in ~0.1% of tasks (x.com/ArtificialAnlys/status/2104640155843989864): same setting.
    const key = byEffort ? `${canonical(model, aliases)} (${effort.toLowerCase()})` : canonical(model, aliases);
    if (!groups.has(key)) groups.set(key, {key, label: byEffort ? row.model : model, effort, observations: []});
    groups.get(key).observations.push(row);
  }
  for (const group of groups.values()) group.score = median(group.observations.map(r => r.score));
  return [...groups.values()];
}

// Fit percentile ≈ ability + board offset (offsets sum to zero) by alternating least squares.
// A board whose shared field is stronger hands out lower percentiles for the same ability; the
// offset corrects that for models it did not score. Fully covered models keep their plain mean.
function fieldOffsets(rows, boards) {
  const offsets = Object.fromEntries(boards.map(b => [b, 0]));
  const used = boards.filter(b => rows.some(r => r[b] != null));
  for (let iteration = 0; iteration < 100; iteration++) {
    const ability = new Map(rows.map(r => {
      const present = used.filter(b => r[b] != null);
      return [r, present.reduce((t, b) => t + r[b] - offsets[b], 0) / present.length];
    }));
    for (const b of used) {
      const members = rows.filter(r => r[b] != null);
      offsets[b] = members.reduce((t, r) => t + r[b] - ability.get(r), 0) / members.length;
    }
    const mean = used.reduce((t, b) => t + offsets[b], 0) / (used.length || 1);
    for (const b of used) offsets[b] -= mean;
  }
  return offsets;
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
  // An evaluator with no entries in this view (e.g. LiveBench lists no explicit effort settings) gets no column.
  for (let i = columns.length - 1; i >= 0; i--) if (!rows.some(r => r[columns[i].key] != null)) columns.splice(i, 1);
  const eligible = rows.filter(row => row.evidence.length >= 2 && row.evidence.every(e => row[e.source] != null));
  const offsets = fieldOffsets(eligible, columns.filter(c => c.key !== 'cost_per_task').map(c => c.key));
  for (const row of eligible) {
    const sum = row.evidence.reduce((total, e) => total + row[e.source] - offsets[e.source], 0);
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
    description: byEffort ? 'Each explicitly labeled effort setting has its own entry; AA default-fallback runs join the same setting.'
      : 'Each model contributes one median tested score per evaluator, across its observed settings.',
    metric: 'Atlas score', decimals: 1, columns, rows, n_scored: ranked.length, availability, offsets,
    qualification: 'Atlas averages within-board percentiles from at least two current model evaluators. Each board ranks only the entries that appear on two or more evaluators, so padding a board with single-board entries cannot inflate them; single-evaluator entries are placed against that field. Shared fields differ in strength, so each board gets a fitted offset (a percentile on a stronger field is worth more); a model scored by every evaluator keeps its plain average. A dash in Atlas score means only one evaluator contributed. AA $/task is the reported cost per task, summarized by the median of priced settings for a model. A rounded $0.00 can represent a small cost. Expand a row for configuration prices and LiveBench cost per successful task.',
  };
}
