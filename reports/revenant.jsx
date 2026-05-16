import { useState } from "react";

const AGENTS = [
  {
    id: "scout",
    name: "SCOUT",
    role: "Discovery Agent",
    icon: "🔭",
    color: "#c8ff00",
    colorBg: "#c8ff0012",
    apis: ["WhoisFreaks API", "CatchDoms API", "Apify Actors", "ICANN CZDS"],
    cost: "$0-39/mo",
    priority: "P0 — builds first, feeds all others",
    description: "Pulls daily expired/dropped/pending-delete domain feeds. Filters by TLD (.com/.net/.io/.dev/.ai), removes junk (random strings, adult, gambling keywords). Outputs clean candidate list to shared queue.",
    inputs: ["Daily WhoisFreaks feed (10K domains free)", "CatchDoms filtered query (score_min=40)", "Apify ExpiredDomains.net scraper (weekly deep scan)"],
    outputs: ["Candidate queue: domain, TLD, drop_date, initial_backlinks, registrar", "Daily: 200-500 filtered candidates from 10K+ raw", "Deduplication across all sources"],
    acceptanceCriteria: [
      "Processes full WhoisFreaks daily feed in <5 minutes",
      "Filters OUT: domains with numbers >3, hyphens >1, length >25 chars",
      "Filters OUT: known spam TLDs (.xyz, .top, .click, .loan, .work)",
      "Filters IN: .com, .net, .io, .dev, .ai, .tools, .app only",
      "Keyword pre-filter: flags domains containing AI/dev/code/tool terms",
      "Deduplicates across WhoisFreaks + CatchDoms + Apify within 24hr window",
      "Writes structured JSON to /candidates/YYYY-MM-DD.json",
      "Sends Slack/webhook notification with daily candidate count",
      "Handles API rate limits with exponential backoff",
      "Logs all filtered-out domains with reason codes for audit"
    ],
    techStack: "Python 3.12 + asyncio + aiohttp | Cron: 03:30 UTC daily | Storage: SQLite → Postgres at scale",
    sprint: 1
  },
  {
    id: "sentinel",
    name: "SENTINEL",
    role: "SEO Vetting Agent",
    icon: "🛡️",
    color: "#00cc88",
    colorBg: "#00cc8812",
    apis: ["Moz API / Apify Moz Scraper", "DataForSEO Backlinks API", "Google Custom Search API"],
    cost: "$50-70/mo",
    priority: "P0 — primary quality gate",
    description: "Takes SCOUT's candidate list and runs every domain through a 3-layer SEO quality check: authority metrics (DA/DR), spam detection, and Google index verification. Kills 80-90% of candidates.",
    inputs: ["SCOUT candidate queue (200-500/day)", "Moz DA/PA/Spam Score", "DataForSEO backlink profile", "Google index page count"],
    outputs: ["Vetted queue: domain + DA + spam_score + ref_domains + anchor_profile + index_count", "Kill log with reason codes (low_da, high_spam, zero_index, toxic_anchors)", "Daily: 20-60 survivors from 200-500 candidates"],
    acceptanceCriteria: [
      "Moz check: PASS if DA ≥25, Spam Score <20%. KILL otherwise",
      "DataForSEO: PASS if referring_domains ≥100 AND branded_anchors ≥40%",
      "DataForSEO: FLAG if exact_match_anchors >30% (link scheme signal)",
      "DataForSEO: FLAG if >80% referring domains from single country (unless EN)",
      "Google index: PASS if site:domain.com returns >0 results. KILL if zero",
      "Google index: BONUS if >100 pages still indexed",
      "Batches Moz checks in groups of 10 (Apify scraper limit)",
      "Respects Google Custom Search 100/day free limit — prioritizes highest DA candidates",
      "Processes full daily candidate list within 2 hours",
      "Outputs structured report with pass/fail/flag per check"
    ],
    techStack: "Python 3.12 + DataForSEO SDK + Moz via Apify | Parallel processing: 3 API streams",
    sprint: 1
  },
  {
    id: "archivist",
    name: "ARCHIVIST",
    role: "History Verification Agent",
    icon: "📜",
    color: "#85B7EB",
    colorBg: "#85B7EB12",
    apis: ["Wayback CDX API", "Wayback Availability API", "WhoisFreaks WHOIS History", "Whoxy WHOIS"],
    cost: "$0/mo",
    priority: "P1 — deep validation on survivors only",
    description: "Takes SENTINEL survivors and performs deep history analysis. Checks Wayback archive age, content consistency over time, detects spam injection periods, verifies WHOIS ownership patterns. The truth-teller agent.",
    inputs: ["SENTINEL vetted queue (20-60/day)", "Wayback CDX full snapshot history", "WHOIS registration history"],
    outputs: ["History report per domain: archive_age, content_pivots, spam_periods, ownership_changes", "Red flag alerts: Japanese/Chinese spam injection, sudden content pivots, PBN patterns", "Clean queue: 5-15 fully verified domains/day"],
    acceptanceCriteria: [
      "Wayback: PASS if earliest snapshot ≥3 years ago with HTTP 200",
      "Wayback: IDEAL if ≥5 years continuous history with consistent content",
      "Wayback: RED FLAG if content language changes (EN→JP/CN = spam injection)",
      "Wayback: RED FLAG if >6 month gap then completely different content",
      "CDX deep scan: fetches last 5 snapshots across different years, extracts <title> tags",
      "Title consistency check: >60% similar titles across years = legitimate site",
      "WHOIS: RED FLAG if >5 ownership transfers in 3 years (domain flipper/PBN)",
      "WHOIS: BONUS if single owner for 3+ years (stable history)",
      "Processes 20-60 domains in <30 minutes (CDX is fast, no auth)",
      "Generates per-domain history timeline visualization data"
    ],
    techStack: "Python 3.12 + waybackpy + BeautifulSoup | No auth needed | Rate: be polite, 1 req/sec to archive.org",
    sprint: 2
  },
  {
    id: "spectre",
    name: "SPECTRE",
    role: "Niche Relevance Agent",
    icon: "👻",
    color: "#AFA9EC",
    colorBg: "#AFA9EC12",
    apis: ["GitHub API", "Reddit API", "DataForSEO SERP API", "Claude Sonnet (classification)"],
    cost: "$5-15/mo",
    priority: "P1 — the differentiator, your unfair advantage",
    description: "The agent nobody else is running. Takes ARCHIVIST-verified domains and scores them for dev tools / AI coding niche relevance. Checks if backlinks come from tech sources, if the domain was discussed in dev communities, and uses LLM classification on Wayback content.",
    inputs: ["ARCHIVIST clean queue (5-15/day)", "Backlink referring domain list (from SENTINEL)", "Wayback archived content samples", "GitHub/Reddit mention data"],
    outputs: ["Niche relevance score 0-100 per domain", "Relevance breakdown: tech_backlinks%, dev_community_mentions, content_topic_match", "Final shortlist: 1-5 domains/day with full dossier"],
    acceptanceCriteria: [
      "Classifies each referring domain as: tech/dev, general, spam, other",
      "Tech backlink ratio: domains with >30% tech referring domains score higher",
      "GitHub search: checks if domain URL appears in any repo README, issues, or docs",
      "Reddit search: checks mentions in r/webdev, r/programming, r/devtools, r/MachineLearning, r/LocalLLaMA",
      "LLM classification: feeds last Wayback snapshot to Claude Sonnet, asks 'Is this domain about: software development, AI tools, coding, developer resources, or tech? Score 1-10'",
      "Keyword match against target niche terms (see NICHE MATRIX below)",
      "Composite score: 40% backlink_niche + 25% content_topic + 20% community_mentions + 15% keyword_match",
      "IDEAL domain: was a dev blog, tool documentation site, or tech comparison site",
      "Processes 5-15 domains in <20 minutes",
      "Outputs ranked list with full reasoning per domain"
    ],
    techStack: "Python 3.12 + GitHub PyGithub + PRAW (Reddit) + Anthropic SDK | Claude Sonnet for classification",
    sprint: 2
  },
  {
    id: "oracle",
    name: "ORACLE",
    role: "Decision & Scoring Agent",
    icon: "🔮",
    color: "#F0997B",
    colorBg: "#F0997B12",
    apis: ["Claude Opus (final judgment)", "GoDaddy/Dynadot availability check", "Namecheap API"],
    cost: "$2-5/mo",
    priority: "P2 — final human-in-the-loop gate",
    description: "The final brain. Aggregates all data from all 4 agents, applies your masterplan's exact scoring weights, generates a buy/pass/investigate verdict with full reasoning. Checks current registration status and estimated acquisition cost. Presents a decision-ready dossier.",
    inputs: ["All upstream agent data merged into single domain profile", "Your scoring criteria weights", "Current domain availability/auction status"],
    outputs: ["Final dossier per domain: verdict, score, price estimate, risk assessment", "Weekly digest email: top 3-5 domains with one-click buy links", "Running database of all scored domains for pattern analysis"],
    acceptanceCriteria: [
      "Weighted scoring algorithm matching YOUR masterplan criteria exactly:",
      "  → Domain Rating (25%): DA 25-35 = 60pts, 35-50 = 90pts, 50+ = 70pts (too high = suspicious)",
      "  → Referring Domains (20%): 100-300 = 70pts, 300-1000 = 95pts, 1000+ = 80pts",
      "  → Niche Relevance (20%): SPECTRE score directly (0-100)",
      "  → Archive History (15%): 3-5yr = 70pts, 5-10yr = 90pts, 10+ = 100pts",
      "  → Anchor Profile (10%): >60% branded = 90pts, 40-60% = 70pts, <40% = 40pts",
      "  → Price (10%): <$500 = 100pts, $500-2000 = 80pts, $2000-5000 = 50pts, >$5K = 20pts",
      "Checks domain availability via registrar APIs (GoDaddy, Namecheap, Dynadot)",
      "Verdict categories: BUY NOW (score >80), INVESTIGATE (60-80), PASS (<60)",
      "Generates natural language reasoning for each verdict via Claude Opus",
      "Weekly email digest with top domains, formatted for mobile reading",
      "Stores all scored domains in persistent database for trend analysis"
    ],
    techStack: "Python 3.12 + Anthropic SDK (Opus) + Resend (email) | SQLite/Postgres | Runs after SPECTRE completes",
    sprint: 3
  }
];

