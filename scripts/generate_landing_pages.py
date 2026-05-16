#!/usr/bin/env python3
"""
Generate domain-for-sale landing pages from template + config.

Usage:
    python scripts/generate_landing_pages.py
    python scripts/generate_landing_pages.py --config path/to/config.json --template path/to/template.html
"""

import json
import os
import sys
import argparse
from pathlib import Path


def format_price(price: int) -> str:
    """Format price with comma separators (e.g., 2500 -> 2,500)."""
    return f"{price:,}"


def generate_page(template: str, domain_config: dict, contact_email: str) -> str:
    """Replace template variables with actual values."""
    domain = domain_config["domain"]
    price = domain_config["price"]
    dan_url = domain_config.get("dan_url", f"https://dan.com/buy-domain/{domain}")

    page = template
    page = page.replace("{{DOMAIN}}", domain)
    page = page.replace("{{PRICE}}", str(price))
    page = page.replace("{{PRICE_FORMATTED}}", format_price(price))
    page = page.replace("{{DAN_URL}}", dan_url)
    page = page.replace("{{CONTACT_EMAIL}}", contact_email)

    return page


def main():
    parser = argparse.ArgumentParser(description="Generate domain for-sale landing pages")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to domains config JSON (default: config/domains-for-sale.json)",
    )
    parser.add_argument(
        "--template",
        default=None,
        help="Path to HTML template (default: templates/for-sale/index.html)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: domains/for-sale/)",
    )
    parser.add_argument(
        "--contact-email",
        default="domains@theluckystrike.com",
        help="Contact email address",
    )
    args = parser.parse_args()

    # Resolve paths relative to project root
    project_root = Path(__file__).resolve().parent.parent

    config_path = Path(args.config) if args.config else project_root / "config" / "domains-for-sale.json"
    template_path = Path(args.template) if args.template else project_root / "templates" / "for-sale" / "index.html"
    output_dir = Path(args.output_dir) if args.output_dir else project_root / "domains" / "for-sale"

    # Load template
    if not template_path.exists():
        print(f"ERROR: Template not found: {template_path}")
        sys.exit(1)

    template = template_path.read_text(encoding="utf-8")

    # Load config
    if not config_path.exists():
        print(f"ERROR: Config not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        domains = json.load(f)

    print(f"Template: {template_path}")
    print(f"Config:   {config_path} ({len(domains)} domains)")
    print(f"Output:   {output_dir}")
    print()

    # Generate pages
    generated = 0
    for domain_config in domains:
        domain = domain_config["domain"]
        page = generate_page(template, domain_config, args.contact_email)

        # Write to output_dir/{domain}/index.html
        domain_dir = output_dir / domain
        domain_dir.mkdir(parents=True, exist_ok=True)

        out_file = domain_dir / "index.html"
        out_file.write_text(page, encoding="utf-8")

        size_kb = len(page.encode("utf-8")) / 1024
        print(f"  Generated: {domain}/index.html ({size_kb:.1f} KB) - ${format_price(domain_config['price'])}")
        generated += 1

    print(f"\nDone. {generated} landing pages generated.")


if __name__ == "__main__":
    main()
