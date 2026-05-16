const MAX_DOMAINS = 100;
const REQUIRED_FIELDS = ["word", "tld", "niche", "tagline", "accent", "accentDim", "price", "priceDisplay", "category"];
const HEX_COLOR_RE = /^#[0-9A-Fa-f]{6}$/;
const VALID_CATEGORIES = ["beauty", "adventure", "brewing", "gaming"];

function validateDomainConfig(key, cfg) {
  for (let i = 0; i < REQUIRED_FIELDS.length; i++) {
    const field = REQUIRED_FIELDS[i];
    if (field === "price") { continue; }
    if (typeof cfg[field] !== "string" || cfg[field].length === 0) {
      throw new Error("domains.js: missing field " + field + " on " + key);
    }
  }
  if (!HEX_COLOR_RE.test(cfg.accent)) {
    throw new Error("domains.js: invalid accent hex on " + key + ": " + cfg.accent);
  }
  if (!HEX_COLOR_RE.test(cfg.accentDim)) {
    throw new Error("domains.js: invalid accentDim hex on " + key + ": " + cfg.accentDim);
  }
  if (typeof cfg.price !== "number" || !Number.isInteger(cfg.price) || cfg.price <= 0) {
    throw new Error("domains.js: price must be a positive integer on " + key);
  }
  if (typeof cfg.priceDisplay !== "string" || cfg.priceDisplay.length === 0 || cfg.priceDisplay[0] !== "$") {
    throw new Error("domains.js: priceDisplay must be a non-empty string starting with $ on " + key);
  }
  if (VALID_CATEGORIES.indexOf(cfg.category) === -1) {
    throw new Error("domains.js: category must be one of beauty|adventure|brewing|gaming on " + key);
  }
}

function validateDomains(domains) {
  const keys = Object.keys(domains);
  if (keys.length > MAX_DOMAINS) {
    throw new Error("domains.js: exceeds MAX_DOMAINS (" + MAX_DOMAINS + ")");
  }
  for (let i = 0; i < keys.length; i++) {
    validateDomainConfig(keys[i], domains[keys[i]]);
  }
}

export function escapeHtml(str) {
  if (typeof str !== "string") {
    throw new Error("escapeHtml: expected string, got " + typeof str);
  }
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const _domains = {
  "curl.beauty": Object.freeze({
    word: "Curl",
    tld: "beauty",
    niche: "Curly Hair Care",
    tagline: "A curly hair beauty brand — this premium name is available for acquisition.",
    accent: "#E8A87C",
    accentDim: "#5C3D2E",
    price: 49999,
    priceDisplay: "$49,999",
    category: "beauty",
  }),
  "dawn.skin": Object.freeze({
    word: "Dawn",
    tld: "skin",
    niche: "Skincare",
    tagline: "A morning skincare ritual brand — this premium name is available for acquisition.",
    accent: "#F2C57C",
    accentDim: "#6B4E1E",
    price: 49999,
    priceDisplay: "$49,999",
    category: "beauty",
  }),
  "mist.hair": Object.freeze({
    word: "Mist",
    tld: "hair",
    niche: "Hair Care",
    tagline: "A lightweight hair mist brand — this premium name is available for acquisition.",
    accent: "#A8D8EA",
    accentDim: "#2E5A6B",
    price: 49999,
    priceDisplay: "$49,999",
    category: "beauty",
  }),
  "fawn.skin": Object.freeze({
    word: "Fawn",
    tld: "skin",
    niche: "Natural Skincare",
    tagline: "A gentle natural skincare brand — this premium name is available for acquisition.",
    accent: "#D4A574",
    accentDim: "#5C3D2E",
    price: 34999,
    priceDisplay: "$34,999",
    category: "beauty",
  }),
  "petal.hair": Object.freeze({
    word: "Petal",
    tld: "hair",
    niche: "Botanical Hair Care",
    tagline: "A botanical hair care brand — this premium name is available for acquisition.",
    accent: "#F4B8C1",
    accentDim: "#6B2E3A",
    price: 34999,
    priceDisplay: "$34,999",
    category: "beauty",
  }),
  "flax.hair": Object.freeze({
    word: "Flax",
    tld: "hair",
    niche: "Natural Hair Care",
    tagline: "A flaxseed-powered hair care brand — this premium name is available for acquisition.",
    accent: "#C8B560",
    accentDim: "#5C4E1E",
    price: 34999,
    priceDisplay: "$34,999",
    category: "beauty",
  }),
  "dusk.quest": Object.freeze({
    word: "Dusk",
    tld: "quest",
    niche: "Gaming & Adventure",
    tagline: "An atmospheric adventure brand — this premium name is available for acquisition.",
    accent: "#7B68AE",
    accentDim: "#2E1F5C",
    price: 24999,
    priceDisplay: "$24,999",
    category: "gaming",
  }),
  "pine.beer": Object.freeze({
    word: "Pine",
    tld: "beer",
    niche: "Craft Beer",
    tagline: "A craft pine beer brand — this premium name is available for acquisition.",
    accent: "#8FBC8F",
    accentDim: "#2E5C2E",
    price: 24999,
    priceDisplay: "$24,999",
    category: "brewing",
  }),
  "hops.garden": Object.freeze({
    word: "Hops",
    tld: "garden",
    niche: "Brewing & Garden",
    tagline: "A home brewing community brand — this premium name is available for acquisition.",
    accent: "#9ACD32",
    accentDim: "#3E5C0E",
    price: 24999,
    priceDisplay: "$24,999",
    category: "brewing",
  }),
  "fjord.surf": Object.freeze({
    word: "Fjord",
    tld: "surf",
    niche: "Adventure & Surf",
    tagline: "A Nordic surf adventure brand — this premium name is available for acquisition.",
    accent: "#5B9BD5",
    accentDim: "#1E3A5F",
    price: 49999,
    priceDisplay: "$49,999",
    category: "adventure",
  }),
  "kelp.surf": Object.freeze({
    word: "Kelp",
    tld: "surf",
    niche: "Ocean & Surf",
    tagline: "An ocean-inspired surf brand — this premium name is available for acquisition.",
    accent: "#2E8B57",
    accentDim: "#1A4A2E",
    price: 34999,
    priceDisplay: "$34,999",
    category: "adventure",
  }),
  "wort.beer": Object.freeze({
    word: "Wort",
    tld: "beer",
    niche: "Craft Brewing",
    tagline: "A craft brewing brand — this premium name is available for acquisition.",
    accent: "#DAA520",
    accentDim: "#5C3D0E",
    price: 24999,
    priceDisplay: "$24,999",
    category: "brewing",
  }),
  "wraith.monster": Object.freeze({
    word: "Wraith",
    tld: "monster",
    niche: "Gaming & Horror",
    tagline: "A dark gaming brand — this premium name is available for acquisition.",
    accent: "#8B0000",
    accentDim: "#3D0000",
    price: 19999,
    priceDisplay: "$19,999",
    category: "gaming",
  }),
  "bane.monster": Object.freeze({
    word: "Bane",
    tld: "monster",
    niche: "Gaming & Horror",
    tagline: "A fierce gaming brand — this premium name is available for acquisition.",
    accent: "#9B59B6",
    accentDim: "#4A1A6B",
    price: 19999,
    priceDisplay: "$19,999",
    category: "gaming",
  }),
};

validateDomains(_domains);

export const DOMAINS = Object.freeze(_domains);
