import { escapeHtml } from "./domains.js";
import { STRIPE_LINKS } from "./stripe-links.js";

const REQUIRED_FIELDS = ["word", "tld", "niche", "tagline", "accent", "accentDim", "price", "priceDisplay", "category"];
const HEX_COLOR_RE = /^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$/;

function assertValidDomain(domain) {
  if (typeof domain !== "string" || domain.length === 0) {
    throw new Error("renderPage: domain must be a non-empty string");
  }
  if (domain.indexOf(".") === -1) {
    throw new Error("renderPage: domain must contain a TLD separator");
  }
}

function assertValidConfig(config) {
  if (config === null || typeof config !== "object") {
    throw new Error("renderPage: config must be a non-null object");
  }
  for (const field of REQUIRED_FIELDS) {
    if (field === "price") { continue; }
    if (typeof config[field] !== "string" || config[field].length === 0) {
      throw new Error(`renderPage: config.${field} must be a non-empty string`);
    }
  }
  if (!HEX_COLOR_RE.test(config.accent)) {
    throw new Error(`renderPage: config.accent must be a valid hex color, got: ${config.accent}`);
  }
  if (!HEX_COLOR_RE.test(config.accentDim)) {
    throw new Error(`renderPage: config.accentDim must be a valid hex color, got: ${config.accentDim}`);
  }
  if (typeof config.price !== "number" || config.price <= 0 || !Number.isInteger(config.price)) {
    throw new Error(`renderPage: config.price must be a positive integer, got: ${config.price}`);
  }
  if (typeof config.priceDisplay !== "string" || config.priceDisplay.length === 0) {
    throw new Error("renderPage: config.priceDisplay must be a non-empty string");
  }
  if (typeof config.category !== "string") {
    throw new Error("renderPage: config.category must be a string");
  }
}

