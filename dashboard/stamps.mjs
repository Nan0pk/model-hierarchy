// Rewrite the cache-busting ?v= stamps in dashboard/index.html from the SHA-256
// of the shipped CSS/JS, so returning visitors always get the new code.
// Run `make stamps` after editing app.js or styles.css. The daily workflow runs
// this too, so a forgotten stamp heals itself on the next scheduled build —
// tests/dashboard.test.mjs remains the offline verifier.
import {createHash} from 'node:crypto';
import {readFileSync, writeFileSync} from 'node:fs';

const dir = new URL('./', import.meta.url);
let html = readFileSync(new URL('index.html', dir), 'utf8');
let changed = false;
for (const file of ['styles.css', 'app.js']) {
  const stamp = createHash('sha256').update(readFileSync(new URL(file, dir))).digest('hex').slice(0, 10);
  const pattern = new RegExp(`(${file.replace('.', '\\.')}\\?v=)[0-9a-f]{10}`);
  if (!pattern.test(html)) throw new Error(`dashboard/index.html has no ?v= stamp for ${file}`);
  const updated = html.replace(pattern, `$1${stamp}`);
  if (updated !== html) {
    console.log(`stamped ${file} -> ${stamp}`);
    changed = true;
  }
  html = updated;
}
if (changed) writeFileSync(new URL('index.html', dir), html);
else console.log('stamps already up to date');
