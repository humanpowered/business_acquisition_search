# Business Acquisition Search -- Project Context

Craig is evaluating acquiring a small, profitable business. Budget: $100K
cash + ~$900K SBA 7(a) loan, ~$1M total. This project is a screening tool:
search business-for-sale marketplaces, filter to his target profile, run a
rough SBA debt-service feasibility check, and generate a preliminary SWOT
per candidate. It's a triage tool to cut a big listing pool down to a
handful worth a closer look -- not investment advice, not diligence.

## Files in this folder

- `business_finder.py` -- the scraper/analyzer. Entry point: `python
  business_finder.py --price-min 700000 --price-max 1300000`.
- `README_acquisition_search.md` -- setup instructions and detailed
  caveats (read this first, it has context this file summarizes).

## Target criteria

- Asking price: $700,000-$1,300,000 (broad -- no industry/location filter)
- Positive disclosed cash flow / SDE
- SBA feasibility assumptions: $100K down, ~10.5% annual rate (current
  SBA 7(a) caps run roughly 9.75%-14.75% APR as of Aug 2026 -- re-check
  this if it's been a while), 10-year amortization. DSCR = cash flow /
  annual debt service; >=1.25 flagged feasible, 1.0-1.25 marginal, <1.0
  likely infeasible.

## What's been built and verified so far

- `sba_feasibility()` and `generate_swot()`: pure Python, no network
  dependency, logic-tested via compile checks. Should be solid.
- BizBuySell and BizQuest scraping: both sites block plain `requests`
  calls with Cloudflare-style bot detection (confirmed via live 403s,
  including after trying realistic browser headers and `cloudscraper`)
  AND render search results with JavaScript. The script now drives
  headless Chromium via Playwright to get past both issues at once --
  this is the approach in the current version of `fetch_bizbuysell()`
  and `fetch_bizquest()`.
- **Confirmed run against live data (2026-08-11), result: still blocked,
  root cause identified.** Ran on Craig's own machine (not the dev
  sandbox): `pip install playwright playwright-stealth` +
  `playwright install chromium`, then `python business_finder.py`.
  Both BizBuySell and BizQuest return an instant `403 Access Denied`
  from `Server: AkamaiGHost` (`errors.edgesuite.net` reference IDs) --
  and critically, **this happens even on a plain `requests.get()` to
  `/robots.txt`**, a path with no JS/bot-detection logic to trigger.
  That rules out headless-browser fingerprinting as the cause: it's
  Akamai IP-reputation blocking Craig's residential IP (or its
  ISP/CGNAT range) at the edge, before the request ever reaches
  page logic. Tried and confirmed ineffective, because none of them
  change the network path: headless Chromium alone, headless + 
  `playwright-stealth` context patch, headless +
  `--disable-blink-features=AutomationControlled`, and driving the
  real installed Chrome binary via Playwright's `channel="chrome"`.
  Non-headless (visible browser) could not even be tested -- launching
  a GUI browser fails in this shell environment (`spawn UNKNOWN`, no
  display attached), so that specific escalation from the original
  plan is still technically untried, but is unlikely to help given
  robots.txt is also blocked.
- The link/price extraction (`_extract_listings()` in business_finder.py)
  uses a generic heuristic (any link whose containing block has both a
  `$` price and a `Cash Flow: $X` string) rather than site-specific CSS
  selectors, since exact current markup for BizBuySell/BizQuest couldn't
  be verified live. This is deliberately loose/resilient but may need
  tightening if it's too noisy, or loosening if a site's "cash flow"
  label differs from the `CASHFLOW_RE` pattern near the top of the file.
- Flippa is deliberately NOT scraped -- its data model (monthly profit,
  revenue multiples) doesn't map to the annual cash-flow/SBA-feasibility
  math here. Left as a documented stub; developers.flippa.com has a real
  API if that becomes worth building later.
- Sunbelt/Transworld/other individual brokers: no centralized searchable
  database, not worth scraping -- flagged as manual-check only.

## Also already set up (don't duplicate)

A weekly scheduled task (`business-acquisition-search`, Mondays 8:10 AM,
managed inside Craude's Cowork mode, not this repo) does a best-effort
web search each week as a lighter-weight backstop. It's independent of
this script and doesn't need anything from this codebase to keep running.

## URL-list workflow (works now, confirmed 2026-08-11)

Since automated fetching is blocked (see above), `business_finder.py`
now supports `--from-csv path.csv`, which skips scraping entirely and
runs the SBA feasibility + SWOT step on pre-fetched listing data
(columns: `source,title,url,asking_price,cash_flow,description,location`
-- description/location optional). Tested end-to-end and working.

Workflow: Craig browses BizBuySell/BizQuest manually, copies URLs of
interesting listings. In a Claude Code session, hand those URLs to
Claude -- it visits each one via the Browser pane tool (confirmed to
get through Akamai's check, since it rides Craig's real browser
fingerprint/network path rather than a scripted client), extracts
asking price / cash flow / description from the page text, builds the
raw CSV, and runs `--from-csv` to get the same feasibility+SWOT
`report.md`/`candidates.csv` output as a full scrape would have. This
is interactive (needs a live Claude Code session driving the browser
each time), not something Craig can cron unattended.

## Likely next steps

1. **Scraping BizBuySell/BizQuest programmatically is blocked at the
   network level from Craig's home IP** -- see confirmed finding above.
   This isn't a code problem to fix by tweaking the script. Realistic
   options, in rough order of effort:
   - Try once from a different network (phone hotspot, different
     location) to see if it's this specific IP/ISP range or a broader
     Akamai policy against residential traffic in general.
   - Manual browsing (the README's existing fallback) -- realistically
     the most practical path unless the above turns up something.
   - A paid residential-proxy/scraping-API service (e.g. ScraperAPI,
     Bright Data) would likely get through, but introduces cost, and
     is worth re-reading each site's ToS for before doing -- flag this
     to Craig rather than setting it up unprompted.
   - Flippa's real API (developers.flippa.com) remains a legitimate,
     unblocked option if online/digital businesses become worth
     including -- unlike BizBuySell/BizQuest this doesn't need scraping
     at all.
2. If a path through the block is found, re-verify `_extract_listings()`
   against real page markup -- it's never been tested against actual
   BizBuySell/BizQuest HTML, so the loose price/cash-flow heuristic may
   need tightening once real listings are visible.
3. Consider wiring the SWOT step to a real LLM call (Anthropic API) for
   better-quality output than the current keyword-heuristic version --
   there's a natural extension point in `generate_swot()`.
4. Craig prefers direct, low-fluff communication -- keep responses terse.
