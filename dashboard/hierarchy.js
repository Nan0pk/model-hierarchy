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

function median(values) {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
}

function standings(board, byEffort) {
  const groups = new Map();
  for (const row of board.rows) {
    if (!Number.isFinite(row.score)) continue;
    const {model, effort} = identity(row.model);
    const label = byEffort ? row.model : model;
    const key = byEffort && effort
      ? label.toLowerCase().replace(/\s+xhigh$/, ' (xhigh)')
      : label.toLowerCase();
    if (!groups.has(key)) groups.set(key, {key, label, effort, observations: []});
    groups.get(key).observations.push({model: row.model, score: row.score});
  }
  const sorted = [...groups.values()];
  for (const group of sorted) group.score = median(group.observations.map(r => r.score));
  sorted.sort((a, b) => a.score - b.score);
  if (sorted.length < 2) return [];
  for (let i = 0; i < sorted.length;) {
    let end = i + 1;
    while (end < sorted.length && sorted[end].score === sorted[i].score) end++;
    const percentile = 100 * (i + end - 1) / (2 * (sorted.length - 1));
    for (let j = i; j < end; j++) sorted[j].percentile = percentile;
    i = end;
  }
  return byEffort ? sorted.filter(group => group.effort) : sorted;
}

export function atlasHierarchy(boards, freshness, byEffort, now = new Date()) {
  const combined = new Map();
  const columns = [];
  const availability = [];
  for (const id of sources) {
    const board = boards[id];
    if (!board) continue;
    const status = boardFreshness(board, freshness, now);
    availability.push({label: board.label, status, failed: board.last_fetch?.status === 'failed'});
    if (status !== 'available') continue;
    columns.push({key: id, label: board.label, type: 'number', decimals: 1});
    for (const item of standings(board, byEffort)) {
      if (!combined.has(item.key)) combined.set(item.key, {
        id: item.key, model: item.label, evidence: [], score: null, rank: null,
      });
      const row = combined.get(item.key);
      row[id] = item.percentile;
      row.evidence.push({source: id, observations: item.observations});
    }
  }
  const rows = [...combined.values()];
  for (const row of rows) {
    if (row.evidence.length < 2) continue;
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
    qualification: 'Atlas averages within-board percentiles from at least two current model evaluators. Source columns show percentiles. A dash in Atlas score means only one evaluator contributed. Expand a row for the original measurements.',
  };
}
