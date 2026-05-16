import { DOMAINS, escapeHtml } from "./domains.js";
import { renderPage } from "./template.js";

const MAX_DOMAINS = 50;
const CSP = "default-src 'self'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self'; frame-ancestors 'none'";

function buildRobotsResponse(domain) {
  const safeDomain = escapeHtml(domain);
  const body = `User-agent: *\nAllow: /\nSitemap: https://${safeDomain}/sitemap.xml`;
  return new Response(body, {
    headers: { "content-type": "text/plain" },
  });
}

function buildSitemapResponse(domain) {
  const safeDomain = escapeHtml(domain);
  const today = new Date().toISOString().split("T")[0];
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://${safeDomain}/</loc>
    <lastmod>${today}</lastmod>
    <priority>1.0</priority>
  </url>
</urlset>`;
  return new Response(body, {
    headers: { "content-type": "application/xml" },
  });
}

function buildDirectoryResponse() {
  const entries = Object.entries(DOMAINS);
  if (entries.length === 0) {
    throw new Error("DOMAINS must be non-empty");
  }
  if (entries.length > MAX_DOMAINS) {
    throw new Error(`DOMAINS exceeds MAX_DOMAINS bound of ${MAX_DOMAINS}`);
  }
  const html = renderDirectory(entries);
  return new Response(html, {
    headers: {
      "content-type": "text/html;charset=UTF-8",
      "cache-control": "public, max-age=3600",
      "content-security-policy": CSP,
      "x-content-type-options": "nosniff",
      "x-frame-options": "DENY",
    },
  });
}

function buildPageResponse(domain, config) {
  const html = renderPage(domain, config);
  return new Response(html, {
    headers: {
      "content-type": "text/html;charset=UTF-8",
      "cache-control": "public, max-age=86400, s-maxage=604800",
      "content-security-policy": CSP,
      "x-content-type-options": "nosniff",
      "x-frame-options": "DENY",
      "x-brand": escapeHtml(domain),
    },
  });
}

function routeRequest(request) {
  if (typeof request !== "object" || request === null) {
    throw new TypeError("request must be an object");
  }
  if (typeof request.url !== "string" || request.url.length === 0) {
    throw new TypeError("request.url must be a non-empty string");
  }

  const url = new URL(request.url);
  const domain = url.hostname.replace(/^www\./, "");

  if (url.pathname === "/robots.txt") {
    return buildRobotsResponse(domain);
  }

  if (url.pathname === "/sitemap.xml") {
    return buildSitemapResponse(domain);
  }

  const config = DOMAINS[domain];

  if (!config) {
    return buildDirectoryResponse();
  }

  if (url.pathname !== "/" && url.pathname !== "/index.html") {
    return Response.redirect(`https://${domain}/`, 301);
  }

  return buildPageResponse(domain, config);
}

export default {
  async fetch(request) {
    try {
      return routeRequest(request);
    } catch (err) {
      return new Response("Internal Server Error", {
        status: 500,
        headers: { "content-type": "text/plain" },
      });
    }
  },
};

function sortByPrice(entries) {
  if (!Array.isArray(entries) || entries.length === 0) {
    throw new TypeError("entries must be a non-empty array");
  }
  if (entries.length > MAX_DOMAINS) {
    throw new RangeError("entries exceeds MAX_DOMAINS bound");
  }
  return entries.slice().sort(([, a], [, b]) => {
    const pa = typeof a.price === "number" ? a.price : 0;
    const pb = typeof b.price === "number" ? b.price : 0;
    return pb - pa;
  });
}

function buildFilterTabs() {
  if (arguments.length !== 0) {
    throw new Error("buildFilterTabs takes no arguments");
  }
  const tabs = [
    { hash: "all", label: "All" },
    { hash: "beauty", label: "Beauty &amp; Skincare" },
    { hash: "brewing", label: "Brewing &amp; Food" },
    { hash: "gaming", label: "Gaming" },
    { hash: "adventure", label: "Adventure" },
  ];
  if (tabs.length !== 5) {
    throw new Error("filter tab count invariant violated");
  }
  const items = tabs.map(
    (t) => `<a href="#${t.hash}" class="tab" id="tab-${t.hash}">${t.label}</a>`
  ).join("");
  return `<nav class="tabs">${items}</nav>`;
}

function buildDirectoryCard(domain, c) {
  if (typeof domain !== "string" || domain.length === 0) {
    throw new TypeError("domain must be a non-empty string");
  }
  if (typeof c !== "object" || c === null) {
    throw new TypeError("config must be a non-null object");
  }
  const safeDomain = escapeHtml(domain);
  const safeWord = escapeHtml(c.word || "");
  const safeTld = escapeHtml(c.tld || "");
  const safeAccent = escapeHtml(c.accent || "#F2C57C");
  const safeAccentDim = escapeHtml(c.accentDim || c.accent || "#F2C57C");
  const safeNiche = escapeHtml(c.niche || "");
  const safePrice = escapeHtml(c.priceDisplay || "");
  const safeCat = escapeHtml(c.category || "");
  return `<div class="card" data-cat="${safeCat}">
  <div class="card-top">
    <span class="dot" style="background:${safeAccent}"></span>
    <span class="brand-name" style="font-family:'Playfair Display',serif">${safeWord}<span style="color:${safeAccent}">.${safeTld}</span></span>
  </div>
  <span class="niche-badge">${safeNiche}</span>
  <div class="card-bottom">
    <span class="price" style="color:${safeAccent}">${safePrice}</span>
    <a href="https://${safeDomain}" class="view-link" style="--accent:${safeAccent};--accent-dim:${safeAccentDim}">View Brand &#8594;</a>
  </div>
</div>`;
}

