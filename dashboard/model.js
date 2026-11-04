// Pure data helpers, shared by the dashboard and regression tests.
export const PAGE_SIZE = 25;
export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function safeURL(value) {
  try { const url = new URL(value); return url.protocol === 'https:' ? url.href : null; }
  catch { return null; }
}
export function selectRows(board, {query = '', filter = '', sort = 'score:desc'} = {}) {
  const q = query.trim().toLocaleLowerCase();
  const [key, direction] = sort.split(':');
  return (board.rows || []).filter(row => {
    const haystack = [row.model, row.provider, row.harness].filter(Boolean).join(' ').toLocaleLowerCase();
    const matches = !filter || (filter === 'open' ? row.open_weights === true : [row.provider, row.harness].includes(filter));
    return matches && haystack.includes(q);
  }).sort((a, b) => {
    // A missing cost/suite/score is never treated as a free/zero result.
    if (a[key] == null || b[key] == null) return a[key] == null ? (b[key] == null ? a.model.localeCompare(b.model) : 1) : -1;
    const delta = typeof a[key] === 'number' ? a[key] - b[key] : String(a[key]).localeCompare(String(b[key]));
    return (direction === 'asc' ? delta : -delta) || a.model.localeCompare(b.model);
  });
}
export function formatValue(value, type = 'number', decimals = type === 'money' ? 2 : 1) {
  if (value == null) return '—';
  if (type === 'interval') return value.map(v => Number(v).toFixed(decimals)).join('–');
  if (type === 'text') return String(value);
  if (type === 'integer') return Number(value).toLocaleString('en-US');
  if (type === 'money') return '$' + Number(value).toFixed(decimals);
  return Number(value).toLocaleString('en-US', {maximumFractionDigits: decimals, minimumFractionDigits: decimals});
}
export function boardFreshness(board, policy, now = new Date()) {
  const stamp = board.published_at || board.observed_at;
  if (!stamp) return 'missing';
  const age = Math.floor((Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()) - Date.parse(stamp + 'T00:00:00Z')) / 86400000);
  if (!Number.isFinite(age) || age < 0) return 'invalid';
  if (age > policy.expire_after_days) return 'expired';
  if (age > policy.warn_after_days) return 'stale';
  return board.status === 'missing' ? 'missing' : 'available';
}
export function otherMatches(boards, selected, query) {
  if (!query.trim()) return [];
  return Object.entries(boards).filter(([id]) => id !== selected).map(([id, board]) => ({id, label: board.label, count: selectRows(board, {query}).length})).filter(item => item.count > 0);
}