function renderStyles(config) {
  const { accent, accentDim } = config;
  return `<style>
:root{--bg:#0a0a0a;--sf:#141414;--br:#1f1f1f;--tx:#f5f5f0;--tm:#8a8a7a;--ac:${accent};--acd:${accentDim};--s:'Playfair Display',Georgia,serif;--n:'Outfit',-apple-system,sans-serif}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--n);background:var(--bg);color:var(--tx);min-height:100vh;-webkit-font-smoothing:antialiased}
body::before{content:'';position:fixed;inset:0;opacity:.03;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");pointer-events:none;z-index:999}
.g{width:340px;height:340px;background:radial-gradient(circle,var(--acd) 0%,transparent 70%);position:fixed;top:20%;left:50%;transform:translateX(-50%);opacity:.18;pointer-events:none;z-index:0}
section{position:relative;z-index:1}
.hero{display:flex;flex-direction:column;align-items:center;text-align:center;padding:80px 24px 60px}
.badge{display:inline-block;font-size:11px;font-weight:600;letter-spacing:3px;text-transform:uppercase;color:var(--ac);border:1px solid var(--acd);padding:6px 16px;border-radius:100px;margin-bottom:40px;opacity:0;animation:u .8s ease .2s forwards}
h1{font-family:var(--s);font-size:clamp(52px,11vw,100px);font-weight:700;line-height:1.02;letter-spacing:-3px;margin-bottom:20px;opacity:0;animation:u .8s ease .4s forwards}
h1 .d{color:var(--ac)}
.tl{font-size:18px;font-weight:300;color:var(--tm);line-height:1.7;max-width:480px;margin:0 auto 24px;opacity:0;animation:u .8s ease .6s forwards}
.hp{font-family:var(--s);font-size:clamp(36px,7vw,56px);font-weight:700;color:var(--ac);margin-bottom:12px;opacity:0;animation:u .8s ease .7s forwards}
.hs{font-size:14px;color:var(--tm);font-weight:300;opacity:0;animation:u .8s ease .8s forwards}
.inc{max-width:800px;margin:0 auto;padding:0 24px 80px}
.inc h2{font-family:var(--s);font-size:28px;text-align:center;margin-bottom:48px;opacity:0;animation:u .8s ease .2s forwards}
.ig{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.ic{background:var(--sf);border:1px solid var(--br);border-radius:10px;padding:28px 24px;opacity:0;animation:u .8s ease calc(.3s + var(--d,0s)) forwards}
.ic svg{margin-bottom:14px}
.ic h3{font-size:15px;font-weight:600;margin-bottom:8px}
.ic p{font-size:13px;color:var(--tm);line-height:1.6;font-weight:300}
.pv{max-width:800px;margin:0 auto;padding:0 24px 80px}
.pv h2{font-family:var(--s);font-size:28px;text-align:center;margin-bottom:48px;opacity:0;animation:u .8s ease .2s forwards}
.pvg{display:flex;gap:32px;justify-content:center;flex-wrap:wrap}
.mk{flex:1;min-width:260px;max-width:340px;opacity:0;animation:u .8s ease .4s forwards}
.bot{width:100%;height:360px;background:linear-gradient(135deg,var(--acd),var(--ac));border-radius:20px 20px 6px 6px;display:flex;align-items:center;justify-content:center;position:relative;box-shadow:0 20px 60px rgba(0,0,0,.4)}
.bot::after{content:'';position:absolute;bottom:-10px;left:20%;right:20%;height:10px;background:rgba(0,0,0,.3);border-radius:50%;filter:blur(6px)}
.bot span{font-family:var(--s);font-size:36px;font-weight:700;color:#fff;text-shadow:0 2px 8px rgba(0,0,0,.3);letter-spacing:-1px}
.soc{width:100%;background:var(--sf);border:1px solid var(--br);border-radius:14px;padding:28px 24px;opacity:0;animation:u .8s ease .5s forwards}
.sav{width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,var(--ac),var(--acd));margin:0 auto 16px}
.sn{font-family:var(--s);font-size:20px;font-weight:700;text-align:center;margin-bottom:4px}
.sh{font-size:13px;color:var(--tm);text-align:center;margin-bottom:12px}
.sb{font-size:13px;color:var(--tm);text-align:center;line-height:1.6;margin-bottom:16px;font-weight:300}
.sf{display:flex;justify-content:center;gap:28px}
.sf span{text-align:center;font-size:12px;color:var(--tm)}
.sf strong{display:block;font-size:16px;color:var(--tx);margin-bottom:2px}
.pr{text-align:center;padding:80px 24px;border-top:1px solid var(--br)}
.pp{font-family:var(--s);font-size:clamp(44px,8vw,72px);font-weight:700;color:var(--ac);margin-bottom:16px;opacity:0;animation:u .8s ease .2s forwards}
.ps{font-size:15px;color:var(--tm);font-weight:300;margin-bottom:40px;opacity:0;animation:u .8s ease .3s forwards}
.cta{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;margin-bottom:48px;opacity:0;animation:u .8s ease .4s forwards}
.b{display:inline-flex;align-items:center;padding:15px 34px;border-radius:6px;font-family:var(--n);font-size:15px;font-weight:500;text-decoration:none;transition:all .3s ease;cursor:pointer;border:none}
.bp{background:var(--ac);color:#000}
.bp:hover{transform:translateY(-2px);box-shadow:0 8px 32px var(--acd)}
.bg{background:transparent;color:var(--tm);border:1px solid var(--br)}
.bg:hover{border-color:var(--tm);color:var(--tx)}
.tr{display:flex;justify-content:center;gap:32px;flex-wrap:wrap;opacity:0;animation:u .8s ease .5s forwards}
.ti{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--tm)}
.ti svg{flex-shrink:0}
footer{padding:32px 24px;text-align:center;border-top:1px solid var(--br)}
footer p{font-size:13px;color:var(--tm);margin-bottom:8px}
footer a{color:var(--ac);text-decoration:none;font-weight:500;font-size:12px;letter-spacing:2px;text-transform:uppercase}
footer a:hover{text-decoration:underline}
@keyframes u{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:680px){.ig{grid-template-columns:1fr 1fr}.pvg{flex-direction:column;align-items:center}}
@media(max-width:480px){h1{letter-spacing:-1px}.ig{grid-template-columns:1fr}.cta{flex-direction:column;align-items:center}.tr{flex-direction:column;align-items:center;gap:16px}}
</style>`;
}

