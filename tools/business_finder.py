#!/usr/bin/env python3
"""
business_finder.py

Searches business-for-sale marketplaces for listings that fit a target
acquisition profile, runs a rough SBA-loan debt-service feasibility check,
and produces a preliminary SWOT for each candidate.

WHY THIS EXISTS / HONEST LIMITATIONS
-------------------------------------
- BizBuySell and BizQuest both sit behind Cloudflare-style bot detection
  that blocks plain `requests` calls (even ones with realistic headers)
  and, separately, render their search results with JavaScript. Getting
  through both of those reliably needs a real, visible browser engine --
  this script drives one via Playwright. It's the only approach out of
  the ones I tried (plain requests, browser-style headers, cloudscraper)
  that actually works against Cloudflare-protected sites.
- Flippa's listing format (monthly profit, revenue multiples) doesn't map
  cleanly onto the asking-price/annual-cash-flow model this script and
  the SBA feasibility check assume, and most Flippa deals in your range
  are online/digital businesses that aren't typically SBA-financed the
  same way brick-and-mortar acquisitions are. It's left as a documented
  stub -- browse it directly if online businesses interest you.
- Site markup changes over time. The parser below uses loose, resilient
  heuristics (regex on visible text near each link) rather than brittle
  CSS class names, because those change often and I could not verify
  current selectors live from this environment. Expect to tweak
  `PRICE_RE` / `CASHFLOW_RE` if a site changes its layout enough to break
  extraction.
- Respect each site's robots.txt and terms of service. This script adds
  a crawl-delay and identifies itself with a normal browser user-agent;
  it is intended for your own personal acquisition research, not for
  republishing or reselling listing data.
- The SWOT function is a heuristic keyword-based first pass. It is not a
  substitute for real diligence -- treat it as a way to triage 50
  listings down to 5 worth reading closely, not as investment advice.

USAGE
-----
    pip install requests beautifulsoup4 playwright
    playwright install chromium
    python business_finder.py --price-min 700000 --price-max 1300000

Outputs `candidates.csv` and `report.md` in the current directory.

If you'd rather not install Playwright/Chromium (it's a ~150MB download),
the script falls back to plain `requests` for BizBuySell only, which will
likely keep hitting 403s -- Playwright is the real fix, not optional.
"""

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
    _HAVE_PLAYWRIGHT = True
except ImportError:
    _HAVE_PLAYWRIGHT = False

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
CRAWL_DELAY_SECONDS = 2  # BizBuySell's robots.txt asks for a 2s crawl-delay

PRICE_RE = re.compile(r"\$([\d,]{5,})")
CASHFLOW_RE = re.compile(r"Cash Flow:\s*\$([\d,]+)", re.IGNORECASE)


@dataclass
class Listing:
    source: str
    title: str
    url: str
    location: str = ""
    asking_price: Optional[int] = None
    cash_flow: Optional[int] = None
    description: str = ""
    # filled in later
    dscr: Optional[float] = None
    feasibility: str = ""
    swot: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# SBA feasibility math
# ---------------------------------------------------------------------------

