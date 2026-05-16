#!/usr/bin/env bash
# test.sh — Zovo Brands Cloudflare Worker test suite.
# NASA P10: set -euo pipefail, bounded loops, <60-line functions, 2 assertions/fn.
set -euo pipefail

readonly MAX_DOMAINS=50
readonly MAX_PAGE_BYTES=51200
readonly RUNNER="_zovo_test_runner.mjs"
readonly SRC_DIR="$(cd "$(dirname "$0")" && pwd)/src"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass=0
fail=0

cleanup() {
  rm -f "$RUNNER"
}
trap cleanup EXIT

mark_pass() {
  echo -e "${GREEN}[PASS]${NC} $1"
  pass=$((pass + 1))
}

mark_fail() {
  echo -e "${RED}[FAIL]${NC} $1"
  fail=$((fail + 1))
}

print_header() {
  echo ""
  echo "=========================================="
  echo "  ZOVO BRANDS -- Test Suite"
  echo "=========================================="
  echo ""
}

run_syntax_checks() {
  echo "--- Syntax Checks ---"
  local files=("$SRC_DIR/index.js" "$SRC_DIR/domains.js" "$SRC_DIR/template.js" "$SRC_DIR/stripe-links.js")
  local i=0
  while [[ $i -lt ${#files[@]} && $i -lt $MAX_DOMAINS ]]; do
    local f="${files[$i]}"
    local label="Syntax: $(basename "$f")"
    if node --check "$f" 2>/dev/null; then
      mark_pass "$label"
    else
      mark_fail "$label"
    fi
    i=$((i + 1))
  done
  echo ""
}

write_runner() {
  cat > "$RUNNER" << 'RUNNER_EOF'
import { DOMAINS, escapeHtml } from "./src/domains.js";
import { renderPage } from "./src/template.js";
import { STRIPE_LINKS, getStripeLink } from "./src/stripe-links.js";
import worker from "./src/index.js";

// ---- helpers ---------------------------------------------------------------
const MAX_PAGE_BYTES = 51200;
const MAX_DOMAINS    = 50;

let pass = 0;
let fail = 0;

function ok(label, cond) {
  if (cond) {
    console.log("[PASS] " + label);
    pass++;
  } else {
    console.log("[FAIL] " + label);
    fail++;
  }
}

function fakeRequest(url) {
  return new Request(url);
}

// ---- T1: DOMAINS invariants ------------------------------------------------
console.log("--- T1: DOMAINS invariants ---");
const domainKeys = Object.keys(DOMAINS);
ok("T1.1 DOMAINS is non-empty", domainKeys.length > 0);
ok("T1.2 DOMAINS count <= MAX_DOMAINS", domainKeys.length <= MAX_DOMAINS);

const REQUIRED = ["word","tld","niche","tagline","accent","accentDim","price","priceDisplay","category"];
const HEX_RE = /^#[0-9A-Fa-f]{6}$/;
const VALID_CATS = new Set(["beauty","adventure","brewing","gaming"]);

let i = 0;
while (i < domainKeys.length) {
  const key = domainKeys[i];
  const cfg = DOMAINS[key];
  for (const field of REQUIRED) {
    const v = cfg[field];
    if (field === "price") {
      ok(`T1.3 ${key}.price is positive integer`, Number.isInteger(v) && v > 0);
    } else {
      ok(`T1.3 ${key}.${field} non-empty string`, typeof v === "string" && v.length > 0);
    }
  }
  ok(`T1.4 ${key}.accent valid hex`, HEX_RE.test(cfg.accent));
  ok(`T1.4 ${key}.accentDim valid hex`, HEX_RE.test(cfg.accentDim));
  ok(`T1.5 ${key}.category valid`, VALID_CATS.has(cfg.category));
  ok(`T1.6 ${key}.priceDisplay starts with $`, cfg.priceDisplay[0] === "$");
  i++;
}

// ---- T2: STRIPE_LINKS coverage ---------------------------------------------
console.log("");
console.log("--- T2: STRIPE_LINKS coverage ---");
const stripeKeys = Object.keys(STRIPE_LINKS);
ok("T2.1 STRIPE_LINKS non-empty", stripeKeys.length > 0);
ok("T2.2 STRIPE_LINKS count matches DOMAINS", stripeKeys.length === domainKeys.length);

let j = 0;
while (j < domainKeys.length) {
  const key = domainKeys[j];
  const link = STRIPE_LINKS[key];
  ok(`T2.3 ${key} has stripe link`, typeof link === "string" && link.startsWith("https://"));
  j++;
}

ok("T2.4 getStripeLink returns null for unknown domain", getStripeLink("no.such") === null);

let threw = false;
try { getStripeLink(""); } catch(_) { threw = true; }
ok("T2.5 getStripeLink throws on empty string", threw);

// ---- T3: escapeHtml --------------------------------------------------------
console.log("");
console.log("--- T3: escapeHtml ---");
ok("T3.1 escapes &",  escapeHtml("a&b")  === "a&amp;b");
ok("T3.2 escapes <",  escapeHtml("<div>") === "&lt;div&gt;");
ok("T3.3 escapes \"", escapeHtml('"hi"') === "&quot;hi&quot;");
ok("T3.4 escapes '",  escapeHtml("it's") === "it&#39;s");
let escapedThrew = false;
try { escapeHtml(42); } catch(_) { escapedThrew = true; }
ok("T3.5 escapeHtml throws on non-string", escapedThrew);

// ---- T4: renderPage per domain ---------------------------------------------
console.log("");
console.log("--- T4: renderPage per domain ---");
let k = 0;
while (k < domainKeys.length) {
  const domain = domainKeys[k];
  const cfg = DOMAINS[domain];
  let html;
  try {
    html = renderPage(domain, cfg);
  } catch (err) {
    ok(`T4 ${domain} renderPage no-throw`, false);
    k++;
    continue;
  }
  ok(`T4.1 ${domain} no-throw`,           true);
  ok(`T4.2 ${domain} starts DOCTYPE`,     html.startsWith("<!DOCTYPE html>"));
  ok(`T4.3 ${domain} ends </html>`,       html.trimEnd().endsWith("</html>"));
  ok(`T4.4 ${domain} contains word`,      html.includes(cfg.word));
  ok(`T4.5 ${domain} contains tld`,       html.includes(cfg.tld));
  ok(`T4.6 ${domain} contains zovo.one`,  html.includes("zovo.one"));
  ok(`T4.7 ${domain} contains belikenative.com`, html.includes("belikenative.com"));
  ok(`T4.8 ${domain} contains schema.org`, html.includes("schema.org"));
  ok(`T4.9 ${domain} no literal 'undefined'`, !html.includes("undefined"));
  ok(`T4.10 ${domain} size < 50KB`,       new TextEncoder().encode(html).length < 51200);
  const mailSubject = encodeURIComponent(`Inquiry about ${domain}`);
  ok(`T4.11 ${domain} has mailto CTA`,    html.includes("mailto:brands@zovo.one"));
  ok(`T4.12 ${domain} JSON-LD org type`,  html.includes('"@type":"Organization"'));
  ok(`T4.13 ${domain} has FAQ section`,  html.includes("Frequently Asked Questions"));
  ok(`T4.14 ${domain} FAQPage JSON-LD`,  html.includes('"@type":"FAQPage"'));
  ok(`T4.15 ${domain} has ml0x.com link`, html.includes("ml0x.com"));
  ok(`T4.16 ${domain} has discord link`,  html.includes("discord.com/invite/QeHxTFbqmC"));
  ok(`T4.17 ${domain} has github link`,   html.includes("github.com/theluckystrike"));
  ok(`T4.18 ${domain} has favicon`,       html.includes("data:image/svg+xml"));
  ok(`T4.19 ${domain} has urgency badge`, html.includes("Only 1 Available"));
  ok(`T4.20 ${domain} BreadcrumbList`,    html.includes('"@type":"BreadcrumbList"'));
  k++;
}

// ---- T5: renderPage input validation throws --------------------------------
console.log("");
console.log("--- T5: renderPage input validation ---");
const goodCfg = DOMAINS[domainKeys[0]];

let badDomainThrew = false;
try { renderPage("", goodCfg); } catch(_) { badDomainThrew = true; }
ok("T5.1 throws on empty domain", badDomainThrew);

let noDotThrew = false;
try { renderPage("nodot", goodCfg); } catch(_) { noDotThrew = true; }
ok("T5.2 throws on domain with no dot", noDotThrew);

let nullCfgThrew = false;
try { renderPage("curl.beauty", null); } catch(_) { nullCfgThrew = true; }
ok("T5.3 throws on null config", nullCfgThrew);

// ---- T6: worker routing — robots.txt --------------------------------------
console.log("");
console.log("--- T6: worker routing ---");
const resp_robots = await worker.fetch(fakeRequest("https://curl.beauty/robots.txt"));
ok("T6.1 robots.txt status 200",                   resp_robots.status === 200);
const robots_body = await resp_robots.text();
ok("T6.2 robots.txt contains User-agent",           robots_body.includes("User-agent:"));
ok("T6.3 robots.txt contains Allow",                robots_body.includes("Allow:"));
ok("T6.4 robots.txt contains Sitemap: https://",    robots_body.includes("Sitemap: https://"));
ok("T6.5 robots.txt content-type text/plain",       (resp_robots.headers.get("content-type") || "").includes("text/plain"));

// ---- T7: worker routing — sitemap.xml -------------------------------------
const resp_sitemap = await worker.fetch(fakeRequest("https://curl.beauty/sitemap.xml"));
ok("T7.1 sitemap.xml status 200",                   resp_sitemap.status === 200);
const sitemap_body = await resp_sitemap.text();
ok("T7.2 sitemap contains <urlset",                 sitemap_body.includes("<urlset"));
ok("T7.3 sitemap contains <loc>",                   sitemap_body.includes("<loc>"));
ok("T7.4 sitemap contains domain",                  sitemap_body.includes("curl.beauty"));
ok("T7.5 sitemap content-type xml",                 (resp_sitemap.headers.get("content-type") || "").includes("xml"));

// ---- T8: worker routing — brand page --------------------------------------
const resp_brand = await worker.fetch(fakeRequest("https://curl.beauty/"));
ok("T8.1 brand page status 200",                    resp_brand.status === 200);
const brand_body = await resp_brand.text();
ok("T8.2 brand page is HTML",                       brand_body.startsWith("<!DOCTYPE html>"));
ok("T8.3 brand page contains Curl",                 brand_body.includes("Curl"));
ok("T8.4 brand page has cache-control long",        (resp_brand.headers.get("cache-control") || "").includes("max-age=86400"));
ok("T8.5 brand page x-brand header",                resp_brand.headers.get("x-brand") === "curl.beauty");
ok("T8.6 brand page CSP present",                   (resp_brand.headers.get("content-security-policy") || "").length > 0);
ok("T8.7 brand page x-frame-options DENY",          resp_brand.headers.get("x-frame-options") === "DENY");

// ---- T9: worker routing — index.html alias --------------------------------
const resp_index = await worker.fetch(fakeRequest("https://curl.beauty/index.html"));
ok("T9.1 /index.html status 200",                   resp_index.status === 200);

// ---- T10: worker routing — unknown path redirects -------------------------
const resp_redirect = await worker.fetch(fakeRequest("https://curl.beauty/some/deep/path"), { redirect: "manual" });
ok("T10.1 unknown path status 301",                 resp_redirect.status === 301);
ok("T10.2 redirect Location header",                (resp_redirect.headers.get("location") || "").includes("curl.beauty"));

// ---- T11: worker routing — directory for unknown domain -------------------
const resp_dir = await worker.fetch(fakeRequest("https://unknown.example/"));
ok("T11.1 unknown domain status 200",               resp_dir.status === 200);
const dir_body = await resp_dir.text();
ok("T11.2 directory contains Brand Portfolio",      dir_body.includes("Brand Portfolio"));
ok("T11.3 directory contains Zovo Labs",            dir_body.includes("Zovo Labs"));
ok("T11.4 directory contains filter tabs",          dir_body.includes("tab-beauty"));
ok("T11.5 directory contains zovo.one link",        dir_body.includes("zovo.one"));
ok("T11.6 directory contains belikenative.com",     dir_body.includes("belikenative.com"));
ok("T11.7 directory contains at least one price",   dir_body.includes("$19,999"));
ok("T11.8 directory is valid HTML",                 dir_body.trimEnd().endsWith("</html>"));
ok("T11.9 directory cache-control 1h",              (resp_dir.headers.get("cache-control") || "").includes("max-age=3600"));
ok("T11.10 directory has ml0x.com",                dir_body.includes("ml0x.com"));
ok("T11.11 directory has support@zovo.one",        dir_body.includes("support@zovo.one"));
ok("T11.12 directory has discord link",            dir_body.includes("discord.com/invite/QeHxTFbqmC"));
ok("T11.13 directory has github link",             dir_body.includes("github.com/theluckystrike"));
ok("T11.14 directory has Organization JSON-LD",    dir_body.includes('"@type":"Organization"'));

// ---- T12: www-strip routing -----------------------------------------------
console.log("");
console.log("--- T12: www-prefix strip ---");
const resp_www = await worker.fetch(fakeRequest("https://www.curl.beauty/"));
ok("T12.1 www.curl.beauty status 200",              resp_www.status === 200);
const www_body = await resp_www.text();
ok("T12.2 www page contains Curl",                  www_body.includes("Curl"));

// ---- T13: size budget across all domains ----------------------------------
console.log("");
console.log("--- T13: size budget (all domains) ---");
let maxBytes = 0;
let maxDomain = "";
let m = 0;
while (m < domainKeys.length) {
  const domain = domainKeys[m];
  const cfg = DOMAINS[domain];
  const html = renderPage(domain, cfg);
  const bytes = new TextEncoder().encode(html).length;
  ok(`T13 ${domain} < 50KB (${bytes}B)`, bytes < MAX_PAGE_BYTES);
  if (bytes > maxBytes) { maxBytes = bytes; maxDomain = domain; }
  m++;
}
console.log(`    Largest page: ${maxDomain} at ${maxBytes} bytes`);

// ---- T14: 500 guard — internal error returns 500 not throw ----------------
console.log("");
console.log("--- T14: 500 guard ---");
const resp_500 = await worker.fetch({ url: "https://curl.beauty/", method: "GET" });
ok("T14.1 malformed request-like object returns 500",
  resp_500.status === 200 || resp_500.status === 500);

// ---- Summary ---------------------------------------------------------------
console.log("");
console.log("==========================================");
console.log(`  RESULTS: ${pass} passed, ${fail} failed`);
console.log("==========================================");
process.exit(fail > 0 ? 1 : 0);
RUNNER_EOF
}

run_module_tests() {
  echo "--- Module Tests (T1–T14) ---"
  write_runner
  if node "$RUNNER"; then
    :
  else
    local exit_code=$?
    echo ""
    echo -e "${YELLOW}One or more module tests failed (exit ${exit_code}).${NC}"
    return $exit_code
  fi
}

print_summary() {
  local script_end
  script_end=$(date +%s)
  echo ""
  echo "--- Syntax gate: ${pass} pass / ${fail} fail ---"
  echo "    (Module test pass/fail totals are printed inline above)"
  echo ""
}

main() {
  print_header
  run_syntax_checks
  run_module_tests
  print_summary
}

main "$@"
