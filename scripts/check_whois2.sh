#!/bin/bash
# Check WHOIS for a list of domains via Verisign registry
# Output: TSV format with tab delimiter

DOMAINS=(
# DEVELOPER TOOLS
devtools.com codetools.com webtools.com apitools.com devkit.com codekit.com
toolkit.com toolbox.com debugger.com linter.com formatter.com validator.com
compiler.com parser.com minifier.com beautifier.com profiler.com analyzer.com
tester.com reviewer.com deployer.com builder.com runner.com executor.com
# FINANCE
loancalc.com taxcalc.com mortgagerate.com loanrate.com savingsrate.com
interestrate.com creditcheck.com debtcalc.com budgetcalc.com investcalc.com
retirementcalc.com annuitycalc.com dividendcalc.com
# SEO/MARKETING
seotool.com seocheck.com rankcheck.com backlinkcheck.com keywordtool.com
sitecheck.com pagerank.com domaincheck.com websitecheck.com siteanalyzer.com
webanalyzer.com contentcheck.com plagiarismcheck.com
# FOOD/RECIPE
recipefinder.com recipebook.com recipemaker.com cookingtool.com mealplanner.com
foodcalc.com nutritioncalc.com caloriefinder.com ingredientfinder.com portionsize.com
# EDUCATION
flashcards.com quizmaker.com studytool.com learningtool.com mathtool.com
sciencetool.com readingtool.com writingtool.com vocabularytool.com grammartool.com
# HEALTH/FITNESS
bmicalc.com fitnesscalc.com workoutplanner.com exercisetool.com diettool.com
nutritiontool.com healthcheck.com symptomscheck.com medicaltool.com
# GENERAL UTILITIES
converter.com calculator.com generator.com randomizer.com timer.com
countdown.com stopwatch.com scheduler.com planner.com organizer.com
tracker.com monitor.com checker.com finder.com picker.com sorter.com
counter.com encoder.com decoder.com translator.com
)

OUTDIR="/Users/mike/Desktop/domainhunter/data/whois_records"
mkdir -p "$OUTDIR"

for domain in "${DOMAINS[@]}"; do
    echo "Checking: $domain" >&2
    outfile="$OUTDIR/${domain}.txt"
    whois -h whois.verisign-grs.com "$domain" 2>/dev/null > "$outfile"
    sleep 0.3
done

echo "Done!" >&2