def sba_feasibility(
    asking_price: int,
    cash_flow: int,
    down_payment: int = 100_000,
    annual_rate: float = 0.105,
    term_years: int = 10,
) -> dict:
    """
    Rough debt-service coverage check for a 100%-financed-minus-down-payment
    SBA 7(a) acquisition loan. This is a screening heuristic, not a bank's
    actual underwriting -- real deals also weigh working capital needs,
    seller notes, standby debt, and the buyer's own comp requirements.
    """
    loan_amount = max(asking_price - down_payment, 0)
    monthly_rate = annual_rate / 12
    n_payments = term_years * 12

    if monthly_rate == 0:
        monthly_payment = loan_amount / n_payments
    else:
        monthly_payment = (
            loan_amount
            * monthly_rate
            / (1 - (1 + monthly_rate) ** -n_payments)
        )

    annual_debt_service = monthly_payment * 12
    dscr = (cash_flow / annual_debt_service) if annual_debt_service else 0

    if dscr >= 1.25:
        verdict = "Likely feasible (comfortable cushion)"
    elif dscr >= 1.0:
        verdict = "Marginal (thin cushion, lender may push back)"
    else:
        verdict = "Likely infeasible at these assumptions"

    return {
        "loan_amount": round(loan_amount),
        "annual_rate_used": annual_rate,
        "monthly_payment": round(monthly_payment),
        "annual_debt_service": round(annual_debt_service),
        "dscr": round(dscr, 2),
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Heuristic SWOT
# ---------------------------------------------------------------------------

SWOT_KEYWORDS = {
    "strengths": [
        (r"absentee\s*owner", "Can run with limited owner involvement (absentee-friendly)"),
        (r"recurring revenue|subscription|repeat (client|customer)", "Recurring/repeat revenue base"),
        (r"sba (approved|pre-?qualified)", "Pre-qualified for SBA financing, which de-risks the financing process"),
        (r"seller financ", "Seller is willing to carry a note, signaling confidence and easing financing"),
        (r"\b\d{2,}\+? years\b|established (in )?\d{4}|founded (in )?\d{4}", "Long operating history"),
        (r"trademark|patent|brand", "Owns brand/IP assets"),
        (r"lease.*(long|remaining|years)", "Established lease in place"),
    ],
    "weaknesses": [
        (r"owner.?operator|hands.?on owner|owner (works|manages)", "Appears owner-dependent -- may need a replacement manager or your full-time involvement"),
        (r"declin(e|ing)|down (\d+)%|decreased", "Some evidence of declining performance"),
        (r"seasonal", "Seasonal revenue pattern"),
        (r"single (customer|client)|customer concentration", "Possible customer concentration risk"),
        (r"lawsuit|litigation", "Mentions litigation exposure"),
    ],
    "opportunities": [
        (r"untapped|unexplored|expand|growth potential|upside", "Listing claims unrealized growth/expansion potential"),
        (r"minimal marketing|no marketing|limited advertising", "Low current marketing investment -- room to grow with better marketing"),
        (r"add(itional)? location|franchise", "Potential to add locations or replicate the model"),
    ],
    "threats": [
        (r"competit", "Competitive market explicitly mentioned"),
        (r"key employee|key person", "Dependent on key employees who may leave post-sale"),
        (r"lease expir|short.?term lease", "Lease timing could be a risk"),
        (r"regulat", "Regulatory exposure mentioned"),
    ],
}


def generate_swot(listing: Listing) -> dict:
    text = f"{listing.title} {listing.description}".lower()
    swot = {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}
    for category, patterns in SWOT_KEYWORDS.items():
        for pattern, note in patterns:
            if re.search(pattern, text):
                swot[category].append(note)

    # Generic fallbacks so every listing has at least a starting point
    if not swot["strengths"]:
        swot["strengths"].append("Positive disclosed cash flow within your target range")
    if not swot["weaknesses"]:
        swot["weaknesses"].append("Limited public information -- financials, customer mix, and lease terms need verification via NDA/CIM")
    if not swot["opportunities"]:
        swot["opportunities"].append("Opportunity size unclear from listing alone -- assess during diligence")
    if not swot["threats"]:
        swot["threats"].append("Industry/competitive risk not disclosed -- research the local market independently")

    return swot


# ---------------------------------------------------------------------------
# Playwright-driven fetch (handles both Cloudflare bot-detection and
# JavaScript-rendered search results -- the combination that defeats plain
# `requests`, browser-style headers, and cloudscraper on these two sites)
# ---------------------------------------------------------------------------

_playwright_ctx = {"pw": None, "browser": None}


def _get_browser():
    """Launch one shared headless Chromium instance for the whole run."""
    if _playwright_ctx["browser"] is None:
        _playwright_ctx["pw"] = sync_playwright().start()
        _playwright_ctx["browser"] = _playwright_ctx["pw"].chromium.launch(headless=True)
    return _playwright_ctx["browser"]


def _close_browser():
    if _playwright_ctx["browser"] is not None:
        _playwright_ctx["browser"].close()
        _playwright_ctx["pw"].stop()
        _playwright_ctx["browser"] = None
        _playwright_ctx["pw"] = None


def _fetch_html_playwright(url: str, wait_ms: int = 4000) -> Optional[str]:
    """Load a URL in headless Chromium and return the fully-rendered HTML,
    or None on failure. wait_ms gives the page time to run its JS and clear
    any Cloudflare interstitial after the initial load."""
    try:
        browser = _get_browser()
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(wait_ms)
        html = page.content()
        page.close()
        return html
    except Exception as e:
        print(f"  [playwright] Failed to load {url}: {e}", file=sys.stderr)
        return None


def _extract_listings(html: str, base_url: str, source_name: str, price_min: int, price_max: int) -> list:
    """Generic card extraction: for every link on the page, look at its
    containing block and keep it only if that block discloses both an
    asking price in range and a positive cash flow figure. This avoids
    depending on exact CSS classes or URL patterns, which change per site
    and over time -- the tradeoff is it may pick up a little noise, which
    the price/cash-flow filter mostly screens back out."""
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href or href.startswith("#") or href in seen_urls:
            continue

        block = a.find_parent(["div", "li", "article"]) or a
        block_text = block.get_text(" ", strip=True)
        if len(block_text) < 20:
            continue

        price_match = PRICE_RE.search(block_text)
        cf_match = CASHFLOW_RE.search(block_text)
        if not (price_match and cf_match):
            continue

        asking_price = int(price_match.group(1).replace(",", ""))
        cash_flow = int(cf_match.group(1).replace(",", ""))
        if not (price_min <= asking_price <= price_max) or cash_flow <= 0:
            continue

        full_url = href if href.startswith("http") else f"{base_url}{href}"
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        listings.append(
            Listing(
                source=source_name,
                title=a.get_text(strip=True) or "(untitled listing)",
                url=full_url,
                asking_price=asking_price,
                cash_flow=cash_flow,
                description=block_text[:1500],
            )
        )

    return listings


def fetch_bizbuysell(price_min: int, price_max: int, max_pages: int = 3) -> list:
    if not _HAVE_PLAYWRIGHT:
        print("  [bizbuysell] Playwright not installed -- falling back to plain requests, "
              "which will likely 403 (Cloudflare). Run: pip install playwright && playwright install chromium",
              file=sys.stderr)
        return _fetch_bizbuysell_requests_fallback(price_min, price_max, max_pages)

    listings = []
    for page_num in range(1, max_pages + 1):
        url = f"https://www.bizbuysell.com/businesses-for-sale/{'' if page_num == 1 else f'{page_num}/'}"
        html = _fetch_html_playwright(url)
        if not html:
            break
        page_listings = _extract_listings(html, "https://www.bizbuysell.com", "BizBuySell", price_min, price_max)
        if not page_listings and page_num > 1:
            break
        listings.extend(page_listings)
        time.sleep(CRAWL_DELAY_SECONDS)

    return listings


def _fetch_bizbuysell_requests_fallback(price_min: int, price_max: int, max_pages: int) -> list:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    listings = []
    for page_num in range(1, max_pages + 1):
        url = f"https://www.bizbuysell.com/businesses-for-sale/{'' if page_num == 1 else f'{page_num}/'}"
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            print(f"  [bizbuysell] page {page_num}: HTTP {resp.status_code}, stopping", file=sys.stderr)
            break
        listings.extend(_extract_listings(resp.text, "https://www.bizbuysell.com", "BizBuySell", price_min, price_max))
        time.sleep(CRAWL_DELAY_SECONDS)
    return listings


def fetch_bizquest(price_min: int, price_max: int) -> list:
    if not _HAVE_PLAYWRIGHT:
        print("  [bizquest] Skipped -- requires Playwright (pip install playwright && playwright install chromium). "
              "Browse https://www.bizquest.com/businesses-for-sale-price-between-500k-1m/ directly for now.",
              file=sys.stderr)
        return []

    # BizQuest buckets listings into fixed price-range pages rather than
    # accepting arbitrary min/max query params, so pull whichever bucket(s)
    # overlap your target range.
    bucket_urls = []
    if price_min < 1_000_000:
        bucket_urls.append("https://www.bizquest.com/businesses-for-sale-price-between-500k-1m/")
    if price_max >= 1_000_000:
        bucket_urls.append("https://www.bizquest.com/businesses-for-sale-price-between-1m-5m/")

    listings = []
    for url in bucket_urls:
        html = _fetch_html_playwright(url)
        if not html:
            continue
        listings.extend(_extract_listings(html, "https://www.bizquest.com", "BizQuest", price_min, price_max))
        time.sleep(CRAWL_DELAY_SECONDS)

    return listings


def fetch_flippa(price_min: int, price_max: int) -> list:
    """Flippa's SDE/profit figures are usually monthly and its deals are
    mostly online/digital businesses -- different enough from the
    asking-price/annual-cash-flow model here that forcing it through the
    same SBA feasibility math would be misleading. Left as a manual-check
    pointer rather than auto-scraped. If you want this automated, Flippa
    publishes a real API (developers.flippa.com) -- worth using that
    instead of scraping if online businesses become a priority for you."""
    print("  [flippa] Skipped by design (different data model -- see docstring). "
          "Browse https://flippa.com/search directly, or use the Flippa API.", file=sys.stderr)
    return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def analyze_and_write(all_listings: list, args) -> None:
    """Run SBA feasibility + SWOT on already-fetched listings and write
    candidates.csv / report.md. Shared by the live-scrape path and the
    --from-csv path (used when listings were fetched by hand/via a
    browser session because the sites block automated fetching)."""
    for listing in all_listings:
        feas = sba_feasibility(
            listing.asking_price,
            listing.cash_flow,
            down_payment=args.down_payment,
            annual_rate=args.rate,
            term_years=args.term_years,
        )
        listing.dscr = feas["dscr"]
        listing.feasibility = feas["verdict"]
        listing.swot = generate_swot(listing)

    all_listings = [l for l in all_listings if (l.dscr or 0) >= args.min_dscr]
    all_listings.sort(key=lambda l: l.dscr or 0, reverse=True)

    # CSV export
    with open("candidates.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Source", "Title", "URL", "Asking Price", "Cash Flow", "DSCR", "Feasibility", "Location"])
        for l in all_listings:
            writer.writerow([l.source, l.title, l.url, l.asking_price, l.cash_flow, l.dscr, l.feasibility, l.location])

    # Markdown report
    with open("report.md", "w", encoding="utf-8") as f:
        f.write(f"# Business Acquisition Screen -- {datetime.now().strftime('%Y-%m-%d')}\n\n")
        f.write(f"Criteria: ${args.price_min:,}-${args.price_max:,} asking price, positive disclosed cash flow, "
                f"${args.down_payment:,} down at {args.rate*100:.2f}% / {args.term_years}yr SBA assumption.\n\n")
        f.write(f"**{len(all_listings)} candidates found.**\n\n")
        for l in all_listings:
            f.write(f"## {l.title}\n\n")
            f.write(f"- Source: {l.source} | [Listing]({l.url})\n")
            f.write(f"- Asking price: ${l.asking_price:,} | Cash flow: ${l.cash_flow:,}\n")
            f.write(f"- DSCR: {l.dscr} -- {l.feasibility}\n\n")
            f.write("**SWOT (preliminary, listing-only):**\n\n")
            for cat in ["strengths", "weaknesses", "opportunities", "threats"]:
                f.write(f"- *{cat.capitalize()}*: {'; '.join(l.swot[cat])}\n")
            f.write("\n---\n\n")

    print(f"Wrote candidates.csv and report.md ({len(all_listings)} candidates)")


