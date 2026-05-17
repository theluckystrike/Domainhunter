#!/usr/bin/env python3
"""
Generate for-sale landing pages from template.

Usage:
    python3 scripts/deploy_landing_page.py --domain viryd.com --price 2500 --dan-url "https://dan.com/buy-domain/viryd.com"
    python3 scripts/deploy_landing_page.py --deploy-all
"""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple


# --- Domain catalog (immutable) ---

class DomainEntry(NamedTuple):
    """Single domain listing configuration."""
    domain: str
    price: int
    dan_url: str


DOMAIN_CATALOG: tuple[DomainEntry, ...] = (
    DomainEntry("viryd.com", 2500, "https://dan.com/buy-domain/viryd.com"),
    DomainEntry("neovistainc.com", 1500, "https://dan.com/buy-domain/neovistainc.com"),
    DomainEntry("pictureeditor.net", 500, "https://dan.com/buy-domain/pictureeditor.net"),
    DomainEntry("recipetool.net", 300, "https://dan.com/buy-domain/recipetool.net"),
)

DEFAULT_CONTACT_EMAIL = "domains@zovo.one"


# --- Pure functions ---

def format_price(price: int) -> str:
    """Format integer price with comma separators."""
    assert isinstance(price, int), f"price must be int, got {type(price)}"
    assert price >= 0, f"price must be non-negative, got {price}"
    return f"{price:,}"


def render_template(template: str, domain: str, price: int,
                    dan_url: str, contact_email: str) -> str:
    """Replace all template variables and return final HTML."""
    assert "{{DOMAIN}}" in template, "template missing {{DOMAIN}} variable"
    assert len(domain) > 0, "domain must not be empty"

    result = template
    result = result.replace("{{DOMAIN}}", domain)
    result = result.replace("{{PRICE}}", str(price))
    result = result.replace("{{PRICE_FORMATTED}}", format_price(price))
    result = result.replace("{{DAN_URL}}", dan_url)
    result = result.replace("{{CONTACT_EMAIL}}", contact_email)

    return result


def load_template(template_path: Path) -> str:
    """Read the HTML template file from disk."""
    assert template_path.exists(), f"template not found: {template_path}"
    assert template_path.suffix == ".html", f"template must be .html: {template_path}"

    content = template_path.read_text(encoding="utf-8")
    return content


def write_generated_page(output_dir: Path, domain: str, html: str) -> Path:
    """Write generated HTML to output_dir/{domain}/index.html."""
    assert len(html) > 0, "html content must not be empty"
    assert len(domain) > 0, "domain must not be empty"

    domain_dir = output_dir / domain
    domain_dir.mkdir(parents=True, exist_ok=True)

    out_path = domain_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")

    return out_path


def generate_single(template: str, domain: str, price: int,
                    dan_url: str, contact_email: str,
                    output_dir: Path) -> dict:
    """Generate a single landing page. Returns result metadata."""
    assert len(domain) > 0, "domain must not be empty"
    assert price > 0, "price must be positive"

    html = render_template(template, domain, price, dan_url, contact_email)
    out_path = write_generated_page(output_dir, domain, html)

    size_bytes = len(html.encode("utf-8"))
    return {
        "domain": domain,
        "price": price,
        "dan_url": dan_url,
        "path": str(out_path),
        "size_kb": round(size_bytes / 1024, 1),
    }


def print_summary_table(results: list[dict]) -> None:
    """Print a formatted summary table of generated pages."""
    assert isinstance(results, list), "results must be a list"
    assert len(results) > 0, "results must not be empty"

    col_domain = max(len(r["domain"]) for r in results)
    col_domain = max(col_domain, 6)  # min header width

    header = (
        f"  {'Domain':<{col_domain}}  {'Price':>8}  {'Size':>6}  Path"
    )
    sep = "  " + "-" * (col_domain + 8 + 6 + 40)

    print()
    print(header)
    print(sep)

    for r in results:
        price_str = f"${format_price(r['price'])}"
        size_str = f"{r['size_kb']}KB"
        print(f"  {r['domain']:<{col_domain}}  {price_str:>8}  {size_str:>6}  {r['path']}")

    print(sep)
    print(f"  {len(results)} page(s) generated.")
    print()


def build_arg_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate for-sale landing pages from template"
    )

    parser.add_argument(
        "--domain",
        help="Domain name (e.g. viryd.com)",
    )
    parser.add_argument(
        "--price",
        type=int,
        help="Price in USD (e.g. 2500)",
    )
    parser.add_argument(
        "--dan-url",
        help="Dan.com listing URL",
    )
    parser.add_argument(
        "--contact-email",
        default=DEFAULT_CONTACT_EMAIL,
        help=f"Contact email (default: {DEFAULT_CONTACT_EMAIL})",
    )
    parser.add_argument(
        "--deploy-all",
        action="store_true",
        help="Generate pages for all domains in catalog",
    )
    parser.add_argument(
        "--template",
        default=None,
        help="Path to HTML template (default: templates/for-sale/index.html)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: templates/for-sale/generated/)",
    )

    return parser


def validate_args(args: argparse.Namespace) -> bool:
    """Validate CLI arguments, print errors, return True if valid."""
    assert args is not None, "args must not be None"

    if not args.deploy_all and not args.domain:
        print("ERROR: Provide --domain or --deploy-all")
        return False

    if args.domain and not args.deploy_all:
        if not args.price:
            print("ERROR: --price is required with --domain")
            return False
        if not args.dan_url:
            # Auto-generate Dan URL from domain
            args.dan_url = f"https://dan.com/buy-domain/{args.domain}"

    return True


def run(args: argparse.Namespace) -> int:
    """Execute the generation pipeline. Returns exit code."""
    assert args is not None, "args must not be None"

    project_root = Path(__file__).resolve().parent.parent

    # Resolve template path
    if args.template:
        template_path = Path(args.template)
    else:
        template_path = project_root / "templates" / "for-sale" / "index.html"

    # Resolve output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = project_root / "templates" / "for-sale" / "generated"

    # Load template
    template = load_template(template_path)

    print(f"Template: {template_path}")
    print(f"Output:   {output_dir}")
    print(f"Contact:  {args.contact_email}")

    # Build entries list
    entries: list[DomainEntry] = []
    if args.deploy_all:
        entries = list(DOMAIN_CATALOG)
        print(f"Mode:     deploy-all ({len(entries)} domains)")
    else:
        entry = DomainEntry(args.domain, args.price, args.dan_url)
        entries = [entry]
        print(f"Mode:     single ({args.domain})")

    # Generate all pages
    results: list[dict] = []
    for entry in entries:
        result = generate_single(
            template=template,
            domain=entry.domain,
            price=entry.price,
            dan_url=entry.dan_url,
            contact_email=args.contact_email,
            output_dir=output_dir,
        )
        results.append(result)

    # Print summary
    print_summary_table(results)

    return 0


def main() -> None:
    """Entry point: parse args, validate, run."""
    parser = build_arg_parser()
    args = parser.parse_args()

    if not validate_args(args):
        parser.print_help()
        sys.exit(1)

    exit_code = run(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
