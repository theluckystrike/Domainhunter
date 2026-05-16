# Cloudflare Pages Deployment — Ingredient Calculator

## Prerequisites

- Cloudflare account with Pages enabled
- `wrangler` CLI installed (`npm install -g wrangler`)
- Authenticated: `wrangler login`
- Custom domain DNS managed by Cloudflare (if using custom domain)

## Project Setup

### 1. Create the Pages Project

```bash
wrangler pages project create ingredientcalculator --production-branch main
```

### 2. Build Settings

This is a **static site** — no build step required.

| Setting            | Value                                |
|--------------------|--------------------------------------|
| Framework preset   | None                                 |
| Build command       | _(leave empty)_                     |
| Build output dir    | `/`                                 |
| Root directory      | `tools/ingredientcalculator`        |
| Node.js version     | N/A                                 |

### 3. Deploy

```bash
# From the repo root:
wrangler pages deploy tools/ingredientcalculator --project-name=ingredientcalculator

# Or use the deploy script:
./deploy/deploy.sh
```

## Custom Domain Setup

### Option A: Subdomain (Recommended)

1. Go to **Cloudflare Dashboard > Pages > ingredientcalculator > Custom domains**
2. Add: `tools.yourdomain.com`
3. Cloudflare auto-creates the CNAME record

### Option B: Path-based (via Worker)

If serving at `yourdomain.com/tools/ingredientcalculator`:

1. Deploy a Cloudflare Worker that proxies requests from the path to the Pages project
2. Add a route in the Worker: `yourdomain.com/tools/ingredientcalculator/*`

### DNS Records

For subdomain deployment, Cloudflare adds automatically:

```
CNAME  tools  ingredientcalculator.pages.dev  (Proxied)
```

## Environment Variables

No environment variables are required for the static site.

If AdSense is added later:

| Variable             | Value              | Notes                     |
|----------------------|--------------------|---------------------------|
| `ADSENSE_PUBLISHER_ID` | `ca-pub-XXXXXXX` | Set in Pages > Settings  |

## Deployment Workflow

### Manual Deploy

```bash
# Production
wrangler pages deploy tools/ingredientcalculator --project-name=ingredientcalculator

# Preview (branch deploy)
wrangler pages deploy tools/ingredientcalculator --project-name=ingredientcalculator --branch=preview
```

### Automated Deploy (GitHub Integration)

1. Go to **Pages > ingredientcalculator > Settings > Builds & deployments**
2. Connect GitHub repository
3. Set:
   - Production branch: `main`
   - Preview branches: `dev`, `staging`
   - Root directory: `tools/ingredientcalculator`
   - Build command: _(empty)_

## Rollback

```bash
# List recent deployments
wrangler pages deployment list --project-name=ingredientcalculator

# Rollback to a specific deployment
wrangler pages deployment rollback --project-name=ingredientcalculator --deployment-id=<DEPLOYMENT_ID>
```

## Verification Checklist

After deployment, verify:

- [ ] Site loads at production URL
- [ ] HTTPS is active (auto-provisioned by Cloudflare)
- [ ] Security headers present (check via `curl -I` or securityheaders.com)
- [ ] `_redirects` working: `/calculator` serves `index.html`
- [ ] 404 page renders for unknown routes
- [ ] favicon.svg loads
- [ ] PWA manifest accessible at `/manifest.json`
- [ ] Cache-Control headers correct (3600 for HTML, 86400 for assets)
- [ ] Mobile responsive design works
