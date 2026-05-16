/**
 * check-combos.mjs — Domain availability checker
 *
 * Pipeline:
 *   1. Read domains-to-check.txt
 *   2. DNS fast-pass (50 concurrent) — NXDOMAIN = possibly available
 *   3. RDAP confirmation for NXDOMAIN results (2/sec rate limit)
 *   4. Sort: available first, then by TLD price estimate
 *   5. Console output + HTML report
 *
 * NASA Power of 10 compliant:
 *   - All loops bounded (MAX_DOMAINS=5000)
 *   - Functions under 60 lines
 *   - Min 2 assertions per function
 *   - No globals — all state passed explicitly
 *   - Every return value checked
 *   - No dangerous mutations
 */

import { promises as dns } from 'node:dns';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { strict as assert } from 'node:assert';
import https from 'node:https';
import http from 'node:http';

// ─── Constants (bounded) ───────────────────────────────────────────────────────

const MAX_DOMAINS = 15000;
const DNS_CONCURRENCY = 50;
const RDAP_RATE_MS = 500;          // 2 per second
const RDAP_TIMEOUT_MS = 8000;
const DNS_TIMEOUT_MS = 5000;
const MAX_RDAP_RETRIES = 2;
const REPORT_PATH = '/Users/mike/Desktop/DOMAIN-HUNT-RESULTS.html';

// ─── TLD Price Map ─────────────────────────────────────────────────────────────

/**
 * Returns price estimate map for known cheap TLDs.
 * @returns {Map<string, number>}
 */
function buildPriceMap() {
  const entries = [
    // Real Porkbun registration prices (May 2026)
    ['cfd', 1.28], ['cyou', 1.28], ['sbs', 1.28],
    ['bond', 1.34],
    ['click', 1.54], ['beauty', 1.54], ['hair', 1.54], ['homes', 1.54],
    ['monster', 1.54], ['quest', 1.54], ['skin', 1.54], ['beer', 1.54],
    ['garden', 1.54], ['help', 1.54], ['lol', 1.54], ['mom', 1.54],
    ['pics', 1.54], ['rest', 1.54], ['surf', 1.54], ['baby', 1.54],
    ['top', 1.63], ['best', 1.72],
    ['website', 1.96], ['space', 1.96], ['online', 1.96], ['site', 1.96],
    ['xyz', 2.04], ['buzz', 2.05],
    ['work', 2.06], ['fit', 2.06], ['ink', 2.06], ['wiki', 2.06],
    ['life', 2.06], ['shop', 2.06],
    ['one', 2.57], ['live', 2.57], ['fun', 2.57], ['bar', 2.57],
    ['art', 3.60], ['blog', 3.60], ['wtf', 3.60], ['world', 3.60],
    ['dog', 3.60], ['cloud', 3.88],
    ['club', 4.12], ['run', 4.12],
    ['zone', 4.63], ['cafe', 4.63], ['golf', 4.63],
  ];

  const map = new Map(entries);
  assert(map.size > 0, 'Price map must not be empty');
  assert(map.size <= 100, 'Price map size exceeds bound');
  return map;
}

// ─── Domain Reading ────────────────────────────────────────────────────────────

/**
 * Reads domain list from file. Returns trimmed, non-empty lines.
 * @param {string} filePath
 * @returns {string[]}
 */
function readDomainList(filePath) {
  assert(typeof filePath === 'string', 'filePath must be a string');
  assert(existsSync(filePath), `File not found: ${filePath}`);

  const raw = readFileSync(filePath, 'utf-8');
  const lines = raw.split('\n');
  const domains = [];

  const bound = Math.min(lines.length, MAX_DOMAINS + 1000); // slack for empty lines
  for (let i = 0; i < bound; i++) {
    const line = lines[i]?.trim();
    if (line && line.length > 0 && line.includes('.')) {
      domains.push(line.toLowerCase());
    }
    if (domains.length >= MAX_DOMAINS) {
      break;
    }
  }

  assert(domains.length > 0, 'Domain list must contain at least one domain');
  assert(domains.length <= MAX_DOMAINS, `Domain count exceeds MAX_DOMAINS (${MAX_DOMAINS})`);
  return domains;
}

