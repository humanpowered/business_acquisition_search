@echo off
cd /d "C:\Users\Craig Nebeker\OneDrive\Documents\business-acquisition-search"

echo ===== Starting run %date% %time% ===== >> "C:\Users\Craig Nebeker\OneDrive\Documents\business-acquisition-search\scheduler.log"

"C:\Users\Craig Nebeker\AppData\Roaming\npm\claude.cmd" -p "Run the business acquisition search. Read CLAUDE.md in this directory first for full instructions (target criteria, sourcing steps, the SBA feasibility script at tools/business_finder.py, report format, and the commit+push-after-every-run requirement). Follow it exactly, including on a quiet week: if few or no genuinely fresh candidates turn up, say so plainly in the report rather than padding it. Save the report to reports/YYYY-MM-DD.md, then commit and push per CLAUDE.md step 7. This is an unattended weekly run -- Craig is not present, so make reasonable choices autonomously and note them in the report rather than asking questions." --allowedTools "Bash WebSearch WebFetch Write Edit Read" --output-format text >> "C:\Users\Craig Nebeker\OneDrive\Documents\business-acquisition-search\scheduler.log" 2>&1

echo ===== Finished %date% %time% ===== >> "C:\Users\Craig Nebeker\OneDrive\Documents\business-acquisition-search\scheduler.log"
echo. >> "C:\Users\Craig Nebeker\OneDrive\Documents\business-acquisition-search\scheduler.log"