function renderDirectory(entries) {
  if (!Array.isArray(entries) || entries.length === 0) {
    throw new TypeError("entries must be a non-empty array");
  }
  if (entries.length > MAX_DOMAINS) {
    throw new RangeError("entries exceeds MAX_DOMAINS bound");
  }
  const sorted = sortByPrice(entries);
  const cards = sorted.map(([domain, c]) => buildDirectoryCard(domain, c)).join("\n");
  const filterTabs = buildFilterTabs();
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Brand Portfolio — Zovo Labs</title>
<meta name="description" content="Premium brand names available for acquisition. Each includes the domain, brand identity system, and a launch-ready landing page.">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Outfit:wght@300;400;500&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Outfit',sans-serif;background:#0a0a0a;color:#f5f5f0;min-height:100vh;padding:60px 24px}
.wrap{max-width:960px;margin:0 auto}
h1{font-family:'Playfair Display',serif;font-size:clamp(32px,5vw,52px);margin-bottom:14px;letter-spacing:-0.5px}
.sub{color:#8a8a7a;font-size:16px;font-weight:300;line-height:1.6;margin-bottom:40px;max-width:580px}
.sub a{color:#F2C57C;text-decoration:none}
.sub a:hover{text-decoration:underline}
.tabs{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:36px}
.tab{padding:8px 18px;border:1px solid #2a2a2a;border-radius:100px;font-size:13px;font-weight:400;color:#8a8a7a;text-decoration:none;letter-spacing:.3px;transition:all .18s}
.tab:hover{border-color:#444;color:#f5f5f0}
.tab:target,.tab.active{border-color:#F2C57C;color:#F2C57C}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.card{padding:26px 24px;background:#111;border:1px solid #1f1f1f;border-radius:10px;display:flex;flex-direction:column;gap:12px;transition:border-color .2s,transform .2s}
.card:hover{border-color:#333;transform:translateY(-3px)}
.card-top{display:flex;align-items:center;gap:10px}
.dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.brand-name{font-size:22px;font-weight:700;color:#f5f5f0;line-height:1.2}
.niche-badge{font-size:10px;letter-spacing:2.5px;text-transform:uppercase;color:#8a8a7a;font-weight:500}
.card-bottom{display:flex;align-items:center;justify-content:space-between;margin-top:4px}
.price{font-size:18px;font-weight:500;letter-spacing:.2px}
.view-link{font-size:13px;font-weight:400;color:var(--accent-dim);text-decoration:none;letter-spacing:.3px;transition:color .18s}
.view-link:hover{color:var(--accent)}
.dir-contact{margin-top:60px;text-align:center;display:flex;flex-direction:column;gap:14px;align-items:center}
.dc-link{display:inline-block;padding:10px 22px;border:1px solid #2a2a2a;border-radius:8px;color:#8a8a7a;text-decoration:none;font-size:14px;transition:all .2s}
.dc-link:hover{border-color:#F2C57C;color:#f5f5f0;transform:translateY(-2px)}
.dc-row{display:flex;flex-wrap:wrap;gap:10px;justify-content:center}
footer{margin-top:32px;text-align:center;display:flex;flex-direction:column;gap:10px;align-items:center}
footer a{font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:#8a8a7a;text-decoration:none;transition:color .18s}
footer a:hover{color:#f5f5f0}
.footer-bln{font-size:12px;letter-spacing:0;text-transform:none;color:#5a5a5a}
.footer-bln a{font-size:12px;letter-spacing:0;text-transform:none;color:#5a5a5a}
#beauty:target ~ .wrap .grid .card:not([data-cat="beauty"]){display:none}
#brewing:target ~ .wrap .grid .card:not([data-cat="brewing"]){display:none}
#gaming:target ~ .wrap .grid .card:not([data-cat="gaming"]){display:none}
#adventure:target ~ .wrap .grid .card:not([data-cat="adventure"]){display:none}
</style>
</head>
<body>
<div id="all"></div>
<div id="beauty"></div>
<div id="brewing"></div>
<div id="gaming"></div>
<div id="adventure"></div>
<div class="wrap">
<h1>Brand Portfolio</h1>
<p class="sub">Premium brand names available for acquisition. Each includes the domain, brand identity system, and a launch-ready landing page. A <a href="https://zovo.one">Zovo Labs</a> collection.</p>
${filterTabs}
<div class="grid">
${cards}
</div>
<div class="dir-contact">
<a href="https://ml0x.com" class="dc-link">ML0X.COM — Premium Domain Exchange</a>
<div class="dc-row">
<a href="mailto:support@zovo.one" class="dc-link">support@zovo.one</a>
<a href="https://zovo.one" class="dc-link">zovo.one</a>
<a href="https://github.com/theluckystrike" class="dc-link">GitHub</a>
<a href="https://discord.com/invite/QeHxTFbqmC" class="dc-link">Discord @zovo</a>
</div>
</div>
<footer>
<a href="https://zovo.one">Powered by Zovo Labs</a>
<span class="footer-bln">Built on <a href="https://www.belikenative.com" rel="dofollow">belikenative</a></span>
</footer>
</div>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"Zovo Labs","url":"https://zovo.one","sameAs":["https://github.com/theluckystrike","https://discord.com/invite/QeHxTFbqmC","https://ml0x.com"]}</script>
</body>
</html>`;
}