function renderHead(domain, config) {
  if (typeof domain !== "string") { throw new Error("renderHead: domain must be string"); }
  if (typeof config !== "object" || config === null) { throw new Error("renderHead: config required"); }

  const { word, tld, tagline, accent } = config;
  const eWord = escapeHtml(word);
  const eTld = escapeHtml(tld);
  const eTagline = escapeHtml(tagline);
  const eDomain = escapeHtml(domain);

  return `<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>${eWord}.${eTld} — Premium Brand Available</title>
<meta name="description" content="${eWord}.${eTld} — ${eTagline}">
<meta name="robots" content="index, follow">
<meta name="theme-color" content="${escapeHtml(accent)}">
<meta property="og:title" content="${eWord}.${eTld} — Premium Brand Available">
<meta property="og:description" content="${eTagline}">
<meta property="og:type" content="website">
<meta property="og:url" content="https://${eDomain}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="${eWord}.${eTld} — Premium Brand Available">
<meta name="twitter:description" content="${eTagline}">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='20' fill='${escapeHtml(accent).replace("#", "%23")}'/%3E%3Ctext x='50' y='72' font-family='serif' font-size='60' font-weight='700' text-anchor='middle' fill='white'%3E${eWord[0]}%3C/text%3E%3C/svg%3E">
<link rel="canonical" href="https://${eDomain}">
<link rel="dns-prefetch" href="https://fonts.googleapis.com">
<link rel="preload" href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Outfit:wght@300;400;500;600&display=swap" as="style">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Outfit:wght@300;400;500;600&display=swap" rel="stylesheet">
${renderStyles(config)}
${renderQuickWinStyles()}
</head>`;
}

function renderHero(domain, config) {
  if (typeof domain !== "string") { throw new Error("renderHero: domain must be string"); }
  if (typeof config !== "object" || config === null) { throw new Error("renderHero: config required"); }

  const { word, tld, niche, tagline, priceDisplay } = config;
  const eWord = escapeHtml(word);
  const eTld = escapeHtml(tld);
  const eNiche = escapeHtml(niche);
  const eTagline = escapeHtml(tagline);
  const ePrice = escapeHtml(priceDisplay);

  return `<section class="hero">
<div class="badge">${eNiche}</div>
<h1>${eWord}<span class="d">.${eTld}</span></h1>
<p class="tl">${eTagline}</p>
<div class="hp">${ePrice}</div>
<p class="hs">Includes domain, brand identity, and launch-ready landing page</p>
</section>`;
}

