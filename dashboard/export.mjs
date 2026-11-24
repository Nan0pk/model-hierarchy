// Write the Atlas rankings to output/atlas.{json,csv} with the dashboard's own code, so the
// published files and the page can never disagree. Usage: node dashboard/export.mjs [output dir]
import {readFileSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {atlasHierarchy} from './hierarchy.js';

const sources = ['artificial_analysis', 'arena_text', 'livebench'];

export function atlasExport(data, now = new Date()) {
  const view = byEffort => {
    const h = atlasHierarchy(data.boards, data.freshness, byEffort, now, data.aliases || {});
    const rows = h.rows.filter(r => r.rank != null).sort((a, b) => a.rank - b.rank).map(r => ({
      rank: r.rank, model: r.model, atlas_score: r.score, evaluators: r.evidence.length,
      ...Object.fromEntries(sources.map(s => [`${s}_percentile`, r[s] == null ? null : Number(r[s].toFixed(1))])),
      cost_per_task: r.cost_per_task == null ? null : Number(r.cost_per_task.toFixed(4)),
    }));
    return {label: h.label, n_ranked: rows.length, field_offsets: h.offsets, rows};
  };
  return {generated_at: now.toISOString().slice(0, 10), source_snapshot: data.generated_at,
    qualification: atlasHierarchy(data.boards, data.freshness, false, now).qualification,
    models: view(false), effort_levels: view(true)};
}

export function atlasCSV(report) {
  const cell = v => v == null ? '' : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v);
  const lines = [];
  for (const [name, view] of [['models', report.models], ['effort_levels', report.effort_levels]]) {
    if (!lines.length) lines.push(['view', ...Object.keys(view.rows[0] ?? {rank: 0})].join(','));
    for (const row of view.rows) lines.push([name, ...Object.values(row)].map(cell).join(','));
  }
  return lines.join('\n') + '\n';
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const out = process.argv[2] || new URL('../output', import.meta.url).pathname;
  const report = atlasExport(JSON.parse(readFileSync(`${out}/leaderboards.json`, 'utf8')));
  writeFileSync(`${out}/atlas.json`, JSON.stringify(report, null, 2) + '\n');
  writeFileSync(`${out}/atlas.csv`, atlasCSV(report));
  console.log(`wrote ${out}/atlas.json and atlas.csv: ${report.models.n_ranked} models, ${report.effort_levels.n_ranked} effort levels`);
}