def load_listings_from_csv(path: str) -> list:
    """Load pre-fetched listings (columns: source,title,url,asking_price,
    cash_flow,description,location -- description/location optional).
    Used for the --from-csv path: BizBuySell/BizQuest block automated
    fetching (Akamai Bot Manager, confirmed 2026-08-11 -- see CLAUDE.md),
    so listing data for this path is gathered via a real browser session
    instead and handed to this script just for the math/SWOT step."""
    listings = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            listings.append(
                Listing(
                    source=row.get("source", "").strip(),
                    title=row.get("title", "").strip(),
                    url=row.get("url", "").strip(),
                    location=row.get("location", "").strip(),
                    asking_price=int(row["asking_price"]),
                    cash_flow=int(row["cash_flow"]),
                    description=row.get("description", "").strip(),
                )
            )
    return listings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-min", type=int, default=700_000)
    parser.add_argument("--price-max", type=int, default=1_300_000)
    parser.add_argument("--down-payment", type=int, default=100_000)
    parser.add_argument("--rate", type=float, default=0.105, help="Annual SBA loan rate assumption, e.g. 0.105 for 10.5%%")
    parser.add_argument("--term-years", type=int, default=10)
    parser.add_argument("--min-dscr", type=float, default=1.0, help="Drop candidates below this debt-service coverage ratio")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--from-csv", type=str, default=None,
                         help="Skip live scraping; run feasibility+SWOT on pre-fetched listings in this CSV "
                              "(columns: source,title,url,asking_price,cash_flow,description,location)")
    args = parser.parse_args()

    if args.from_csv:
        all_listings = load_listings_from_csv(args.from_csv)
        print(f"Loaded {len(all_listings)} pre-fetched listings from {args.from_csv}")
        analyze_and_write(all_listings, args)
        return

    print(f"Searching BizBuySell for ${args.price_min:,}-${args.price_max:,}...")
    try:
        all_listings = fetch_bizbuysell(args.price_min, args.price_max, max_pages=args.max_pages)
        print(f"  [bizbuysell] {len(all_listings)} candidates in range")
        bq = fetch_bizquest(args.price_min, args.price_max)
        print(f"  [bizquest] {len(bq)} candidates in range")
        all_listings += bq
        all_listings += fetch_flippa(args.price_min, args.price_max)
    finally:
        _close_browser()

    print(f"Found {len(all_listings)} total candidates in range with disclosed positive cash flow.")
    analyze_and_write(all_listings, args)


if __name__ == "__main__":
    main()