function renderIncludes(domain, config) {
  if (typeof domain !== "string") { throw new Error("renderIncludes: domain must be string"); }
  if (typeof config !== "object" || config === null) { throw new Error("renderIncludes: config required"); }

  const eDomain = escapeHtml(domain);
  const ac = escapeHtml(config.accent);
  const items = [
    { icon: `<svg width="24" height="24" fill="none" stroke="${ac}" stroke-width="1.5" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/></svg>`, t: "Premium Domain", d: `Fully registered ${eDomain} with instant transfer` },
    { icon: `<svg width="24" height="24" fill="none" stroke="${ac}" stroke-width="1.5" viewBox="0 0 24 24"><circle cx="13.5" cy="6.5" r="2.5"/><circle cx="19" cy="17" r="2"/><circle cx="6" cy="12" r="3"/><path d="M9 12h3.5l2 5M13.5 9v3"/></svg>`, t: "Brand Identity", d: "Color palette, typography system, and logo concept" },
    { icon: `<svg width="24" height="24" fill="none" stroke="${ac}" stroke-width="1.5" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>`, t: "Landing Page", d: "This production-ready page, transferred to your hosting" },
    { icon: `<svg width="24" height="24" fill="none" stroke="${ac}" stroke-width="1.5" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0V12a10 10 0 1 0-4 8"/></svg>`, t: "Social Handles", d: "Username availability report across major platforms" },
    { icon: `<svg width="24" height="24" fill="none" stroke="${ac}" stroke-width="1.5" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/></svg>`, t: "Brand Strategy", d: "One-page brand positioning and market analysis" },
    { icon: `<svg width="24" height="24" fill="none" stroke="${ac}" stroke-width="1.5" viewBox="0 0 24 24"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>`, t: "30-Day Support", d: "Post-sale guidance to launch your brand" },
  ];

  const cards = items.map((item, i) => {
    return `<div class="ic" style="--d:${i * 0.1}s">${item.icon}<h3>${item.t}</h3><p>${item.d}</p></div>`;
  }).join("");

  return `<section class="inc"><h2>What&#39;s Included</h2><div class="ig">${cards}</div></section>`;
}

function renderPreview(domain, config) {
  if (typeof domain !== "string") { throw new Error("renderPreview: domain must be string"); }
  if (typeof config !== "object" || config === null) { throw new Error("renderPreview: config required"); }

  const { word, tld, tagline } = config;
  const eWord = escapeHtml(word);
  const eTld = escapeHtml(tld);
  const eTagline = escapeHtml(tagline);

  const bottle = `<div class="mk"><div class="bot"><span>${eWord}</span></div></div>`;
  const social = `<div class="mk soc">
<div class="sav"></div>
<div class="sn">${eWord}</div>
<div class="sh">@${eWord.toLowerCase()}${eTld.toLowerCase()}</div>
<div class="sb">${eTagline}</div>
<div class="sf"><span><strong>1.2K</strong>followers</span><span><strong>847</strong>following</span><span><strong>24</strong>posts</span></div>
</div>`;

  return `<section class="pv"><h2>Brand Preview</h2><div class="pvg">${bottle}${social}</div></section>`;
}

function renderPricing(domain, config) {
  if (typeof domain !== "string") { throw new Error("renderPricing: domain must be string"); }
  if (typeof config !== "object" || config === null) { throw new Error("renderPricing: config required"); }

  const ePrice = escapeHtml(config.priceDisplay);
  const stripeUrl = STRIPE_LINKS[domain];
  const eSubject = encodeURIComponent(`Inquiry about ${domain}`);
  const ctaHref = stripeUrl ? escapeHtml(stripeUrl) : `mailto:brands@zovo.one?subject=${eSubject}`;
  const ac = escapeHtml(config.accent);

  const trustItems = [
    `<div class="ti"><svg width="16" height="16" fill="none" stroke="${ac}" stroke-width="1.5" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>Secure Payment</div>`,
    `<div class="ti"><svg width="16" height="16" fill="none" stroke="${ac}" stroke-width="1.5" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>48hr Transfer</div>`,
    `<div class="ti"><svg width="16" height="16" fill="none" stroke="${ac}" stroke-width="1.5" viewBox="0 0 24 24"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>30-Day Support</div>`,
  ];

  return `<section class="pr">
<div class="ur">Limited Edition — Only 1 Available</div>
<div class="pp">${ePrice}</div>
<p class="ps">One-time purchase. Full ownership transfer within 48 hours.</p>
<div class="cta">
<a href="${ctaHref}" class="b bp">Acquire This Brand — ${ePrice}</a>
<a href="mailto:brands@zovo.one?subject=${eSubject}" class="b bg">Questions? brands@zovo.one</a>
</div>
<div class="tr">${trustItems.join("")}</div>
</section>`;
}