const NICHE_KEYWORDS = {
  "Tier 1 — Money Models": ["claude code", "cursor", "copilot", "kimi", "qwen", "codex", "windsurf", "gemini code assist", "cline", "aider", "continue dev"],
  "Tier 2 — Model Names": ["gpt-5", "opus", "sonnet", "o3", "deepseek", "llama", "mistral", "claude", "gemini", "command-r"],
  "Tier 3 — Tool Categories": ["ai coding", "ai code review", "ai dev tools", "llm benchmark", "ai model comparison", "token calculator", "context window", "ai agent", "code assistant"],
  "Tier 4 — Dev Ecosystem": ["vscode extension", "jetbrains plugin", "neovim ai", "ide ai", "ai terminal", "ai cli", "prompt engineering", "ai debugging", "ai testing"]
};

const SPRINTS = [
  {
    number: 1,
    name: "Foundation",
    duration: "Week 1-2",
    goal: "SCOUT + SENTINEL operational. Daily candidate pipeline running.",
    tasks: [
      { task: "Set up project repo, CI/CD, env configs", effort: "4h", owner: "Dev" },
      { task: "WhoisFreaks API integration + daily cron", effort: "6h", owner: "Dev" },
      { task: "CatchDoms API integration + filters", effort: "4h", owner: "Dev" },
      { task: "Apify ExpiredDomains.net actor config", effort: "3h", owner: "Dev" },
      { task: "SCOUT TLD/keyword pre-filter logic", effort: "4h", owner: "Dev" },
      { task: "Deduplication engine across 3 sources", effort: "3h", owner: "Dev" },
      { task: "Moz DA/Spam bulk checker (Apify scraper)", effort: "5h", owner: "Dev" },
      { task: "DataForSEO backlink profile integration", effort: "5h", owner: "Dev" },
      { task: "Google Custom Search index checker", effort: "3h", owner: "Dev" },
      { task: "SENTINEL scoring logic + kill/pass rules", effort: "4h", owner: "Dev" },
      { task: "Candidate queue JSON schema + storage", effort: "2h", owner: "Dev" },
      { task: "Slack/webhook notification system", effort: "2h", owner: "Dev" },
      { task: "Sprint 1 integration test: full SCOUT→SENTINEL flow", effort: "4h", owner: "Dev" },
      { task: "Deploy to server, configure cron jobs", effort: "3h", owner: "Dev" },
    ],
    milestone: "First daily run produces 20-60 DA-vetted candidates from 10K+ raw domains",
    risk: "WhoisFreaks free tier may not include backlink counts — fallback: use CatchDoms as primary for metric-rich domains"
  },
  {
    number: 2,
    name: "Deep validation",
    duration: "Week 3-4",
    goal: "ARCHIVIST + SPECTRE operational. Full pipeline end-to-end.",
    tasks: [
      { task: "Wayback CDX API integration + snapshot parser", effort: "5h", owner: "Dev" },
      { task: "Content consistency analyzer (title extraction across years)", effort: "4h", owner: "Dev" },
      { task: "Spam injection detector (language change, content pivot)", effort: "4h", owner: "Dev" },
      { task: "WHOIS history integration (WhoisFreaks + Whoxy)", effort: "3h", owner: "Dev" },
      { task: "ARCHIVIST scoring logic + red flag system", effort: "3h", owner: "Dev" },
      { task: "GitHub API: domain mention search in repos/issues", effort: "4h", owner: "Dev" },
      { task: "Reddit API (PRAW): mention search in target subreddits", effort: "3h", owner: "Dev" },
      { task: "Claude Sonnet integration: content topic classifier", effort: "4h", owner: "Dev" },
      { task: "SPECTRE niche keyword matrix implementation", effort: "3h", owner: "Dev" },
      { task: "SPECTRE composite scoring algorithm", effort: "3h", owner: "Dev" },
      { task: "Full pipeline integration: SCOUT→SENTINEL→ARCHIVIST→SPECTRE", effort: "5h", owner: "Dev" },
      { task: "Backfill test: run last 7 days of SCOUT data through new agents", effort: "3h", owner: "Dev" },
    ],
    milestone: "Pipeline produces 1-5 niche-scored, history-verified domains daily",
    risk: "Wayback CDX can be slow for domains with 1000s of snapshots — implement timeout + sampling strategy"
  },
  {
    number: 3,
    name: "Intelligence layer",
    duration: "Week 5-6",
    goal: "ORACLE live. Full dossier generation. Weekly digest shipping.",
    tasks: [
      { task: "ORACLE weighted scoring algorithm (matching masterplan criteria)", effort: "4h", owner: "Dev" },
      { task: "Domain availability checker (GoDaddy/Namecheap/Dynadot APIs)", effort: "4h", owner: "Dev" },
      { task: "Claude Opus verdict generator (natural language reasoning)", effort: "4h", owner: "Dev" },
      { task: "Domain dossier template (HTML email + dashboard view)", effort: "5h", owner: "Dev" },
      { task: "Weekly digest email system (Resend API)", effort: "3h", owner: "Dev" },
      { task: "Persistent database: all scored domains + historical trends", effort: "4h", owner: "Dev" },
      { task: "Dashboard: real-time pipeline status + top domains", effort: "6h", owner: "Dev" },
      { task: "One-click buy links in dossier (direct to registrar)", effort: "2h", owner: "Dev" },
      { task: "Alert system: notify within 1hr when score >85 domain found", effort: "2h", owner: "Dev" },
      { task: "Full end-to-end test: 14 days of historical data through complete pipeline", effort: "4h", owner: "Dev" },
      { task: "Documentation: runbook, API key rotation, monitoring", effort: "3h", owner: "Dev" },
    ],
    milestone: "Receiving weekly email with top 3-5 domain recommendations + full dossiers",
    risk: "Claude Opus costs can spike if too many domains reach ORACLE — implement strict upstream filtering"
  },
  {
    number: 4,
    name: "Optimization + first acquisition",
    duration: "Week 7-8",
    goal: "Tune scoring based on real data. Buy first domain. Validate pipeline accuracy.",
    tasks: [
      { task: "Analyze 4 weeks of pipeline data: false positive/negative rates", effort: "4h", owner: "PM + Dev" },
      { task: "Tune SENTINEL thresholds based on actual DA distribution", effort: "3h", owner: "Dev" },
      { task: "Tune SPECTRE niche weights based on backlink quality audit", effort: "3h", owner: "Dev" },
      { task: "Add new niche keywords from trending AI tool launches", effort: "2h", owner: "PM" },
      { task: "Buy first domain from ORACLE's top recommendations", effort: "2h", owner: "PM" },
      { task: "Post-acquisition: validate ORACLE's predictions vs reality", effort: "4h", owner: "PM + Dev" },
      { task: "Implement feedback loop: acquisition outcomes → scoring weights", effort: "4h", owner: "Dev" },
      { task: "Performance optimization: reduce daily pipeline runtime to <1hr", effort: "3h", owner: "Dev" },
      { task: "Cost audit: actual API spend vs budget, optimize calls", effort: "2h", owner: "PM" },
      { task: "Sprint retrospective + v2 roadmap", effort: "2h", owner: "PM + Dev" },
    ],
    milestone: "First domain acquired. Pipeline accuracy validated. Scoring calibrated on real data.",
    risk: "First domain may not meet all criteria perfectly — that's fine, it calibrates the pipeline"
  }
];