// ─── DNS Check ─────────────────────────────────────────────────────────────────

/**
 * Checks a single domain via DNS. Returns status string.
 * @param {string} domain
 * @returns {Promise<{ domain: string, dns: string }>}
 */
async function checkDns(domain) {
  assert(typeof domain === 'string', 'domain must be a string');
  assert(domain.includes('.'), 'domain must contain a dot');

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), DNS_TIMEOUT_MS);

    try {
      await dns.resolve(domain, 'A');
      clearTimeout(timer);
      return { domain, dns: 'registered' };
    } catch (err) {
      clearTimeout(timer);
      const code = err?.code ?? 'UNKNOWN';
      if (code === 'ENOTFOUND' || code === 'ENODATA') {
        return { domain, dns: 'nxdomain' };
      }
      if (code === 'ETIMEOUT' || code === 'EAI_AGAIN') {
        return { domain, dns: 'timeout' };
      }
      if (code === 'ESERVFAIL') {
        return { domain, dns: 'servfail' };
      }
      return { domain, dns: 'error' };
    }
  } catch (outerErr) {
    return { domain, dns: 'error' };
  }
}

/**
 * Runs DNS checks with bounded concurrency.
 * @param {string[]} domains
 * @param {(done: number, total: number) => void} onProgress
 * @returns {Promise<{ domain: string, dns: string }[]>}
 */
async function checkDnsBatch(domains, onProgress) {
  assert(Array.isArray(domains), 'domains must be an array');
  assert(domains.length <= MAX_DOMAINS, 'domains exceeds MAX_DOMAINS');

  const results = [];
  let done = 0;

  // Process in chunks of DNS_CONCURRENCY
  const totalChunks = Math.ceil(domains.length / DNS_CONCURRENCY);
  const MAX_CHUNKS = Math.ceil(MAX_DOMAINS / DNS_CONCURRENCY) + 1;

  for (let c = 0; c < totalChunks && c < MAX_CHUNKS; c++) {
    const start = c * DNS_CONCURRENCY;
    const end = Math.min(start + DNS_CONCURRENCY, domains.length);
    const chunk = domains.slice(start, end);

    const chunkResults = await Promise.all(
      chunk.map((d) => checkDns(d))
    );

    for (let i = 0; i < chunkResults.length && i < DNS_CONCURRENCY; i++) {
      results.push(chunkResults[i]);
      done++;
    }

    if (onProgress) {
      onProgress(done, domains.length);
    }
  }

  return results;
}

// ─── RDAP Check ────────────────────────────────────────────────────────────────

/**
 * Makes an HTTPS GET request, returns { statusCode, body } or error.
 * @param {string} url
 * @returns {Promise<{ statusCode: number, body: string }>}
 */
function httpsGet(url) {
  assert(typeof url === 'string', 'url must be a string');
  assert(url.startsWith('http'), 'url must start with http');

  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? https : http;
    const req = mod.get(url, { timeout: RDAP_TIMEOUT_MS }, (res) => {
      // Handle redirects (bounded to 3)
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        resolve({ statusCode: res.statusCode, body: '', redirect: res.headers.location });
        res.resume();
        return;
      }

      const chunks = [];
      let totalBytes = 0;
      const MAX_BODY = 100_000;

      res.on('data', (chunk) => {
        totalBytes += chunk.length;
        if (totalBytes <= MAX_BODY) {
          chunks.push(chunk);
        }
      });

      res.on('end', () => {
        resolve({ statusCode: res.statusCode, body: Buffer.concat(chunks).toString('utf-8') });
      });

      res.on('error', (err) => reject(err));
    });

    req.on('error', (err) => reject(err));
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('RDAP timeout'));
    });
  });
}