function renderFooter(domain, config) {
  if (typeof domain !== "string") { throw new Error("renderFooter: domain must be string"); }
  if (typeof config !== "object" || config === null) { throw new Error("renderFooter: config required"); }

  return `<footer>
<p>Built with AI-powered tools from <a href="https://www.belikenative.com" rel="dofollow" title="belikenative — AI Writing Assistant">belikenative</a></p>
<a href="https://zovo.one">A Zovo Labs Brand</a>
</footer>`;
}

function renderQuickWinStyles() {
  if (arguments.length !== 0) { throw new Error("renderQuickWinStyles takes no arguments"); }
  return `<style>
.faq{max-width:800px;margin:0 auto;padding:0 24px 80px}
.faq h2{font-family:var(--s);font-size:28px;text-align:center;margin-bottom:48px}
.fq{background:var(--sf);border:1px solid var(--br);border-radius:10px;padding:24px;margin-bottom:12px;text-align:left}
.fq h3{font-size:15px;font-weight:600;margin-bottom:10px;color:var(--ac)}
.fq p{font-size:14px;color:var(--tm);line-height:1.7;font-weight:300}
.fq a{color:var(--ac);text-decoration:none}
.fq a:hover{text-decoration:underline}
.ct{max-width:800px;margin:0 auto;padding:0 24px 60px;text-align:center}
.ct h2{font-family:var(--s);font-size:28px;margin-bottom:36px}
.ctg{display:flex;flex-direction:column;gap:12px;align-items:center}
.ctl{display:inline-flex;align-items:center;gap:10px;padding:14px 28px;background:var(--sf);border:1px solid var(--br);border-radius:8px;color:var(--tm);text-decoration:none;font-size:14px;transition:all .2s;width:fit-content;min-width:320px;justify-content:center}
.ctl:hover{border-color:var(--ac);color:var(--tx);transform:translateY(-2px)}
.ctl svg{flex-shrink:0}
.ur{display:inline-block;font-size:12px;letter-spacing:2.5px;text-transform:uppercase;color:var(--ac);border:1px solid var(--acd);padding:8px 24px;border-radius:100px;margin-bottom:28px;animation:pulse 2s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
</style>`;
}

function buildFaqItems(domain, config) {
  if (typeof domain !== "string") { throw new Error("buildFaqItems: domain must be string"); }
  if (typeof config !== "object" || config === null) { throw new Error("buildFaqItems: config required"); }
  const d = escapeHtml(domain);
  const w = escapeHtml(config.word);
  const t = escapeHtml(config.tld);
  return [
    { q: `What&#39;s included with ${w}.${t}?`, a: `You receive the premium domain ${d}, a complete brand identity system (color palette, typography, logo concept), this production-ready landing page, a social handle availability report, brand positioning strategy, and 30 days of post-sale support.` },
    { q: "How does the transfer process work?", a: "After secure payment, we initiate domain transfer within 24 hours. Full ownership is transferred to your registrar account within 48 hours. All brand assets are delivered via a shared drive." },
    { q: `Can I preview the ${w} brand before purchasing?`, a: `You&#39;re looking at it! This page showcases the ${w} brand identity — the color palette, typography, and visual direction are all included in the purchase.` },
    { q: "Is financing available?", a: `For all brands, we offer flexible payment plans. Contact us at <a href="mailto:support@zovo.one">support@zovo.one</a> to discuss options.` },
    { q: "Who do I contact with questions?", a: `Email <a href="mailto:support@zovo.one">support@zovo.one</a>, join our <a href="https://discord.com/invite/QeHxTFbqmC">Discord</a>, or browse more brands at <a href="https://ml0x.com">ML0X.COM</a>.` },
  ];
}