const BUDGET = [
  { item: "WhoisFreaks (expired domains feed)", monthly: 0, note: "Free tier: 10K domains/day" },
  { item: "CatchDoms API", monthly: 39, note: "€468/yr = ~€39/mo. 370K+ domains, MCP server" },
  { item: "Apify (ExpiredDomains scraper)", monthly: 0, note: "Free tier credits, then ~$5/mo" },
  { item: "DataForSEO (backlinks + SERP)", monthly: 50, note: "Already in masterplan budget" },
  { item: "Moz API (via Apify scraper)", monthly: 0, note: "Apify actor scrapes free Moz analysis" },
  { item: "Google Custom Search API", monthly: 0, note: "100 free queries/day" },
  { item: "Wayback Machine CDX/Availability", monthly: 0, note: "Completely free, no auth" },
  { item: "WhoisFreaks WHOIS Lookup", monthly: 0, note: "Free tier for basic lookups" },
  { item: "GitHub API", monthly: 0, note: "Free: 5,000 requests/hour" },
  { item: "Reddit API (PRAW)", monthly: 0, note: "Free: 100 requests/minute" },
  { item: "Claude Sonnet (SPECTRE classifier)", monthly: 8, note: "~5-15 domains/day × ~$0.02/classification" },
  { item: "Claude Opus (ORACLE verdicts)", monthly: 5, note: "~1-5 domains/day × ~$0.05/verdict" },
  { item: "Resend (email)", monthly: 0, note: "Free tier: 100 emails/day" },
  { item: "Server (VPS)", monthly: 10, note: "$10/mo DigitalOcean or Railway" },
];

