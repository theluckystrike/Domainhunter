"""Sprint Plan Generator — Domain Hunter REVENANT operations.

Generates structured sprint plans from templates for automated pipeline
execution. Each plan is a frozen, immutable sequence of verified steps.

NASA Power of 10 rules enforced:
  - All functions < 60 lines
  - 2+ assertions per function
  - No global mutable state
  - Fixed loop bounds (max iterations explicit)
  - frozen=True on all dataclasses
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

_MAX_STEPS_PER_PLAN: int = 20
_MAX_CRITERIA_PER_PLAN: int = 15
_MAX_DOMAINS_WATCHLIST: int = 100


@dataclass(frozen=True)
class SprintStep:
    """Single atomic step within a sprint plan."""

    number: int
    name: str
    do: str
    tool: str
    input_desc: str
    output_desc: str
    verify: str
    on_fail: str

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        assert isinstance(self.number, int) and self.number > 0, (
            f"step number must be positive int, got {self.number}"
        )
        assert isinstance(self.name, str) and len(self.name) > 0, (
            "step name must be non-empty string"
        )
        assert isinstance(self.do, str) and len(self.do) > 0, (
            "step 'do' must be non-empty string"
        )
        assert isinstance(self.tool, str) and len(self.tool) > 0, (
            "step tool must be non-empty string"
        )
        assert self.on_fail in ("retry", "fallback", "blocks"), (
            f"on_fail must be retry|fallback|blocks, got {self.on_fail}"
        )


@dataclass(frozen=True)
class SprintPlan:
    """Complete sprint plan with budgets and success criteria."""

    number: int
    slug: str
    objective: str
    leverage_score: int
    depends_on: str
    steps: tuple[SprintStep, ...]
    success_criteria: tuple[str, ...]
    budget_steps: int
    budget_tool_calls: int
    budget_timeout_min: int

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        assert isinstance(self.number, int) and self.number > 0, (
            f"plan number must be positive int, got {self.number}"
        )
        assert isinstance(self.slug, str) and len(self.slug) > 0, (
            "slug must be non-empty string"
        )
        assert 1 <= self.leverage_score <= 10, (
            f"leverage_score must be 1-10, got {self.leverage_score}"
        )
        assert 0 < len(self.steps) <= _MAX_STEPS_PER_PLAN, (
            f"steps count must be 1-{_MAX_STEPS_PER_PLAN}, got {len(self.steps)}"
        )
        assert 0 < len(self.success_criteria) <= _MAX_CRITERIA_PER_PLAN, (
            f"criteria count must be 1-{_MAX_CRITERIA_PER_PLAN}, got {len(self.success_criteria)}"
        )
        assert self.budget_steps > 0, "budget_steps must be positive"
        assert self.budget_tool_calls > 0, "budget_tool_calls must be positive"
        assert self.budget_timeout_min > 0, "budget_timeout_min must be positive"


# ---------------------------------------------------------------------------
# Plan Templates
# ---------------------------------------------------------------------------


def plan_domain_scan() -> SprintPlan:
    """Generate plan for daily domain pipeline scan.

    Runs the full SCOUT->SENTINEL->ARCHIVIST->SPECTRE->ORACLE chain.
    """
    steps = (
        SprintStep(
            number=1,
            name="Source expired domains",
            do="Query WhoisFreaks + CatchDoms for newly expired/dropping domains",
            tool="python -m main --from-stage scout",
            input_desc=".env API keys (WHOISFREAKS_API_KEY, CATCHDOMS_API_KEY)",
            output_desc="data/candidates_raw.json with DomainCandidate objects",
            verify="test -s data/candidates_raw.json && python -c \"import json; d=json.load(open('data/candidates_raw.json')); assert len(d)>0\"",
            on_fail="retry",
        ),
        SprintStep(
            number=2,
            name="Score domain metrics",
            do="Run SENTINEL to fetch DA/DR/traffic from DataForSEO",
            tool="python -m main --from-stage sentinel",
            input_desc="data/candidates_raw.json",
            output_desc="data/scored_domains.json with ScoredDomain objects",
            verify="test -s data/scored_domains.json",
            on_fail="retry",
        ),
        SprintStep(
            number=3,
            name="Archive historical content",
            do="Run ARCHIVIST to capture Wayback Machine snapshots",
            tool="python -m main --from-stage archivist",
            input_desc="data/scored_domains.json",
            output_desc="data/verified_domains.json with content analysis",
            verify="test -s data/verified_domains.json",
            on_fail="fallback",
        ),
        SprintStep(
            number=4,
            name="Social signal scan",
            do="Run SPECTRE to check GitHub/Reddit/social mentions",
            tool="python -m main --from-stage spectre",
            input_desc="data/verified_domains.json",
            output_desc="data/vetted_domains.json with social scores",
            verify="test -s data/vetted_domains.json",
            on_fail="fallback",
        ),
        SprintStep(
            number=5,
            name="Final verdict generation",
            do="Run ORACLE to produce buy/watch/skip verdicts via Claude",
            tool="python -m main --from-stage oracle",
            input_desc="data/vetted_domains.json",
            output_desc="data/verdicts.json with DomainVerdict objects",
            verify="test -s data/verdicts.json && python -c \"import json; d=json.load(open('data/verdicts.json')); assert len(d)>0\"",
            on_fail="blocks",
        ),
    )

    assert len(steps) == 5, "domain_scan must have exactly 5 steps"
    assert all(s.number == i + 1 for i, s in enumerate(steps)), "step numbers must be sequential"

    return SprintPlan(
        number=_next_sprint_number(),
        slug="domain-scan",
        objective="Run full 5-agent pipeline to discover and score expired domains",
        leverage_score=8,
        depends_on="none",
        steps=steps,
        success_criteria=(
            "At least 10 new candidates discovered",
            "All 5 pipeline stages complete without BLOCKS failure",
            "Verdicts file contains buy or watch recommendations",
            "Logs written to logs/ directory",
        ),
        budget_steps=5,
        budget_tool_calls=25,
        budget_timeout_min=30,
    )


def plan_tool_deploy(domain: str, tool_path: str) -> SprintPlan:
    """Generate plan to deploy a tool to Cloudflare Pages.

    Args:
        domain: Target domain (e.g. 'ingredientcalculator.com').
        tool_path: Relative path to tool directory (e.g. 'tools/ingredientcalculator').
    """
    assert isinstance(domain, str) and "." in domain, f"invalid domain: {domain}"
    assert isinstance(tool_path, str) and len(tool_path) > 0, "tool_path must be non-empty"

    project_name = domain.split(".")[0]

    steps = (
        SprintStep(
            number=1,
            name="Validate tool files",
            do=f"Check {tool_path}/index.html exists and passes HTML validation",
            tool=f"test -f {tool_path}/index.html && wc -l {tool_path}/index.html",
            input_desc=f"Tool directory at {tool_path}",
            output_desc="Confirmation that index.html exists with line count",
            verify=f"test -f {tool_path}/index.html",
            on_fail="blocks",
        ),
        SprintStep(
            number=2,
            name="Check deploy prerequisites",
            do="Verify wrangler is authenticated and project exists",
            tool="wrangler whoami && wrangler pages project list",
            input_desc="Wrangler CLI config (~/.wrangler/)",
            output_desc="Account ID and project list",
            verify="wrangler whoami | grep -q 'Account'",
            on_fail="blocks",
        ),
        SprintStep(
            number=3,
            name="Deploy to CF Pages",
            do=f"Push {tool_path} to Cloudflare Pages project {project_name}",
            tool=f"wrangler pages deploy {tool_path} --project-name={project_name}",
            input_desc=f"Static files in {tool_path}",
            output_desc="Deployment URL (*.pages.dev)",
            verify=f"curl -sI https://{project_name}.pages.dev | grep -q '200'",
            on_fail="retry",
        ),
        SprintStep(
            number=4,
            name="Verify custom domain",
            do=f"Confirm {domain} resolves to the Pages deployment",
            tool=f"curl -sI https://{domain} | head -5",
            input_desc=f"Custom domain: {domain}",
            output_desc="HTTP 200 response with CF headers",
            verify=f"curl -sI https://{domain} | grep -q '200'",
            on_fail="fallback",
        ),
        SprintStep(
            number=5,
            name="Submit to IndexNow",
            do=f"Ping IndexNow with https://{domain}/ to trigger crawl",
            tool=f"curl -s 'https://api.indexnow.org/indexnow?url=https://{domain}/&key=domainhunter'",
            input_desc=f"URL: https://{domain}/",
            output_desc="HTTP 200 from IndexNow API",
            verify=f"curl -so /dev/null -w '%{{http_code}}' 'https://api.indexnow.org/indexnow?url=https://{domain}/&key=domainhunter' | grep -q '200'",
            on_fail="fallback",
        ),
    )

    assert len(steps) == 5, "tool_deploy must have exactly 5 steps"
    assert all(s.number == i + 1 for i, s in enumerate(steps)), "step numbers sequential"

    return SprintPlan(
        number=_next_sprint_number(),
        slug=f"deploy-{project_name}",
        objective=f"Deploy tool to {domain} via Cloudflare Pages and verify live",
        leverage_score=7,
        depends_on="tool built and tested locally",
        steps=steps,
        success_criteria=(
            f"https://{domain}/ returns HTTP 200",
            "CF Pages deployment successful (no errors in wrangler output)",
            "IndexNow submission accepted",
        ),
        budget_steps=5,
        budget_tool_calls=15,
        budget_timeout_min=10,
    )


def plan_domain_acquire(domain: str, registrar: str, budget: float) -> SprintPlan:
    """Generate plan to acquire a specific domain.

    Args:
        domain: Domain to acquire (e.g. 'recipetool.net').
        registrar: Target registrar (e.g. 'cloudflare', 'namecheap').
        budget: Maximum spend in USD.
    """
    assert isinstance(domain, str) and "." in domain, f"invalid domain: {domain}"
    assert isinstance(registrar, str) and len(registrar) > 0, "registrar required"
    assert isinstance(budget, (int, float)) and budget > 0, f"budget must be positive, got {budget}"

    steps = (
        SprintStep(
            number=1,
            name="WHOIS availability check",
            do=f"Verify {domain} is available or in redemption/auction",
            tool=f"whois {domain} | grep -i 'status\\|expir\\|registrar'",
            input_desc=f"Domain: {domain}",
            output_desc="WHOIS status (available/pendingDelete/registered)",
            verify=f"whois {domain} | grep -iq 'no match\\|available\\|pendingDelete'",
            on_fail="blocks",
        ),
        SprintStep(
            number=2,
            name="Price check",
            do=f"Confirm registration cost at {registrar} is within ${budget:.2f} budget",
            tool=f"curl -s 'https://api.{registrar}.com/v1/domains/{domain}/check'",
            input_desc=f"Domain: {domain}, Registrar: {registrar}",
            output_desc="Price and availability status JSON",
            verify=f"echo 'manual: verify price <= ${budget:.2f}'",
            on_fail="fallback",
        ),
        SprintStep(
            number=3,
            name="Register domain",
            do=f"Register {domain} at {registrar} with auto-renew enabled",
            tool=f"curl -sX POST 'https://api.{registrar}.com/v1/domains' -d 'domain={domain}&auto_renew=true'",
            input_desc=f"API credentials for {registrar}, domain: {domain}",
            output_desc="Registration confirmation with expiry date",
            verify=f"whois {domain} | grep -iq 'registrant'",
            on_fail="blocks",
        ),
        SprintStep(
            number=4,
            name="Configure DNS",
            do=f"Point {domain} to Cloudflare Pages or parking page",
            tool=f"curl -sX POST 'https://api.cloudflare.com/client/v4/zones' -d 'name={domain}'",
            input_desc=f"CF API token, domain: {domain}",
            output_desc="Zone ID and nameservers",
            verify=f"dig +short NS {domain} | grep -q 'cloudflare'",
            on_fail="retry",
        ),
        SprintStep(
            number=5,
            name="Record acquisition",
            do=f"Log {domain} to portfolio database with cost and metadata",
            tool="python -c \"from storage.database import Database; db=Database(); db.record_acquisition(...)\"",
            input_desc=f"Domain: {domain}, cost: ${budget:.2f}, registrar: {registrar}",
            output_desc="Database row ID confirmation",
            verify="python -c \"from storage.database import Database; db=Database(); assert db.domain_exists('{domain}')\"".format(domain=domain),
            on_fail="retry",
        ),
    )

    assert len(steps) == 5, "domain_acquire must have exactly 5 steps"
    assert all(s.number == i + 1 for i, s in enumerate(steps)), "step numbers sequential"

    return SprintPlan(
        number=_next_sprint_number(),
        slug=f"acquire-{domain.replace('.', '-')}",
        objective=f"Register {domain} at {registrar} within ${budget:.2f} budget",
        leverage_score=9,
        depends_on="ORACLE verdict = BUY",
        steps=steps,
        success_criteria=(
            f"{domain} registered and WHOIS shows our registrant",
            f"Total cost <= ${budget:.2f}",
            "DNS configured (nameservers pointing to Cloudflare)",
            "Acquisition recorded in portfolio database",
        ),
        budget_steps=5,
        budget_tool_calls=12,
        budget_timeout_min=15,
    )


def plan_watchlist_check(domains: list[str]) -> SprintPlan:
    """Generate plan to check watchlist domain status changes.

    Args:
        domains: List of domains to monitor (max 100).
    """
    assert isinstance(domains, list) and len(domains) > 0, "domains list must be non-empty"
    assert len(domains) <= _MAX_DOMAINS_WATCHLIST, (
        f"max {_MAX_DOMAINS_WATCHLIST} domains per check, got {len(domains)}"
    )

    domain_count = len(domains)
    sample = ", ".join(domains[:3])
    suffix = f" (+{domain_count - 3} more)" if domain_count > 3 else ""

    steps = (
        SprintStep(
            number=1,
            name="Load watchlist",
            do=f"Load {domain_count} domains from watchlist for status check",
            tool="python scripts/watchlist_monitor.py --load",
            input_desc=f"Watchlist: {sample}{suffix}",
            output_desc="Loaded domain list with last-known statuses",
            verify="python scripts/watchlist_monitor.py --load --dry-run | grep -q 'loaded'",
            on_fail="blocks",
        ),
        SprintStep(
            number=2,
            name="Bulk WHOIS check",
            do=f"Query WHOIS for all {domain_count} domains to detect status changes",
            tool="python scripts/watchlist_monitor.py --check-whois",
            input_desc=f"{domain_count} domains",
            output_desc="Status map: domain -> (old_status, new_status)",
            verify="test -s data/watchlist_status.json",
            on_fail="retry",
        ),
        SprintStep(
            number=3,
            name="Detect drops and expirations",
            do="Compare current WHOIS to last known status, flag changes",
            tool="python scripts/watchlist_monitor.py --diff",
            input_desc="data/watchlist_status.json",
            output_desc="data/watchlist_changes.json with changed domains only",
            verify="python -c \"import json,pathlib; pathlib.Path('data/watchlist_changes.json').exists()\"",
            on_fail="fallback",
        ),
        SprintStep(
            number=4,
            name="Alert on actionable changes",
            do="Send notifications for domains that moved to pendingDelete/available",
            tool="python scripts/watchlist_monitor.py --notify",
            input_desc="data/watchlist_changes.json",
            output_desc="Notification sent count (Slack/email)",
            verify="echo 'notifications sent or no changes detected'",
            on_fail="fallback",
        ),
    )

    assert len(steps) == 4, "watchlist_check must have exactly 4 steps"
    assert all(s.number == i + 1 for i, s in enumerate(steps)), "step numbers sequential"

    return SprintPlan(
        number=_next_sprint_number(),
        slug="watchlist-check",
        objective=f"Monitor {domain_count} watchlist domains for status changes",
        leverage_score=6,
        depends_on="none",
        steps=steps,
        success_criteria=(
            f"All {domain_count} domains checked via WHOIS",
            "Status changes detected and logged",
            "Actionable changes (drops/expirations) trigger notifications",
        ),
        budget_steps=4,
        budget_tool_calls=10,
        budget_timeout_min=20,
    )


def plan_goldmine_integration(keyword_file: str) -> SprintPlan:
    """Generate plan to integrate new keyword goldmine data.

    Args:
        keyword_file: Path to keyword research CSV/JSON file.
    """
    assert isinstance(keyword_file, str) and len(keyword_file) > 0, (
        "keyword_file must be non-empty"
    )
    assert keyword_file.endswith((".csv", ".json")), (
        f"keyword_file must be .csv or .json, got: {keyword_file}"
    )

    steps = (
        SprintStep(
            number=1,
            name="Parse keyword file",
            do=f"Load and validate keyword data from {keyword_file}",
            tool=f"python -c \"import json; data=json.load(open('{keyword_file}')); print(len(data), 'keywords')\"" if keyword_file.endswith(".json") else f"wc -l {keyword_file}",
            input_desc=f"Keyword file: {keyword_file}",
            output_desc="Keyword count and sample data",
            verify=f"test -s {keyword_file}",
            on_fail="blocks",
        ),
        SprintStep(
            number=2,
            name="Extract domain candidates",
            do="Generate exact-match domain candidates from high-volume keywords",
            tool="python -m agents.scout --from-keywords " + keyword_file,
            input_desc=f"Keywords from {keyword_file}",
            output_desc="data/goldmine_candidates.json with domain suggestions",
            verify="test -s data/goldmine_candidates.json",
            on_fail="retry",
        ),
        SprintStep(
            number=3,
            name="Check availability",
            do="Bulk WHOIS check all generated domain candidates",
            tool="python scripts/watchlist_monitor.py --bulk-check data/goldmine_candidates.json",
            input_desc="data/goldmine_candidates.json",
            output_desc="data/goldmine_available.json (available domains only)",
            verify="test -s data/goldmine_available.json",
            on_fail="retry",
        ),
        SprintStep(
            number=4,
            name="Score and rank",
            do="Score available domains by keyword volume * domain quality",
            tool="python -m agents.sentinel --input data/goldmine_available.json --output data/goldmine_scored.json",
            input_desc="data/goldmine_available.json",
            output_desc="data/goldmine_scored.json ranked by composite score",
            verify="test -s data/goldmine_scored.json",
            on_fail="fallback",
        ),
        SprintStep(
            number=5,
            name="Merge into pipeline",
            do="Add top-scoring goldmine domains to main watchlist",
            tool="python scripts/watchlist_monitor.py --merge data/goldmine_scored.json",
            input_desc="data/goldmine_scored.json",
            output_desc="Updated watchlist with new goldmine entries",
            verify="python -c \"import json; w=json.load(open('data/watchlist.json')); assert len(w)>0\"",
            on_fail="retry",
        ),
    )

    assert len(steps) == 5, "goldmine_integration must have exactly 5 steps"
    assert all(s.number == i + 1 for i, s in enumerate(steps)), "step numbers sequential"

    return SprintPlan(
        number=_next_sprint_number(),
        slug="goldmine-integration",
        objective=f"Integrate keyword goldmine from {keyword_file} into domain pipeline",
        leverage_score=8,
        depends_on="keyword research completed",
        steps=steps,
        success_criteria=(
            f"Keyword file {keyword_file} parsed successfully",
            "Domain candidates generated from high-volume keywords",
            "Available domains scored and ranked",
            "Top candidates merged into watchlist",
        ),
        budget_steps=5,
        budget_tool_calls=20,
        budget_timeout_min=25,
    )


# ---------------------------------------------------------------------------
# Rendering & Output
# ---------------------------------------------------------------------------


def generate_sprint_markdown(plan: SprintPlan) -> str:
    """Render a SprintPlan to sprint-template markdown format.

    Args:
        plan: The SprintPlan to render.

    Returns:
        Formatted markdown string ready to write to file.
    """
    assert isinstance(plan, SprintPlan), "plan must be a SprintPlan instance"
    assert len(plan.steps) > 0, "plan must have at least one step"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = [
        f"# Sprint {plan.number} — {plan.slug}",
        "",
        f"**Generated:** {now}",
        f"**Objective:** {plan.objective}",
        f"**Leverage Score:** {plan.leverage_score}/10",
        f"**Depends On:** {plan.depends_on}",
        "",
        "## Budget",
        "",
        f"| Metric | Limit |",
        f"|--------|-------|",
        f"| Steps | {plan.budget_steps} |",
        f"| Tool Calls | {plan.budget_tool_calls} |",
        f"| Timeout | {plan.budget_timeout_min} min |",
        "",
        "## Steps",
        "",
    ]

    for step in plan.steps:
        assert step.number <= _MAX_STEPS_PER_PLAN, "step number exceeds max"
        lines.extend([
            f"### Step {step.number}: {step.name}",
            "",
            f"- **Do:** {step.do}",
            f"- **Tool:** `{step.tool}`",
            f"- **Input:** {step.input_desc}",
            f"- **Output:** {step.output_desc}",
            f"- **Verify:** `{step.verify}`",
            f"- **On Fail:** {step.on_fail}",
            "",
        ])

    lines.extend([
        "## Success Criteria",
        "",
    ])

    for idx, criterion in enumerate(plan.success_criteria):
        assert idx < _MAX_CRITERIA_PER_PLAN, "too many criteria"
        lines.append(f"- [ ] {criterion}")

    lines.append("")
    lines.append("---")
    lines.append(f"*Domain Hunter REVENANT — Sprint Planner v1.0*")
    lines.append("")

    return "\n".join(lines)


def save_sprint_plan(plan: SprintPlan, output_dir: Path) -> Path:
    """Write sprint plan to markdown file in output directory.

    Args:
        plan: The SprintPlan to save.
        output_dir: Directory to write the file into (created if missing).

    Returns:
        Path to the written file.
    """
    assert isinstance(plan, SprintPlan), "plan must be a SprintPlan instance"
    assert isinstance(output_dir, Path), "output_dir must be a Path"

    output_dir.mkdir(parents=True, exist_ok=True)
    assert output_dir.is_dir(), f"output_dir is not a directory: {output_dir}"

    filename = f"sprint-{plan.number}-{plan.slug}.md"
    filepath = output_dir / filename

    content = generate_sprint_markdown(plan)
    assert len(content) > 0, "generated markdown must not be empty"

    filepath.write_text(content, encoding="utf-8")
    assert filepath.exists(), f"failed to write file: {filepath}"

    return filepath


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

# Sprint counter — module-level constant seed, incremented via file state
_SPRINT_COUNTER_FILE: str = "data/.sprint_counter"


def _next_sprint_number() -> int:
    """Read and increment the sprint counter from persistent file.

    Returns:
        Next sprint number (starts at 1 if no file exists).
    """
    counter_path = Path(_SPRINT_COUNTER_FILE)

    if counter_path.exists():
        text = counter_path.read_text(encoding="utf-8").strip()
        assert text.isdigit(), f"corrupt sprint counter: {text}"
        current = int(text)
    else:
        current = 0

    next_num = current + 1
    assert next_num > 0, "sprint number overflow"
    assert next_num < 10000, "sprint number exceeds reasonable bound"

    counter_path.parent.mkdir(parents=True, exist_ok=True)
    counter_path.write_text(str(next_num), encoding="utf-8")

    return next_num


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for generating sprint plans.

    Usage:
        python sprint_planner.py domain-scan
        python sprint_planner.py tool-deploy ingredientcalculator.com tools/ingredientcalculator
        python sprint_planner.py acquire recipetool.net cloudflare 12.00
        python sprint_planner.py watchlist domain1.com domain2.com domain3.com
        python sprint_planner.py goldmine data/keywords.json
    """
    import sys

    assert len(sys.argv) >= 2, (
        "Usage: python sprint_planner.py <command> [args...]\n"
        "Commands: domain-scan, tool-deploy, acquire, watchlist, goldmine"
    )

    command = sys.argv[1]
    output_dir = Path("data/sprint-plans")

    if command == "domain-scan":
        plan = plan_domain_scan()
    elif command == "tool-deploy":
        assert len(sys.argv) >= 4, "Usage: tool-deploy <domain> <tool_path>"
        plan = plan_tool_deploy(domain=sys.argv[2], tool_path=sys.argv[3])
    elif command == "acquire":
        assert len(sys.argv) >= 5, "Usage: acquire <domain> <registrar> <budget>"
        plan = plan_domain_acquire(
            domain=sys.argv[2],
            registrar=sys.argv[3],
            budget=float(sys.argv[4]),
        )
    elif command == "watchlist":
        assert len(sys.argv) >= 3, "Usage: watchlist <domain1> [domain2] ..."
        plan = plan_watchlist_check(domains=sys.argv[2:])
    elif command == "goldmine":
        assert len(sys.argv) >= 3, "Usage: goldmine <keyword_file>"
        plan = plan_goldmine_integration(keyword_file=sys.argv[2])
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)

    filepath = save_sprint_plan(plan, output_dir)
    print(f"Sprint plan saved: {filepath}")
    print(generate_sprint_markdown(plan))


if __name__ == "__main__":
    main()