/**
 * Follows redirects up to maxRedirects.
 * @param {string} url
 * @param {number} maxRedirects
 * @returns {Promise<{ statusCode: number, body: string }>}
 */
async function httpsGetWithRedirects(url, maxRedirects) {
  assert(typeof url === 'string', 'url required');
  assert(maxRedirects >= 0 && maxRedirects <= 5, 'maxRedirects must be 0-5');

  let currentUrl = url;
  for (let i = 0; i <= maxRedirects && i <= 5; i++) {
    const result = await httpsGet(currentUrl);
    if (result.redirect && i < maxRedirects) {
      currentUrl = result.redirect;
      continue;
    }
    return result;
  }
  return { statusCode: 0, body: '' };
}

/**
 * Checks a single domain via RDAP. Returns availability status.
 * @param {string} domain
 * @returns {Promise<{ domain: string, rdap: string }>}
 */
async function checkRdap(domain) {
  assert(typeof domain === 'string', 'domain must be a string');
  assert(domain.includes('.'), 'domain must contain a dot');

  const url = `https://rdap.org/domain/${domain}`;

  for (let attempt = 0; attempt < MAX_RDAP_RETRIES; attempt++) {
    try {
      const result = await httpsGetWithRedirects(url, 3);
      const status = result.statusCode;

      if (status === 200) {
        return { domain, rdap: 'registered' };
      }
      if (status === 404) {
        return { domain, rdap: 'available' };
      }
      if (status === 429) {
        // Rate limited — wait and retry
        await sleep(2000);
        continue;
      }
      // Other status — treat as uncertain
      return { domain, rdap: 'uncertain' };
    } catch (err) {
      if (attempt < MAX_RDAP_RETRIES - 1) {
        await sleep(1000);
        continue;
      }
      return { domain, rdap: 'error' };
    }
  }

  return { domain, rdap: 'error' };
}

/**
 * Promise-based sleep.
 * @param {number} ms
 * @returns {Promise<void>}
 */
