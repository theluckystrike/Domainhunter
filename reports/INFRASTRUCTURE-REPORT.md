# DOMAIN HUNTER — Infrastructure Setup Complete
## DNS + Cloudflare Pages + Google Search Console | May 7, 2026

---

## CUSTOM DOMAINS — LIVE

| Domain | Status | CNAME Target | SSL | HTTP |
|--------|--------|-------------|-----|------|
| **ingredientcalculator.com** | LIVE | ingredientcalculator.pages.dev | Google CA | 200 |
| **www.ingredientcalculator.com** | LIVE | ingredientcalculator.pages.dev | Google CA | 200 |
| **pictureeditor.net** | LIVE | pictureeditor.pages.dev | Google CA | 200 |
| **www.pictureeditor.net** | LIVE | pictureeditor.pages.dev | Google CA | 200 |

### DNS Records Created (Cloudflare API)

| Zone | Type | Name | Content | Proxied |
|------|------|------|---------|---------|
| ingredientcalculator.com | CNAME | @ | ingredientcalculator.pages.dev | Yes |
| ingredientcalculator.com | CNAME | www | ingredientcalculator.pages.dev | Yes |
| ingredientcalculator.com | TXT | @ | google-site-verification=thDvZAKY-... | — |
| pictureeditor.net | CNAME | @ | pictureeditor.pages.dev | Yes |
| pictureeditor.net | CNAME | www | pictureeditor.pages.dev | Yes |
| pictureeditor.net | TXT | @ | google-site-verification=-xKx8UCmB... | — |
| recipetool.net | TXT | @ | google-site-verification=DGozdEND5... | — |

---

## GOOGLE SEARCH CONSOLE — VERIFIED

| Property | Level | Sitemap | Status |
|----------|-------|---------|--------|
| ingredientcalculator.com | **siteOwner** | Submitted (1 URL, 0 errors) | INDEXED |
| pictureeditor.net | **siteOwner** | Submitted (1 URL, 0 errors) | INDEXED |
| recipetool.net | **siteOwner** | — (no tool deployed yet) | VERIFIED |

### Verification Method
- DNS TXT records via Google Site Verification API
- Service account: zovo-gsc-cleanup@zovo-extensions.iam.gserviceaccount.com
- All 3 domains verified as siteOwner

---

## CLOUDFLARE PAGES PROJECTS

| Project | Domain | Files | Deploy URL |
|---------|--------|-------|-----------|
| ingredientcalculator | ingredientcalculator.com | 6 | ad536145.ingredientcalculator.pages.dev |
| pictureeditor | pictureeditor.net | 4 | db969ad5.pictureeditor.pages.dev |

---

## API TOKENS

| Token | Scope | Used For |
|-------|-------|----------|
| CLOUDFLARE_API_TOKEN (cfut_JRG...) | Pages:Write | Deploying to Cloudflare Pages |
| CLOUDFLARE_DNS_TOKEN (cfut_P4V...) | Zone:DNS:Edit | Creating CNAME/TXT records |
| gcloud SA (zovo-gsc-cleanup@...) | webmasters, siteverification | GSC property management |

All tokens stored in `/Users/mike/Desktop/domainhunter/.env`

---

## INFRASTRUCTURE CHECKLIST

- [x] Cloudflare Pages projects created (2)
- [x] Static files deployed (ingredientcalculator: 6 files, pictureeditor: 4 files)
- [x] CNAME records created (4: apex + www for each domain)
- [x] SSL certificates provisioned (Google CA, auto-managed)
- [x] Custom domains resolving (HTTP 200 confirmed)
- [x] Security headers active (CSP, X-Frame-Options, X-Content-Type-Options)
- [x] Google Site Verification TXT records (3 domains)
- [x] GSC properties verified as siteOwner (3 domains)
- [x] Sitemaps submitted and downloaded (2 sites, 0 errors)
- [x] DNS token saved for future automation
- [ ] recipetool.net Pages deployment (pending — tool not built yet)

---

*All infrastructure fully automated via Cloudflare API + Google APIs. Zero manual dashboard clicks.*
*Generated: May 7, 2026*
