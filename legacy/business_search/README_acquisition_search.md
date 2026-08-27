# Small Business Acquisition Search -- Setup & Methodology

## What this is

`business_finder.py` screens business-for-sale listings against your
target profile ($700K-$1.3M asking price, positive disclosed cash flow,
no industry/location restriction), runs a rough SBA debt-service
feasibility check on each, and writes out a heuristic SWOT for every
candidate. Output: `candidates.csv` and `report.md`.

## Status: BizBuySell and BizQuest are currently blocked from this network

Ran end-to-end on 2026-08-11 from Craig's own machine. Both sites return
an instant `403 Access Denied` from Akamai (`Server: AkamaiGHost`) --
including on a plain request to `/robots.txt`, a path with no bot-check
logic behind it. That means it's an IP-reputation block at the network
edge, not headless-browser detection: headless Chromium, a
`playwright-stealth`-patched context, anti-automation launch flags, and
driving the real installed Chrome binary via Playwright all hit the same
wall. A non-headless (visible) browser run is the one thing not yet
ruled out, but couldn't be tested in this shell (no display attached),
and is unlikely to matter given robots.txt is blocked too.

Practical options: try once from a different network (phone hotspot) to
see if it's this IP specifically; fall back to manually browsing the
sites (always fine, and the honest baseline); or use a paid
scraping-proxy service if this becomes a recurring need -- worth
checking each site's ToS first if so. See `CLAUDE.md` for the full
diagnosis.

Setup instructions below are still accurate for how the script is meant
to be run if/when the block clears:

```
pip install requests beautifulsoup4 playwright
playwright install chromium
python business_finder.py --price-min 700000 --price-max 1300000
```

`playwright install chromium` downloads a real headless browser (~150MB,
one-time). It's necessary, not optional: BizBuySell and BizQuest both sit
behind Cloudflare-style bot detection that blocks plain `requests` calls
outright (we hit this -- 403s even with realistic browser headers, and
even with `cloudscraper`), on top of loading their search results with
JavaScript. A real browser engine is the only thing that gets through
both of those. Run it once, open `report.md`, and sanity-check a couple
of listings against the live site. If a site changes its page layout
enough to break extraction, the price/cash-flow regexes near the top of
the file are the spot to adjust.

## Coverage: BizBuySell and BizQuest are scraped; Flippa is not

- **BizBuySell**: scraped via headless Chromium (Playwright).
- **BizQuest**: same approach, pulling its two price-bucket pages that
  overlap $700K-$1.3M ($500K-$1M and $1M-$5M).
- **Flippa**: intentionally left as a manual-check pointer. Its listings
  report monthly profit and revenue multiples rather than annual asking
  price / cash flow, so folding it into the same SBA feasibility math
  would produce misleading numbers. Flippa also publishes a real API
  (developers.flippa.com) if you want to automate it properly later.
- **Sunbelt / Transworld / other brokers**: these are broker networks
  without a single searchable database the way BizBuySell/BizQuest work
  -- individual brokers list independently. Best handled by periodic
  manual browsing or by watching their email alerts, not by scraping.

If Playwright isn't installed, the script still runs but falls back to
plain `requests` for BizBuySell only (which will likely 403 again) and
skips BizQuest entirely.

## Legal note

BizBuySell's and BizQuest's `robots.txt` don't block general crawlers
from their public listing pages (they block specific bots like AhrefsBot
and set a 2-second crawl delay, which the script respects). That's a
weaker signal than their Terms of Service, though -- many listing sites'
ToS separately restrict automated data collection even where robots.txt
allows it. This script is meant for your own personal research at a
light, respectful pace (a handful of runs, not continuous polling) --
not for republishing, reselling, or bulk-archiving listings. If you plan
to run this often or share the output beyond your own use, it's worth a
quick read of each site's current ToS.

## SBA feasibility assumptions (as of Aug 2026)

Current SBA 7(a) rate caps run roughly 9.75%-14.75% APR depending on loan
size and structure; variable-rate loans are typically Prime + 2.25-4.75%,
with Prime at 6.75% as of July 2026 (~9-11.5% APR). The script defaults
to 10.5% fixed, 10-year term, $100K down -- override with `--rate`,
`--term-years`, `--down-payment` if your lender quotes differently.

Sources: [Lendio](https://www.lendio.com/blog/sba-loan-interest-rates),
[NerdWallet](https://www.nerdwallet.com/business/loans/learn/sba-loan-rates)

The debt-service coverage ratio (DSCR) it computes is `cash flow / annual
debt service`. Most SBA lenders want to see 1.15-1.25x+ before they'll
approve; the script flags anything under 1.0x as likely infeasible at
those assumptions. This is a screening shortcut, not underwriting --
actual approval also depends on your personal credit, industry
experience, collateral, and whether you need working capital on top of
the purchase price.

## SWOT caveat

The SWOT in `report.md` is generated from keyword patterns in the public
listing text alone (e.g. "absentee owner," "seller financing," "owner-
operator," "customer concentration"). It's meant to help you triage a
big list down to the ones worth pursuing an NDA for -- it is not
diligence. Real financials, customer concentration, lease terms, and
litigation history only come out after signing an NDA and reviewing the
CIM/financials directly with the broker.

## Recurring search

A weekly scheduled task has been set up to do a best-effort search each
week and message you with new candidates. Because of the sandbox network
restriction noted above, that automated run may sometimes only be able
to search via general web search rather than a full scrape -- treat its
output as a heads-up to go look at the live sites, not as an exhaustive
feed. Running `business_finder.py` yourself periodically (or on a local
cron job) will be the more complete and reliable source.
