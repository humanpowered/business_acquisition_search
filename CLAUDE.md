# Business Acquisition Search

You are helping Craig (craigdnebeker@gmail.com) find small businesses to acquire.
Budget: $100K cash + ~$900K SBA loan, ~$1M total.
Target: asking price roughly $700,000–$1,300,000, positive disclosed cash flow/SDE. No industry or location restriction — broad screen.

## Each run, do the following

1. **Source listings.** Try BizBuySell (https://www.bizbuysell.com/businesses-for-sale/) directly via WebFetch. Also try BizQuest and Flippa — these are heavily JS-rendered, so a plain fetch often returns an empty shell. If a fetch comes back empty or nav-only, fall back to WebSearch with queries like `site:bizbuysell.com business for sale cash flow $900,000`. Be upfront in the report about which sites yielded real data this run.

2. **Data quality check, before including any listing:** sanity-check whether the content looks current — recent dates, no leftover references to years far in the past (e.g. "figures for FY2018," "revenue forecast 2018 thru 2022" are stale-cache tells). BizBuySell in particular seems to serve inconsistent freshness across category pages — some pages come back current, others come back as multi-year-old cached snapshots. Check every page you pull, not just the first one. If you can't tell whether a listing is current, say so explicitly rather than presenting it as fresh.

3. **SBA debt-service feasibility check**, for each candidate with a disclosed asking price and cash flow in range: loan amount = asking price − $100,000 down. Search for the current SBA 7(a) rate (as of a recent reference point, the range has run roughly 9.75%–14.75% APR caps; ~10.5% is a reasonable default absent a fresher number). Use 10-year amortization. Compute annual debt service and DSCR = cash flow / annual debt service. Flag DSCR ≥ 1.25 as likely feasible, 1.0–1.25 as marginal, < 1.0 as likely infeasible.

4. **Preliminary SWOT** for each candidate, using only the public listing description. Label it clearly as preliminary/listing-only, not diligence.

5. **Compile a short markdown report**: date, which sites yielded real data this run, candidates ranked by DSCR with price/cash-flow/DSCR/SWOT, and a one-line reminder that this is a triage tool, not investment advice. Save it to `reports/YYYY-MM-DD.md` in this repo. **Every candidate listing must include a direct URL to the listing** so Craig can open it himself — if a listing came from a WebSearch result without a clean listing-page URL, include the best URL available (search result link) and note that it may need to be reached via search rather than direct link.

6. **If few or no genuinely fresh candidates turn up** (fetches blocked or stale), say so plainly instead of padding the report — an honest "nothing new, here's what to check manually" beats a report that looks complete but isn't.

7. **Commit after every run.** Once the report is saved, `git add reports/<file> CLAUDE.md README.md` (whatever changed) and commit with a short message noting the date and candidate count, e.g. `git commit -m "Acquisition search 2026-08-27: 4 candidates"`. Do this even if the run found nothing — commit the report either way so `git log` reflects every run.

Keep the report concise — direct, low-fluff writing, no filler.

## Notes for Claude Code specifically

- Use the built-in WebSearch and WebFetch tools directly — no Cowork-style provenance restriction; you can fetch URLs found via search normally.
- Save reports under `reports/`, named by date, so `git log`/`git diff` gives a history of what changed run over run.
- If a fetch throws or times out, don't spend more than 1–2 retries on the same URL — fall back to WebSearch and move on.
