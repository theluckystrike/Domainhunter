#!/usr/bin/env python3
"""
Sprint 16 - DeepSeek Monetization Classifier
Classifies top 37 dropping whale domains by monetization potential.
Single API call to minimize cost.
"""

import json
import requests
import sys
from datetime import datetime

API_URL = "https://api.deepseek.com/v1/chat/completions"
API_KEY = "sk-7def9bbbdc3e49a6a4ac0fcdc12e0334"
MODEL = "deepseek-chat"
OUTPUT_PATH = "/Users/mike/Desktop/domainhunter/data/sprint16_monetization.json"

PROMPT = """You are a domain monetization expert. For each domain below, assess:
1. Monetization Model (affiliate, SaaS, content/ads, lead gen, ecommerce, community, tool)
2. Revenue Potential (HIGH=$1000+/mo, MEDIUM=$200-$1000/mo, LOW=<$200/mo)
3. Build Difficulty (EASY=landing page/redirect, MEDIUM=simple tool, HARD=complex app)
4. Brand Value (GENERIC=describes a thing, BRAND=company name, NICHE=specific audience)
5. Competition Level (LOW, MEDIUM, HIGH)
6. One-line monetization strategy

Domains:
1. alabe.com ($802K ETV) - astrology
2. calculator.com ($761K ETV) - calculator tools
3. bench.co ($481K ETV) - bookkeeping
4. chatbot.com ($434K ETV) - AI chatbot
5. asciitable.com ($83K ETV) - ASCII reference
6. encoder.com ($43K ETV) - encoding tools
7. invoicemaker.com ($40K ETV) - invoice tools
8. foodbank.org ($31K ETV) - food bank
9. nonprofitaccountingbasics.org ($29K ETV) - nonprofit accounting
10. texteditor.com ($27K ETV) - text editor
11. jsondiff.com ($27K ETV) - JSON comparison
12. aigenerator.com ($27K ETV) - AI tools
13. bmicalc.com ($25K ETV) - BMI calculator
14. plastiq.com ($24K ETV) - payment platform
15. conferenceindex.org ($15K ETV) - conference listing
16. eatatmurphs.com ($15K ETV) - restaurant
17. guerrameats.com ($11K ETV) - meat shop
18. globalhealth.org ($10K ETV) - health org
19. lumio.com ($9K ETV) - lighting/tech
20. readingfoundation.org ($7K ETV) - reading education
21. codeparrot.ai ($5K ETV) - AI coding
22. newcap.org ($5K ETV) - community org
23. sitecheck.com ($4K ETV) - site scanner
24. getir.com ($4K ETV) - delivery
25. sendy.co ($3K ETV) - email marketing
26. itsflip.com ($3K ETV) - social commerce
27. sunnyray.org ($3K ETV) - spiritual/healing
28. ammonoosuc.org ($3K ETV) - community
29. themessenger.com ($2K ETV) - news
30. woodysseafood.com ($2K ETV) - seafood
31. northvolt.com ($2K ETV) - batteries
32. juicero.com ($1K ETV) - juice
33. veev.com ($1K ETV) - construction
34. mikespienh.com ($1K ETV) - restaurant
35. internetfreedom.org ($1K ETV) - digital rights
36. rtfkt.com ($1K ETV) - NFT/fashion
37. affordableeducation.org ($1K ETV) - education

Return ONLY a JSON array with objects: {"domain", "model", "revenue", "difficulty", "brand", "competition", "strategy"}
No markdown formatting, no code fences, just raw JSON."""

def main():
    print(f"[{datetime.now().isoformat()}] Sending 37 domains to DeepSeek for monetization classification...")

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a domain monetization expert. Return only valid JSON with no markdown formatting."
            },
            {
                "role": "user",
                "content": PROMPT
            }
        ],
        "max_tokens": 4000,
        "temperature": 0.3
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response body: {e.response.text}")
        sys.exit(1)

    data = resp.json()

    # Extract usage info
    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)

    # DeepSeek pricing: ~$0.14/1M input, ~$0.28/1M output (deepseek-chat)
    cost_est = (prompt_tokens * 0.14 / 1_000_000) + (completion_tokens * 0.28 / 1_000_000)

    print(f"Tokens used: {prompt_tokens} input + {completion_tokens} output = {total_tokens} total")
    print(f"Estimated cost: ${cost_est:.4f}")

    # Parse the response content
    raw_content = data["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if present
    if raw_content.startswith("```"):
        lines = raw_content.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw_content = "\n".join(lines)

    try:
        results = json.loads(raw_content)
    except json.JSONDecodeError as e:
        print(f"WARNING: Failed to parse JSON response: {e}")
        print(f"Raw content (first 500 chars): {raw_content[:500]}")
        # Try to find JSON array in the response
        start = raw_content.find("[")
        end = raw_content.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                results = json.loads(raw_content[start:end])
                print("Successfully extracted JSON array from response.")
            except json.JSONDecodeError:
                print("ERROR: Could not extract valid JSON from response.")
                # Save raw response for debugging
                with open(OUTPUT_PATH.replace(".json", "_raw.txt"), "w") as f:
                    f.write(raw_content)
                sys.exit(1)
        else:
            print("ERROR: No JSON array found in response.")
            sys.exit(1)

    print(f"Successfully parsed {len(results)} domain classifications.")

    # Determine top 5 actionable domains based on revenue/difficulty ratio
    # Scoring: HIGH revenue=3, MEDIUM=2, LOW=1; EASY difficulty=3, MEDIUM=2, HARD=1
    rev_score = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    diff_score = {"EASY": 3, "MEDIUM": 2, "HARD": 1}
    comp_score = {"LOW": 3, "MEDIUM": 2, "HIGH": 1}

    scored = []
    for r in results:
        revenue = r.get("revenue", "LOW").upper()
        difficulty = r.get("difficulty", "HARD").upper()
        competition = r.get("competition", "HIGH").upper()
        score = rev_score.get(revenue, 1) * diff_score.get(difficulty, 1) * comp_score.get(competition, 1)
        scored.append({**r, "_score": score})

    scored.sort(key=lambda x: x["_score"], reverse=True)
    top_5 = []
    for item in scored[:5]:
        entry = {k: v for k, v in item.items() if k != "_score"}
        entry["_score"] = item["_score"]
        top_5.append(entry)

    # Build output
    output = {
        "classifier": "deepseek-chat",
        "classified_at": datetime.now().isoformat(),
        "api_cost_est": f"~${cost_est:.4f}",
        "tokens": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": total_tokens
        },
        "domains_classified": len(results),
        "results": results,
        "top_5_actionable": top_5,
        "scoring_method": "revenue_score * difficulty_score * competition_score (each HIGH/EASY/LOW=3, MED=2, LOW/HARD/HIGH=1)"
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults written to {OUTPUT_PATH}")
    print(f"\n{'='*60}")
    print("TOP 5 ACTIONABLE DOMAINS (best revenue/difficulty/competition ratio):")
    print(f"{'='*60}")
    for i, d in enumerate(top_5, 1):
        print(f"  {i}. {d['domain']}")
        print(f"     Model: {d['model']} | Revenue: {d['revenue']} | Difficulty: {d['difficulty']}")
        print(f"     Competition: {d['competition']} | Brand: {d['brand']}")
        print(f"     Strategy: {d['strategy']}")
        print(f"     Score: {d['_score']}")
        print()

if __name__ == "__main__":
    main()
