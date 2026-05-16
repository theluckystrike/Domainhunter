// stripe-links.js — Stripe payment link registry for Zovo brand domains.
// NASA P10: bounded data, assertions on every invariant, frozen export.

const MAX_LINKS = 50;

const _links = {
  "curl.beauty":    "https://buy.stripe.com/PLACEHOLDER_curl_beauty",
  "dawn.skin":      "https://buy.stripe.com/PLACEHOLDER_dawn_skin",
  "mist.hair":      "https://buy.stripe.com/PLACEHOLDER_mist_hair",
  "fawn.skin":      "https://buy.stripe.com/PLACEHOLDER_fawn_skin",
  "petal.hair":     "https://buy.stripe.com/PLACEHOLDER_petal_hair",
  "flax.hair":      "https://buy.stripe.com/PLACEHOLDER_flax_hair",
  "dusk.quest":     "https://buy.stripe.com/PLACEHOLDER_dusk_quest",
  "pine.beer":      "https://buy.stripe.com/PLACEHOLDER_pine_beer",
  "hops.garden":    "https://buy.stripe.com/PLACEHOLDER_hops_garden",
  "fjord.surf":     "https://buy.stripe.com/PLACEHOLDER_fjord_surf",
  "kelp.surf":      "https://buy.stripe.com/PLACEHOLDER_kelp_surf",
  "wort.beer":      "https://buy.stripe.com/PLACEHOLDER_wort_beer",
  "wraith.monster": "https://buy.stripe.com/PLACEHOLDER_wraith_monster",
  "bane.monster":   "https://buy.stripe.com/PLACEHOLDER_bane_monster",
};

// Assertion 1: link count must not exceed MAX_LINKS.
const _count = Object.keys(_links).length;
if (_count > MAX_LINKS) {
  throw new Error(
    `stripe-links: link count ${_count} exceeds MAX_LINKS ${MAX_LINKS}`
  );
}

// Assertion 2: every value must be a non-empty https:// string.
for (const [domain, url] of Object.entries(_links)) {
  if (typeof url !== "string" || url.length === 0 || !url.startsWith("https://")) {
    throw new Error(
      `stripe-links: invalid URL for domain "${domain}": "${url}"`
    );
  }
}

export const STRIPE_LINKS = Object.freeze(_links);

/**
 * Returns the Stripe payment link for a given domain, or null if not found.
 *
 * @param {string} domain - e.g. "curl.beauty"
 * @returns {string|null}
 */
export function getStripeLink(domain) {
  if (typeof domain !== "string" || domain.length === 0) {
    throw new Error("getStripeLink: domain must be a non-empty string");
  }
  const link = STRIPE_LINKS[domain];
  if (typeof link !== "string") {
    return null; // No link configured for this domain.
  }
  return link;
}
