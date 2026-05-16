# Domain For-Sale Landing Pages

Static landing pages for domains listed for sale via Dan.com.

## Structure

```
domains/for-sale/
├── README.md
├── viryd.com/index.html        ($2,500)
├── neovistainc.com/index.html  ($1,500)
├── pictureeditor.net/index.html ($300)
└── recipetool.net/index.html   ($200)
```

## Regenerating Pages

Edit `config/domains-for-sale.json` to add/remove/update domains, then run:

```bash
python3 scripts/generate_landing_pages.py
```

Options:
- `--config path/to/config.json` — custom config file
- `--template path/to/template.html` — custom template
- `--output-dir path/to/output/` — custom output directory
- `--contact-email you@example.com` — override contact email

## Deployment to Cloudflare Pages

Each domain gets its own Cloudflare Pages project pointing to its subdirectory.

### Option A: Per-domain projects (recommended)

1. Push this repo to GitHub.
2. For each domain, create a Cloudflare Pages project:
   - Go to Cloudflare Dashboard > Pages > Create a project
   - Connect your GitHub repo
   - Set **Build output directory** to `domains/for-sale/{domain}`
   - Leave **Build command** empty (static files, no build needed)
3. Add the custom domain:
   - In the Pages project settings, go to Custom Domains
   - Add the domain (e.g., `viryd.com`)
   - Cloudflare will auto-configure DNS if the domain uses Cloudflare nameservers

### Option B: Single project with `_redirects`

If all domains resolve to one Cloudflare Pages project, create a `_redirects` file or use Cloudflare Workers to route by hostname.

### Option C: Wrangler CLI deployment

Deploy directly without GitHub integration:

```bash
# Install wrangler if needed
npm install -g wrangler

# Login
wrangler login

# Deploy a single domain
wrangler pages deploy domains/for-sale/viryd.com --project-name=viryd-com

# Add custom domain via dashboard or API after first deploy
```

### DNS Configuration

For each domain, ensure DNS points to Cloudflare Pages:
- If domain is on Cloudflare: custom domain setup handles it automatically
- If domain is elsewhere: add a CNAME record pointing to `{project}.pages.dev`

## Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{{DOMAIN}}` | Full domain name | `viryd.com` |
| `{{PRICE}}` | Numeric price | `2500` |
| `{{PRICE_FORMATTED}}` | Formatted price | `2,500` |
| `{{DAN_URL}}` | Dan.com listing URL | `https://dan.com/buy-domain/viryd.com` |
| `{{CONTACT_EMAIL}}` | Contact email | `domains@theluckystrike.com` |