function App() {
  const [activeTab, setActiveTab] = useState("overview");
  const [expandedAgent, setExpandedAgent] = useState(null);
  const [expandedSprint, setExpandedSprint] = useState(null);

  const totalMonthly = BUDGET.reduce((s, b) => s + b.monthly, 0);

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "agents", label: "5 Agents" },
    { id: "sprints", label: "Sprints" },
    { id: "niche", label: "Niche matrix" },
    { id: "budget", label: "Budget" },
    { id: "rating", label: "Rating" },
  ];

  return (
    <div style={{ fontFamily: "'DM Mono', 'SF Mono', monospace", background: "#060708", color: "#c2bdb4", minHeight: "100vh" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,500;0,9..144,700;1,9..144,300&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::selection { background: #c8ff00; color: #060708; }
        .rev-tag { font-size: 10px; letter-spacing: 3px; color: #c8ff00; text-transform: uppercase; font-weight: 500; margin-bottom: 8px; }
        .rev-h1 { font-family: 'Fraunces', Georgia, serif; font-size: clamp(22px, 3.5vw, 32px); font-weight: 300; color: #eae6df; line-height: 1.2; }
        .rev-h1 em { font-style: italic; color: #c8ff00; font-weight: 500; }
        .rev-h2 { font-family: 'Fraunces', Georgia, serif; font-size: 18px; font-weight: 300; color: #eae6df; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 1px solid #1a1c22; }
        .rev-h3 { font-size: 10px; font-weight: 500; color: #c8ff00; letter-spacing: 1px; text-transform: uppercase; margin: 20px 0 8px; }
        .rev-card { background: #0c0d10; border: 1px solid #1a1c22; border-radius: 6px; padding: 16px; margin-bottom: 12px; }
        .rev-card-accent { border-left: 3px solid #c8ff00; }
        .rev-metric { display: inline-flex; align-items: baseline; gap: 4px; background: #c8ff0012; border: 1px solid #c8ff0020; border-radius: 3px; padding: 2px 8px; font-size: 12px; color: #c8ff00; }
        .rev-badge { display: inline-block; font-size: 10px; padding: 2px 8px; border-radius: 3px; font-weight: 500; }
        .rev-nav { display: flex; overflow-x: auto; gap: 2px; border-bottom: 1px solid #1a1c22; margin-bottom: 24px; scrollbar-width: none; }
        .rev-nav::-webkit-scrollbar { display: none; }
        .rev-nav button { padding: 10px 14px; font-family: 'DM Mono', monospace; font-size: 11px; color: #6b6660; background: none; border: none; cursor: pointer; white-space: nowrap; border-bottom: 2px solid transparent; transition: all 0.2s; }
        .rev-nav button:hover { color: #c2bdb4; }
        .rev-nav button.active { color: #c8ff00; border-bottom-color: #c8ff00; }
        .rev-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 20px; }
        .rev-stat { background: #0c0d10; border: 1px solid #1a1c22; border-radius: 6px; padding: 12px 14px; }
        .rev-stat-label { font-size: 10px; color: #6b6660; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 4px; }
        .rev-stat-value { font-family: 'Fraunces', Georgia, serif; font-size: 24px; font-weight: 700; color: #c8ff00; line-height: 1; }
        .rev-expand { cursor: pointer; transition: background 0.15s; }
        .rev-expand:hover { background: #111318; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th { font-size: 10px; letter-spacing: 1px; text-transform: uppercase; color: #6b6660; text-align: left; padding: 6px 10px; border-bottom: 1px solid #1a1c22; }
        td { padding: 8px 10px; border-bottom: 1px solid #1a1c22; vertical-align: top; color: #c2bdb4; }
        tr:last-child td { border-bottom: none; }
        .flow { display: flex; align-items: center; gap: 0; flex-wrap: wrap; margin: 16px 0; }
        .flow-step { background: #111318; border: 1px solid #1a1c22; border-radius: 4px; padding: 8px 12px; font-size: 11px; }
        .flow-arrow { color: #c8ff00; font-size: 14px; padding: 0 5px; }
        .checklist { list-style: none; padding: 0; }
        .checklist li { padding: 4px 0 4px 18px; position: relative; font-size: 12px; line-height: 1.6; }
        .checklist li::before { content: '>'; position: absolute; left: 2px; color: #c8ff00; font-weight: 700; }
        .rating-bar { height: 6px; background: #1a1c22; border-radius: 3px; margin-top: 6px; overflow: hidden; }
        .rating-fill { height: 100%; border-radius: 3px; }
        @media (max-width: 600px) { .rev-grid { grid-template-columns: 1fr 1fr; } }
      `}</style>

      <div style={{ padding: "32px 20px 24px", borderBottom: "1px solid #1a1c22", position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", top: -80, right: -80, width: 300, height: 300, background: "radial-gradient(circle, #c8ff0018, transparent 70%)", pointerEvents: "none" }} />
        <div style={{ maxWidth: 860, margin: "0 auto" }}>
          <div className="rev-tag">AUTOM8 LLC // Domain Acquisition Sprint</div>
          <h1 className="rev-h1">Project <em>REVENANT</em></h1>
          <div style={{ marginTop: 8, fontSize: 11, color: "#6b6660" }}>
            5-Agent Expired Domain Hunter // 4 Sprints // 8 Weeks // Target: AI Dev Tools Niche
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 860, margin: "0 auto", padding: "0 20px" }}>
        <div className="rev-nav">
          {tabs.map(t => (
            <button key={t.id} className={activeTab === t.id ? "active" : ""} onClick={() => setActiveTab(t.id)}>{t.label}</button>
          ))}
        </div>

        {activeTab === "overview" && (
          <div>
            <h2 className="rev-h2">Mission brief</h2>
            <div className="rev-grid">
              <div className="rev-stat"><div className="rev-stat-label">Agents</div><div className="rev-stat-value">5</div></div>
              <div className="rev-stat"><div className="rev-stat-label">Sprints</div><div className="rev-stat-value">4</div></div>
              <div className="rev-stat"><div className="rev-stat-label">Duration</div><div className="rev-stat-value">8 wk</div></div>
              <div className="rev-stat"><div className="rev-stat-label">Monthly cost</div><div className="rev-stat-value">${totalMonthly}</div></div>
              <div className="rev-stat"><div className="rev-stat-label">Daily scan</div><div className="rev-stat-value">10K+</div></div>
              <div className="rev-stat"><div className="rev-stat-label">Daily output</div><div className="rev-stat-value">1-5</div></div>
              <div className="rev-stat"><div className="rev-stat-label">Target niche</div><div className="rev-stat-value" style={{ fontSize: 14 }}>AI Dev</div></div>
              <div className="rev-stat"><div className="rev-stat-label">Free APIs used</div><div className="rev-stat-value">9/14</div></div>
            </div>

            <div className="rev-card rev-card-accent">
              <p style={{ fontSize: 13, lineHeight: 1.7 }}>
                <strong style={{ color: "#eae6df" }}>REVENANT</strong> is a 5-agent autonomous pipeline that scans 10,000+ expired domains daily, filters them through 7 automated gates, and delivers 1-5 acquisition-ready domains per week — scored against your exact masterplan criteria and optimized for the AI dev tools niche where Kimi, Cursor, Claude Code, Qwen, and Codex dominate search volume.
              </p>
            </div>

            <h3 className="rev-h3">Pipeline flow</h3>
            <div className="flow">
              <div className="flow-step" style={{ borderColor: "#c8ff00" }}>🔭 SCOUT<br /><span style={{ color: "#6b6660" }}>10K+ raw/day</span></div>
              <div className="flow-arrow">→</div>
              <div className="flow-step" style={{ borderColor: "#00cc88" }}>🛡️ SENTINEL<br /><span style={{ color: "#6b6660" }}>200-500 → 20-60</span></div>
              <div className="flow-arrow">→</div>
              <div className="flow-step" style={{ borderColor: "#85B7EB" }}>📜 ARCHIVIST<br /><span style={{ color: "#6b6660" }}>20-60 → 5-15</span></div>
              <div className="flow-arrow">→</div>
              <div className="flow-step" style={{ borderColor: "#AFA9EC" }}>👻 SPECTRE<br /><span style={{ color: "#6b6660" }}>5-15 → 1-5</span></div>
              <div className="flow-arrow">→</div>
              <div className="flow-step" style={{ borderColor: "#F0997B" }}>🔮 ORACLE<br /><span style={{ color: "#6b6660" }}>Buy / Pass</span></div>
            </div>

            <h3 className="rev-h3">Why these target models matter</h3>
            <div className="rev-card">
              <p style={{ fontSize: 12, lineHeight: 1.7, marginBottom: 10 }}>
                Every domain we hunt needs to rank for keywords around the hottest AI coding tools. A domain that once covered "dev tools" or "code editors" has backlinks and topical authority that transfer directly to covering these models:
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {["Claude Code", "Cursor", "Kimi (Moonshot)", "Qwen Coder", "Codex", "Copilot", "Windsurf", "Cline", "Aider", "Gemini Code Assist", "Continue.dev", "v0 by Vercel", "Bolt.new"].map(m => (
                  <span key={m} className="rev-metric">{m}</span>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === "agents" && (
          <div>
            <h2 className="rev-h2">The 5 agents</h2>
            {AGENTS.map(a => (
              <div key={a.id} className="rev-card rev-expand" style={{ borderLeft: `3px solid ${a.color}` }} onClick={() => setExpandedAgent(expandedAgent === a.id ? null : a.id)}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                  <div>
                    <span style={{ fontSize: 16, marginRight: 6 }}>{a.icon}</span>
                    <strong style={{ color: "#eae6df", fontSize: 14 }}>{a.name}</strong>
                    <span style={{ color: "#6b6660", fontSize: 12, marginLeft: 8 }}>{a.role}</span>
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <span className="rev-badge" style={{ background: "#c8ff0018", color: "#c8ff00" }}>Sprint {a.sprint}</span>
                    <span className="rev-badge" style={{ background: `${a.color}18`, color: a.color }}>{a.cost}</span>
                  </div>
                </div>
                <p style={{ fontSize: 12, lineHeight: 1.6, color: "#9c9890" }}>{a.description}</p>

                {expandedAgent === a.id && (
                  <div style={{ marginTop: 14, borderTop: `1px solid #1a1c22`, paddingTop: 14 }}>
                    <h3 className="rev-h3" style={{ marginTop: 0 }}>APIs used</h3>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 12 }}>
                      {a.apis.map(api => <span key={api} className="rev-metric">{api}</span>)}
                    </div>

                    <h3 className="rev-h3">Inputs</h3>
                    <ul className="checklist">{a.inputs.map((inp, i) => <li key={i}>{inp}</li>)}</ul>

                    <h3 className="rev-h3">Outputs</h3>
                    <ul className="checklist">{a.outputs.map((out, i) => <li key={i}>{out}</li>)}</ul>

                    <h3 className="rev-h3">Acceptance criteria</h3>
                    <ul className="checklist">{a.acceptanceCriteria.map((ac, i) => <li key={i}>{ac}</li>)}</ul>

                    <h3 className="rev-h3">Tech stack</h3>
                    <p style={{ fontSize: 11, color: "#6b6660", fontStyle: "italic" }}>{a.techStack}</p>

                    <div style={{ marginTop: 12, fontSize: 11, color: "#6b6660" }}>{a.priority}</div>
                  </div>
                )}
                <div style={{ textAlign: "right", fontSize: 10, color: "#6b6660", marginTop: 4 }}>
                  {expandedAgent === a.id ? "▲ collapse" : "▼ expand details"}
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === "sprints" && (
          <div>
            <h2 className="rev-h2">Sprint roadmap — 8 weeks</h2>
            {SPRINTS.map(s => (
              <div key={s.number} className="rev-card rev-expand" onClick={() => setExpandedSprint(expandedSprint === s.number ? null : s.number)}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                  <div>
                    <span className="rev-badge" style={{ background: "#c8ff0018", color: "#c8ff00", marginRight: 8 }}>Sprint {s.number}</span>
                    <strong style={{ color: "#eae6df", fontSize: 14 }}>{s.name}</strong>
                    <span style={{ color: "#6b6660", fontSize: 11, marginLeft: 8 }}>{s.duration}</span>
                  </div>
                </div>
                <p style={{ fontSize: 12, color: "#9c9890", marginBottom: 6 }}>{s.goal}</p>
                <div style={{ fontSize: 11, color: "#00cc88" }}>✓ Milestone: {s.milestone}</div>

                {expandedSprint === s.number && (
                  <div style={{ marginTop: 14, borderTop: "1px solid #1a1c22", paddingTop: 14 }}>
                    <table>
                      <thead>
                        <tr><th>Task</th><th>Effort</th><th>Owner</th></tr>
                      </thead>
                      <tbody>
                        {s.tasks.map((t, i) => (
                          <tr key={i}>
                            <td>{t.task}</td>
                            <td><span className="rev-metric">{t.effort}</span></td>
                            <td style={{ color: "#6b6660" }}>{t.owner}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div style={{ marginTop: 12, fontSize: 11, padding: "8px 12px", background: "#ffaa0012", borderLeft: "3px solid #ffaa00", borderRadius: 4 }}>
                      <strong style={{ color: "#ffaa00" }}>Risk:</strong> <span style={{ color: "#9c9890" }}>{s.risk}</span>
                    </div>
                    <div style={{ marginTop: 8, fontSize: 11, color: "#6b6660" }}>
                      Total effort: {s.tasks.reduce((sum, t) => sum + parseInt(t.effort), 0)}h estimated
                    </div>
                  </div>
                )}
                <div style={{ textAlign: "right", fontSize: 10, color: "#6b6660", marginTop: 4 }}>
                  {expandedSprint === s.number ? "▲ collapse" : "▼ expand tasks"}
                </div>
              </div>
            ))}

            <div className="rev-card" style={{ borderLeft: "3px solid #c8ff00", marginTop: 16 }}>
              <h3 className="rev-h3" style={{ marginTop: 0 }}>Total development effort</h3>
              <div className="rev-grid" style={{ marginTop: 8 }}>
                <div className="rev-stat"><div className="rev-stat-label">Sprint 1</div><div className="rev-stat-value" style={{ fontSize: 18 }}>52h</div></div>
                <div className="rev-stat"><div className="rev-stat-label">Sprint 2</div><div className="rev-stat-value" style={{ fontSize: 18 }}>44h</div></div>
                <div className="rev-stat"><div className="rev-stat-label">Sprint 3</div><div className="rev-stat-value" style={{ fontSize: 18 }}>41h</div></div>
                <div className="rev-stat"><div className="rev-stat-label">Sprint 4</div><div className="rev-stat-value" style={{ fontSize: 18 }}>29h</div></div>
              </div>
              <p style={{ fontSize: 12, color: "#6b6660", marginTop: 4 }}>~166 total dev hours across 8 weeks = ~21h/week average. Solo-buildable with focused sprints.</p>
            </div>
          </div>
        )}

        {activeTab === "niche" && (
          <div>
            <h2 className="rev-h2">Niche keyword targeting matrix</h2>
            <div className="rev-card rev-card-accent">
              <p style={{ fontSize: 12, lineHeight: 1.7 }}>
                SPECTRE uses this matrix to score domain relevance. A domain that previously covered any of these terms in its content or has backlinks from pages containing these terms gets a higher niche relevance score. <strong style={{ color: "#eae6df" }}>Tier 1 terms are weighted 4×</strong> because these are the exact models your masterplan targets for the dev tools authority site.
              </p>
            </div>
            {Object.entries(NICHE_KEYWORDS).map(([tier, keywords]) => (
              <div key={tier} style={{ marginBottom: 16 }}>
                <h3 className="rev-h3">{tier}</h3>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                  {keywords.map(k => (
                    <span key={k} className="rev-badge" style={{
                      background: tier.includes("1") ? "#c8ff0018" : tier.includes("2") ? "#00cc8818" : tier.includes("3") ? "#85B7EB18" : "#AFA9EC18",
                      color: tier.includes("1") ? "#c8ff00" : tier.includes("2") ? "#00cc88" : tier.includes("3") ? "#85B7EB" : "#AFA9EC",
                      fontSize: 11, padding: "4px 10px"
                    }}>{k}</span>
                  ))}
                </div>
              </div>
            ))}

            <h3 className="rev-h3">Ideal domain profiles</h3>
            <div className="rev-card">
              <ul className="checklist">
                <li><strong style={{ color: "#eae6df" }}>Dream domain:</strong> Was a dev tools comparison blog (e.g. "bestcodetools.com") with 3+ years of consistent tech content, DR 35-50, 300+ referring domains from GitHub repos and dev blogs</li>
                <li><strong style={{ color: "#eae6df" }}>Strong match:</strong> Was a software review site, IDE plugin directory, or programming tutorial hub. Backlinks from tech publications.</li>
                <li><strong style={{ color: "#eae6df" }}>Acceptable:</strong> General tech blog, SaaS tool site, or developer portfolio with good metrics. Content can be pivoted to AI dev tools.</li>
                <li><strong style={{ color: "#eae6df" }}>Pass:</strong> Non-tech domain regardless of metrics. E-commerce, health, finance, news — the topical gap is too wide for authority transfer.</li>
              </ul>
            </div>

            <h3 className="rev-h3">Why these models = money</h3>
            <div className="rev-card">
              <table>
                <thead><tr><th>Model/Tool</th><th>Why it matters</th><th>Keyword velocity</th></tr></thead>
                <tbody>
                  <tr><td style={{ color: "#eae6df" }}>Cursor</td><td>$2B+ ARR, fastest-growing IDE. Every comparison keyword has volume.</td><td><span className="rev-metric">Explosive</span></td></tr>
                  <tr><td style={{ color: "#eae6df" }}>Claude Code</td><td>Your proven niche (CCG: 498 clicks, 2 sales in 23 days). 6× growth in 12mo.</td><td><span className="rev-metric">Explosive</span></td></tr>
                  <tr><td style={{ color: "#eae6df" }}>Kimi (Moonshot)</td><td>Dominant in Asia, expanding globally. Underserved in English-language SEO.</td><td><span className="rev-metric">High growth</span></td></tr>
                  <tr><td style={{ color: "#eae6df" }}>Qwen Coder</td><td>Alibaba's push into dev tools. Massive model releases creating new keywords weekly.</td><td><span className="rev-metric">High growth</span></td></tr>
                  <tr><td style={{ color: "#eae6df" }}>Codex / Copilot</td><td>Incumbent. Massive search volume. Comparison keywords are the gateway.</td><td><span className="rev-metric">Steady high</span></td></tr>
                  <tr><td style={{ color: "#eae6df" }}>Windsurf / Cline</td><td>Rising challengers. Early keyword coverage = first-mover advantage.</td><td><span className="rev-metric">Emerging</span></td></tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === "budget" && (
          <div>
            <h2 className="rev-h2">Monthly operating budget</h2>
            <div className="rev-grid" style={{ marginBottom: 16 }}>
              <div className="rev-stat"><div className="rev-stat-label">Monthly total</div><div className="rev-stat-value">${totalMonthly}</div></div>
              <div className="rev-stat"><div className="rev-stat-label">Annual</div><div className="rev-stat-value">${totalMonthly * 12}</div></div>
              <div className="rev-stat"><div className="rev-stat-label">Free APIs</div><div className="rev-stat-value">9</div></div>
              <div className="rev-stat"><div className="rev-stat-label">Domain budget</div><div className="rev-stat-value" style={{ fontSize: 16 }}>$500-2K</div></div>
            </div>
            <table>
              <thead><tr><th>Service</th><th>Monthly</th><th>Notes</th></tr></thead>
              <tbody>
                {BUDGET.map((b, i) => (
                  <tr key={i}>
                    <td style={{ color: "#eae6df" }}>{b.item}</td>
                    <td>{b.monthly === 0 ? <span style={{ color: "#00cc88" }}>FREE</span> : <span className="rev-metric">${b.monthly}</span>}</td>
                    <td style={{ color: "#6b6660", fontSize: 11 }}>{b.note}</td>
                  </tr>
                ))}
                <tr style={{ borderTop: "2px solid #c8ff00" }}>
                  <td style={{ color: "#c8ff00", fontWeight: 500 }}>TOTAL</td>
                  <td><span className="rev-metric">${totalMonthly}/mo</span></td>
                  <td style={{ color: "#6b6660", fontSize: 11 }}>Within your masterplan's $130-190/mo operating budget</td>
                </tr>
              </tbody>
            </table>

            <div className="rev-card" style={{ marginTop: 16, borderLeft: "3px solid #00cc88" }}>
              <h3 className="rev-h3" style={{ marginTop: 0 }}>Budget fits your masterplan</h3>
              <p style={{ fontSize: 12, lineHeight: 1.7 }}>Your masterplan budgets $130-190/mo for all operations. REVENANT's $112/mo pipeline leaves $18-78/mo headroom for your content generation costs (DeepSeek drafts + Claude QA). The domain acquisition budget ($500-2000) is a one-time Phase 0 expense, exactly as planned.</p>
            </div>
          </div>
        )}

        {activeTab === "rating" && (
          <div>
            <h2 className="rev-h2">Self-rating: Project REVENANT</h2>
            <div className="rev-card" style={{ borderLeft: "3px solid #c8ff00", textAlign: "center", padding: 24 }}>
              <div style={{ fontFamily: "'Fraunces', serif", fontSize: 56, fontWeight: 700, color: "#c8ff00", lineHeight: 1 }}>8.7</div>
              <div style={{ fontSize: 12, color: "#6b6660", marginTop: 4 }}>out of 10</div>
            </div>

            {[
              { label: "Comprehensiveness", score: 9.2, color: "#00cc88", note: "14 APIs mapped, 5 agents with full acceptance criteria, 4 sprints with task-level decomposition, budget to the dollar" },
              { label: "Execution readiness", score: 8.5, color: "#00cc88", note: "A PM can hand this to a dev today. Every task has effort estimate, owner, and dependencies. Acceptance criteria are testable." },
              { label: "Niche targeting", score: 9.0, color: "#00cc88", note: "4-tier keyword matrix covering every major AI coding tool. SPECTRE agent is the differentiator nobody else runs." },
              { label: "Budget realism", score: 9.5, color: "#00cc88", note: "$112/mo fits inside your masterplan's operating budget. 9 of 14 APIs are free. No surprise costs." },
              { label: "Risk coverage", score: 8.0, color: "#c8ff00", note: "Each sprint has identified risks. Missing: no explicit rollback plan if an API goes down mid-pipeline. Need monitoring." },
              { label: "Time estimate accuracy", score: 7.5, color: "#ffaa00", note: "166 dev hours is aggressive for a solo builder. Integration complexity often underestimated. Honest risk: could be 200+ hours." },
              { label: "Scalability", score: 8.0, color: "#c8ff00", note: "SQLite → Postgres path planned. But multi-niche expansion (beyond dev tools) would need SPECTRE matrix refactoring." },
              { label: "Missing pieces", score: 8.0, color: "#c8ff00", note: "No monitoring/alerting stack defined. No data backup strategy. No load testing plan for API rate limits at scale." }
            ].map(r => (
              <div key={r.label} className="rev-card" style={{ padding: "12px 16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                  <span style={{ fontSize: 13, color: "#eae6df" }}>{r.label}</span>
                  <span style={{ fontFamily: "'Fraunces', serif", fontSize: 18, fontWeight: 700, color: r.color }}>{r.score}</span>
                </div>
                <div className="rating-bar"><div className="rating-fill" style={{ width: `${r.score * 10}%`, background: r.color }} /></div>
                <p style={{ fontSize: 11, color: "#6b6660", marginTop: 6 }}>{r.note}</p>
              </div>
            ))}

            <div className="rev-card rev-card-accent" style={{ marginTop: 16 }}>
              <h3 className="rev-h3" style={{ marginTop: 0 }}>What takes this to a 9.5+</h3>
              <ul className="checklist">
                <li>Add monitoring stack (Uptime Kuma + PagerDuty/Slack alerts for pipeline failures)</li>
                <li>Add data backup strategy (daily SQLite export to S3/Backblaze B2)</li>
                <li>Add API fallback chains (if Moz is down → fall back to SEMrush Apify scraper)</li>
                <li>Add A/B scoring: run two ORACLE weight configs in parallel, compare predictions vs actual acquisition outcomes</li>
                <li>Add portfolio tracker: post-acquisition monitoring of domain performance in GSC</li>
                <li>Validate time estimates with a 2-day spike before committing to Sprint 1</li>
              </ul>
            </div>
          </div>
        )}

        <div style={{ padding: "24px 0", borderTop: "1px solid #1a1c22", marginTop: 24, fontSize: 10, color: "#6b6660", textAlign: "center" }}>
          PROJECT REVENANT // AUTOM8 LLC // {new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
        </div>
      </div>
    </div>
  );
}

export default App;