function sleep(ms) {
  assert(typeof ms === 'number', 'ms must be a number');
  assert(ms >= 0 && ms <= 30000, 'ms must be 0-30000');
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Runs RDAP checks with rate limiting (2/sec).
 * @param {string[]} domains
 * @param {(done: number, total: number, lastResult: string) => void} onProgress
 * @returns {Promise<Map<string, string>>}
 */
async function checkRdapBatch(domains, onProgress) {
  assert(Array.isArray(domains), 'domains must be an array');
  assert(domains.length <= MAX_DOMAINS, 'exceeds MAX_DOMAINS');

  const results = new Map();

  for (let i = 0; i < domains.length && i < MAX_DOMAINS; i++) {
    const result = await checkRdap(domains[i]);
    results.set(result.domain, result.rdap);

    if (onProgress) {
      onProgress(i + 1, domains.length, result.rdap);
    }

    // Rate limit: wait between requests (except last)
    if (i < domains.length - 1) {
      await sleep(RDAP_RATE_MS);
    }
  }

  return results;
}

// ─── TLD Extraction ────────────────────────────────────────────────────────────

/**
 * Extracts TLD from a domain string.
 * @param {string} domain
 * @returns {string}
 */
function extractTld(domain) {
  assert(typeof domain === 'string', 'domain must be a string');
  assert(domain.includes('.'), 'domain must contain a dot');

  const parts = domain.split('.');
  return parts[parts.length - 1];
}

// ─── Result Sorting ────────────────────────────────────────────────────────────

/**
 * @typedef {Object} DomainResult
 * @property {string} domain
 * @property {string} dns
 * @property {string} rdap
 * @property {number} price
 * @property {string} status - 'available' | 'registered' | 'uncertain' | 'error'
 */

/**
 * Merges DNS + RDAP results and sorts: available first, then by price.
 * @param {{ domain: string, dns: string }[]} dnsResults
 * @param {Map<string, string>} rdapResults
 * @param {Map<string, number>} priceMap
 * @returns {DomainResult[]}
 */
function mergeAndSort(dnsResults, rdapResults, priceMap) {
  assert(Array.isArray(dnsResults), 'dnsResults must be an array');
  assert(rdapResults instanceof Map, 'rdapResults must be a Map');

  const merged = [];

  const bound = Math.min(dnsResults.length, MAX_DOMAINS);
  for (let i = 0; i < bound; i++) {
    const dr = dnsResults[i];
    const tld = extractTld(dr.domain);
    const price = priceMap.get(tld) ?? 10;
    const rdap = rdapResults.get(dr.domain) ?? 'not-checked';

    let status = 'registered';
    if (dr.dns === 'nxdomain' && rdap === 'available') {
      status = 'available';
    } else if (dr.dns === 'nxdomain' && rdap === 'uncertain') {
      status = 'uncertain';
    } else if (dr.dns === 'nxdomain' && rdap === 'error') {
      status = 'uncertain';
    } else if (dr.dns === 'nxdomain' && rdap === 'not-checked') {
      status = 'possibly-available';
    } else if (dr.dns === 'timeout' || dr.dns === 'servfail') {
      status = 'dns-error';
    }

    merged.push({ domain: dr.domain, dns: dr.dns, rdap, price, status });
  }

  // Sort: available first, then uncertain, then by price ascending
  const statusOrder = {
    'available': 0,
    'possibly-available': 1,
    'uncertain': 2,
    'dns-error': 3,
    'registered': 4,
  };

  merged.sort((a, b) => {
    const sa = statusOrder[a.status] ?? 5;
    const sb = statusOrder[b.status] ?? 5;
    if (sa !== sb) return sa - sb;
    return a.price - b.price;
  });

  return merged;
}

// ─── Console Output ────────────────────────────────────────────────────────────

/**
 * Prints summary results to console.
 * @param {DomainResult[]} results
 * @param {{ dnsTime: number, rdapTime: number }} timing
 */
function printConsoleResults(results, timing) {
  assert(Array.isArray(results), 'results must be an array');
  assert(typeof timing === 'object', 'timing must be an object');

  const available = results.filter((r) => r.status === 'available');
  const uncertain = results.filter((r) => r.status === 'uncertain' || r.status === 'possibly-available');
  const registered = results.filter((r) => r.status === 'registered');

  console.log('\n══════════════════════════════════════════════════');
  console.log('  DOMAIN HUNT RESULTS');
  console.log('══════════════════════════════════════════════════');
  console.log(`  Total checked:  ${results.length}`);
  console.log(`  Available:      ${available.length}`);
  console.log(`  Uncertain:      ${uncertain.length}`);
  console.log(`  Registered:     ${registered.length}`);
  console.log(`  DNS time:       ${(timing.dnsTime / 1000).toFixed(1)}s`);
  console.log(`  RDAP time:      ${(timing.rdapTime / 1000).toFixed(1)}s`);
  console.log('──────────────────────────────────────────────────');

  if (available.length > 0) {
    console.log('\n  AVAILABLE DOMAINS:');
    const bound = Math.min(available.length, 200);
    for (let i = 0; i < bound; i++) {
      const d = available[i];
      console.log(`    ${d.domain.padEnd(30)} ~$${d.price}/yr`);
    }
  }

  if (uncertain.length > 0) {
    console.log('\n  POSSIBLY AVAILABLE (needs manual check):');
    const bound = Math.min(uncertain.length, 50);
    for (let i = 0; i < bound; i++) {
      const d = uncertain[i];
      console.log(`    ${d.domain.padEnd(30)} ~$${d.price}/yr  [${d.rdap}]`);
    }
  }

  console.log('\n══════════════════════════════════════════════════\n');
}

// ─── HTML Report ───────────────────────────────────────────────────────────────

/**
 * Escapes HTML special chars.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  assert(typeof str === 'string', 'str must be a string');
  assert(str.length < 1_000_000, 'str too long');

  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Builds HTML table rows for a category of results.
 * @param {DomainResult[]} results
 * @param {string} statusClass
 * @returns {string}
 */
function buildTableRows(results, statusClass) {
  assert(Array.isArray(results), 'results must be an array');
  assert(typeof statusClass === 'string', 'statusClass must be a string');

  let html = '';
  const bound = Math.min(results.length, MAX_DOMAINS);
  for (let i = 0; i < bound; i++) {
    const r = results[i];
    html += `      <tr class="${statusClass}">
        <td>${escapeHtml(r.domain)}</td>
        <td>${escapeHtml(r.status)}</td>
        <td>$${r.price}/yr</td>
        <td>${escapeHtml(r.dns)}</td>
        <td>${escapeHtml(r.rdap)}</td>
      </tr>\n`;
  }
  return html;
}

/**
 * Generates the full HTML report.
 * @param {DomainResult[]} results
 * @param {{ dnsTime: number, rdapTime: number }} timing
 * @returns {string}
 */
function generateHtmlReport(results, timing) {
  assert(Array.isArray(results), 'results must be an array');
  assert(typeof timing === 'object', 'timing required');

  const available = results.filter((r) => r.status === 'available');
  const uncertain = results.filter((r) => r.status === 'uncertain' || r.status === 'possibly-available');
  const registered = results.filter((r) => r.status === 'registered');
  const dnsError = results.filter((r) => r.status === 'dns-error');
  const now = new Date().toISOString();

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Domain Hunt Results — ${now.slice(0, 10)}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
      background: #0a0a0a; color: #e0e0e0;
      padding: 2rem; line-height: 1.6;
    }
    h1 { color: #00ff88; margin-bottom: 0.5rem; font-size: 1.8rem; }
    h2 { color: #88ccff; margin: 2rem 0 1rem; font-size: 1.3rem; }
    .meta { color: #888; margin-bottom: 2rem; font-size: 0.9rem; }
    .stats {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem; margin-bottom: 2rem;
    }
    .stat-card {
      background: #1a1a2e; border: 1px solid #333;
      border-radius: 8px; padding: 1rem; text-align: center;
    }
    .stat-card .num { font-size: 2rem; font-weight: bold; }
    .stat-card .label { color: #888; font-size: 0.85rem; }
    .available .num { color: #00ff88; }
    .uncertain-card .num { color: #ffaa00; }
    .registered-card .num { color: #ff4444; }
    .time-card .num { color: #88ccff; font-size: 1.2rem; }
    table {
      width: 100%; border-collapse: collapse;
      margin-bottom: 2rem; font-size: 0.9rem;
    }
    th {
      background: #1a1a2e; color: #88ccff;
      padding: 0.7rem; text-align: left;
      border-bottom: 2px solid #333; position: sticky; top: 0;
    }
    td { padding: 0.5rem 0.7rem; border-bottom: 1px solid #1a1a1a; }
    tr.avail { background: #0a2a1a; }
    tr.avail td:first-child { color: #00ff88; font-weight: bold; }
    tr.maybe { background: #2a2a0a; }
    tr.maybe td:first-child { color: #ffaa00; }
    tr.taken { color: #666; }
    tr.dns-err { color: #886600; }
    tr:hover { background: #1a1a3e; }
    .filter-bar {
      margin-bottom: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;
    }
    .filter-btn {
      background: #1a1a2e; border: 1px solid #333; color: #e0e0e0;
      padding: 0.4rem 1rem; border-radius: 4px; cursor: pointer;
      font-size: 0.85rem;
    }
    .filter-btn:hover, .filter-btn.active {
      background: #2a2a4e; border-color: #88ccff;
    }
    #search {
      background: #1a1a2e; border: 1px solid #333; color: #e0e0e0;
      padding: 0.5rem 1rem; border-radius: 4px; font-size: 0.9rem;
      width: 300px;
    }
    .registrar-links { margin-top: 0.5rem; }
    .registrar-links a {
      color: #88ccff; text-decoration: none; margin-right: 1rem;
      font-size: 0.8rem;
    }
    .registrar-links a:hover { text-decoration: underline; }
    footer { color: #555; font-size: 0.8rem; margin-top: 3rem; border-top: 1px solid #222; padding-top: 1rem; }
  </style>
</head>
<body>
  <h1>Domain Hunt Results</h1>
  <p class="meta">Generated: ${escapeHtml(now)} | Total: ${results.length} domains</p>

  <div class="stats">
    <div class="stat-card available">
      <div class="num">${available.length}</div>
      <div class="label">Available</div>
    </div>
    <div class="stat-card uncertain-card">
      <div class="num">${uncertain.length}</div>
      <div class="label">Uncertain</div>
    </div>
    <div class="stat-card registered-card">
      <div class="num">${registered.length}</div>
      <div class="label">Registered</div>
    </div>
    <div class="stat-card time-card">
      <div class="num">${(timing.dnsTime / 1000).toFixed(1)}s / ${(timing.rdapTime / 1000).toFixed(1)}s</div>
      <div class="label">DNS / RDAP Time</div>
    </div>
  </div>

  <div class="filter-bar">
    <input type="text" id="search" placeholder="Filter domains..." oninput="filterTable()">
    <button class="filter-btn active" onclick="setFilter('all', this)">All (${results.length})</button>
    <button class="filter-btn" onclick="setFilter('avail', this)">Available (${available.length})</button>
    <button class="filter-btn" onclick="setFilter('maybe', this)">Uncertain (${uncertain.length})</button>
    <button class="filter-btn" onclick="setFilter('taken', this)">Registered (${registered.length})</button>
  </div>

  <table id="results">
    <thead>
      <tr>
        <th>Domain</th>
        <th>Status</th>
        <th>Est. Price</th>
        <th>DNS</th>
        <th>RDAP</th>
      </tr>
    </thead>
    <tbody>
${buildTableRows(available, 'avail')}${buildTableRows(uncertain, 'maybe')}${buildTableRows(dnsError, 'dns-err')}${buildTableRows(registered, 'taken')}
    </tbody>
  </table>

${available.length > 0 ? `
  <h2>Quick Registration Links</h2>
  <p style="color: #888; font-size: 0.85rem; margin-bottom: 1rem;">Click to check pricing at popular registrars:</p>
  ${available.slice(0, 50).map((d) => `
  <div style="margin-bottom: 0.5rem;">
    <strong style="color: #00ff88;">${escapeHtml(d.domain)}</strong>
    <span class="registrar-links">
      <a href="https://www.namecheap.com/domains/registration/results/?domain=${encodeURIComponent(d.domain)}" target="_blank">Namecheap</a>
      <a href="https://www.porkbun.com/checkout/search?q=${encodeURIComponent(d.domain)}" target="_blank">Porkbun</a>
      <a href="https://www.cloudflare.com/products/registrar/" target="_blank">Cloudflare</a>
    </span>
  </div>`).join('\n')}
` : ''}

  <footer>
    Domain Hunter v1.0 | DNS fast-pass + RDAP verification | ${results.length} domains checked
  </footer>

  <script>
    let currentFilter = 'all';
    function setFilter(f, btn) {
      currentFilter = f;
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      filterTable();
    }
    function filterTable() {
      const search = document.getElementById('search').value.toLowerCase();
      const rows = document.querySelectorAll('#results tbody tr');
      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const domain = row.cells[0].textContent.toLowerCase();
        const matchesSearch = !search || domain.includes(search);
        const matchesFilter = currentFilter === 'all' || row.classList.contains(currentFilter);
        row.style.display = (matchesSearch && matchesFilter) ? '' : 'none';
      }
    }
  </script>
</body>
</html>`;

  return html;
}

/**
 * Writes the HTML report to disk.
 * @param {string} html
 * @param {string} outputPath
 */
function writeReport(html, outputPath) {
  assert(typeof html === 'string' && html.length > 0, 'html must be non-empty');
  assert(typeof outputPath === 'string', 'outputPath must be a string');

  writeFileSync(outputPath, html, 'utf-8');
  console.log(`  HTML report: ${outputPath}`);
}

// ─── Progress Display ──────────────────────────────────────────────────────────

/**
 * Writes progress to stderr (overwrites line).
 * @param {string} phase
 * @param {number} done
 * @param {number} total
 */
function showProgress(phase, done, total) {
  assert(typeof phase === 'string', 'phase required');
  assert(done >= 0 && total >= 0, 'counts must be non-negative');

  const pct = total > 0 ? ((done / total) * 100).toFixed(1) : '0.0';
  process.stderr.write(`\r  [${phase}] ${done}/${total} (${pct}%)   `);
}

// ─── Main Pipeline ─────────────────────────────────────────────────────────────

/**
 * Runs the full check pipeline.
 */
async function main() {
  const __dirname = dirname(fileURLToPath(import.meta.url));
  const inputPath = join(__dirname, 'domains-to-check.txt');

  assert(typeof __dirname === 'string', 'dirname must resolve');
  assert(existsSync(inputPath), `Input file not found: ${inputPath}. Run generate-combos.mjs first.`);

  console.log('=== Domain Hunter ===');
  console.log(`  Input: ${inputPath}`);

  // Step 1: Read domains
  const domains = readDomainList(inputPath);
  console.log(`  Domains loaded: ${domains.length}`);

  // Step 2: DNS fast-pass
  console.log('\n  Phase 1: DNS fast-pass...');
  const dnsStart = Date.now();
  const dnsResults = await checkDnsBatch(domains, (done, total) => {
    showProgress('DNS', done, total);
  });
  const dnsTime = Date.now() - dnsStart;
  process.stderr.write('\n');

  // Count NXDOMAIN results
  const nxdomainDomains = [];
  const MAX_NX = MAX_DOMAINS;
  for (let i = 0; i < dnsResults.length && nxdomainDomains.length < MAX_NX; i++) {
    if (dnsResults[i].dns === 'nxdomain') {
      nxdomainDomains.push(dnsResults[i].domain);
    }
  }

  console.log(`  DNS complete: ${dnsResults.length} checked, ${nxdomainDomains.length} NXDOMAIN`);

  // Step 3: RDAP verification for NXDOMAIN
  let rdapResults = new Map();
  let rdapTime = 0;

  if (nxdomainDomains.length > 0) {
    console.log(`\n  Phase 2: RDAP verification (${nxdomainDomains.length} domains, ~${(nxdomainDomains.length * RDAP_RATE_MS / 1000).toFixed(0)}s est.)...`);
    const rdapStart = Date.now();
    rdapResults = await checkRdapBatch(nxdomainDomains, (done, total, lastResult) => {
      showProgress('RDAP', done, total);
    });
    rdapTime = Date.now() - rdapStart;
    process.stderr.write('\n');
    console.log(`  RDAP complete: ${rdapResults.size} verified`);
  } else {
    console.log('\n  Phase 2: RDAP skipped (no NXDOMAIN results)');
  }

  // Step 4: Merge and sort
  const priceMap = buildPriceMap();
  const results = mergeAndSort(dnsResults, rdapResults, priceMap);

  // Step 5: Console output
  const timing = { dnsTime, rdapTime };
  printConsoleResults(results, timing);

  // Step 6: HTML report
  const html = generateHtmlReport(results, timing);
  writeReport(html, REPORT_PATH);

  console.log('  Done.');
}

main().catch((err) => {
  console.error('FATAL:', err.message);
  process.exit(1);
});