function renderFaq(domain, config) {
  if (typeof domain !== "string") { throw new Error("renderFaq: domain must be string"); }
  if (typeof config !== "object" || config === null) { throw new Error("renderFaq: config required"); }
  const faqs = buildFaqItems(domain, config);
  const items = faqs.map(f => `<div class="fq"><h3>${f.q}</h3><p>${f.a}</p></div>`).join("");
  return `<section class="faq"><h2>Frequently Asked Questions</h2>${items}</section>`;
}

function renderFaqJsonLd(domain, config) {
  if (typeof domain !== "string") { throw new Error("renderFaqJsonLd: domain must be string"); }
  if (typeof config !== "object" || config === null) { throw new Error("renderFaqJsonLd: config required"); }
  const w = config.word;
  const t = config.tld;
  const d = domain;
  const faqs = [
    { q: `What's included with ${w}.${t}?`, a: `You receive the premium domain ${d}, a complete brand identity system, this production-ready landing page, social handle availability report, brand positioning strategy, and 30 days of post-sale support.` },
    { q: "How does the transfer process work?", a: "After secure payment, we initiate domain transfer within 24 hours. Full ownership is transferred to your registrar account within 48 hours." },
    { q: `Can I preview the ${w} brand before purchasing?`, a: `This page showcases the ${w} brand identity — the color palette, typography, and visual direction are all included.` },
    { q: "Is financing available?", a: "For all brands, we offer flexible payment plans. Contact support@zovo.one to discuss options." },
    { q: "Who do I contact with questions?", a: "Email support@zovo.one, join our Discord, or browse more brands at ML0X.COM." },
  ];
  const schema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": faqs.map(f => ({ "@type": "Question", "name": f.q, "acceptedAnswer": { "@type": "Answer", "text": f.a } }))
  };
  return `<script type="application/ld+json">${JSON.stringify(schema)}</script>`;
}

function renderBreadcrumbJsonLd(domain, config) {
  if (typeof domain !== "string") { throw new Error("renderBreadcrumbJsonLd: domain must be string"); }
  if (typeof config !== "object" || config === null) { throw new Error("renderBreadcrumbJsonLd: config required"); }
  const schema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      { "@type": "ListItem", "position": 1, "name": "Zovo Labs", "item": "https://zovo.one" },
      { "@type": "ListItem", "position": 2, "name": "Brand Portfolio", "item": "https://ml0x.com" },
      { "@type": "ListItem", "position": 3, "name": `${config.word}.${config.tld}`, "item": `https://${domain}` }
    ]
  };
  return `<script type="application/ld+json">${JSON.stringify(schema)}</script>`;
}

function renderContact() {
  if (arguments.length !== 0) { throw new Error("renderContact takes no arguments"); }
  const links = [
    { href: "https://ml0x.com", icon: `<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/></svg>`, label: "ML0X.COM — Premium Domain Exchange" },
    { href: "mailto:support@zovo.one", icon: `<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>`, label: "support@zovo.one" },
    { href: "https://zovo.one", icon: `<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>`, label: "zovo.one" },
    { href: "https://github.com/theluckystrike", icon: `<svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M12 .3a12 12 0 0 0-3.8 23.4c.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.4-1.8-1.4-1.8-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-6 0-1.2.5-2.3 1.3-3.1-.2-.4-.6-1.6.1-3.2 0 0 1-.3 3.4 1.2a11.5 11.5 0 0 1 6 0c2.3-1.5 3.3-1.2 3.3-1.2.7 1.6.2 2.8.1 3.2.8.8 1.3 1.9 1.3 3.2 0 4.6-2.8 5.6-5.5 5.9.5.4.9 1.2.9 2.2v3.3c0 .3.2.7.8.6A12 12 0 0 0 12 .3"/></svg>`, label: "github.com/theluckystrike" },
    { href: "https://discord.com/invite/QeHxTFbqmC", icon: `<svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M20.3 4.4a19.8 19.8 0 0 0-4.9-1.5.07.07 0 0 0-.08.04c-.2.4-.4.9-.6 1.2a18.3 18.3 0 0 0-5.5 0c-.2-.4-.4-.8-.6-1.2a.08.08 0 0 0-.08-.04 19.7 19.7 0 0 0-4.9 1.5.07.07 0 0 0-.03.03C.5 9-.3 13.6.1 18.1a.08.08 0 0 0 .03.05 19.9 19.9 0 0 0 6 3 .08.08 0 0 0 .08-.03c.5-.6.9-1.3 1.2-2a.08.08 0 0 0-.04-.1 13.1 13.1 0 0 1-1.9-.9.08.08 0 0 1 0-.13l.4-.3a.07.07 0 0 1 .08 0 14.2 14.2 0 0 0 12.1 0l.4.3a.08.08 0 0 1 0 .13c-.6.3-1.2.6-1.9.9a.08.08 0 0 0-.04.1c.4.7.8 1.4 1.2 2a.08.08 0 0 0 .08.03 19.8 19.8 0 0 0 6-3 .08.08 0 0 0 .03-.05c.5-5.2-.8-9.7-3.5-13.7a.06.06 0 0 0-.03-.03zM8 15.3c-1.2 0-2.2-1.1-2.2-2.4s1-2.4 2.2-2.4 2.2 1.1 2.2 2.4-1 2.4-2.2 2.4zm8 0c-1.2 0-2.2-1.1-2.2-2.4s1-2.4 2.2-2.4 2.2 1.1 2.2 2.4-1 2.4-2.2 2.4z"/></svg>`, label: "Discord @zovo" },
  ];
  const items = links.map(l => `<a href="${l.href}" class="ctl">${l.icon}${l.label}</a>`).join("");
  return `<section class="ct"><h2>Get in Touch</h2><div class="ctg">${items}</div></section>`;
}

function renderJsonLd(domain, config) {
  if (typeof domain !== "string") { throw new Error("renderJsonLd: domain must be string"); }
  if (typeof config !== "object" || config === null) { throw new Error("renderJsonLd: config required"); }

  const { word, tld, niche, price } = config;

  const schema = {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": `${word}.${tld}`,
    "description": `Premium ${niche} brand — domain and brand identity available for acquisition`,
    "brand": { "@type": "Brand", "name": `${word} ${tld}` },
    "offers": {
      "@type": "Offer",
      "price": String(price),
      "priceCurrency": "USD",
      "availability": "https://schema.org/InStock",
      "url": `https://${domain}`
    },
    "seller": {
      "@type": "Organization",
      "name": "Zovo Labs",
      "url": "https://zovo.one"
    }
  };

  return `<script type="application/ld+json">${JSON.stringify(schema)}</script>`;
}

export function renderPage(domain, config) {
  assertValidDomain(domain);
  assertValidConfig(config);

  const safeConfig = Object.freeze({
    word: config.word,
    tld: config.tld,
    niche: config.niche,
    tagline: config.tagline,
    accent: config.accent,
    accentDim: config.accentDim,
    price: config.price,
    priceDisplay: config.priceDisplay,
    category: config.category,
  });

  const head = renderHead(domain, safeConfig);
  const hero = renderHero(domain, safeConfig);
  const includes = renderIncludes(domain, safeConfig);
  const preview = renderPreview(domain, safeConfig);
  const pricing = renderPricing(domain, safeConfig);
  const faq = renderFaq(domain, safeConfig);
  const contact = renderContact();
  const footer = renderFooter(domain, safeConfig);
  const jsonLd = renderJsonLd(domain, safeConfig);
  const faqJsonLd = renderFaqJsonLd(domain, safeConfig);
  const breadcrumbJsonLd = renderBreadcrumbJsonLd(domain, safeConfig);

  return `<!DOCTYPE html>
<html lang="en">
${head}
<body>
<div class="g"></div>
${hero}
${includes}
${preview}
${pricing}
${faq}
${contact}
${footer}
${jsonLd}
${faqJsonLd}
${breadcrumbJsonLd}
</body>
</html>`;
}
