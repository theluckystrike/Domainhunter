#!/bin/bash
# Check WHOIS for a list of domains via Verisign registry
# Output: domain|registrar|creation|expiry|status|nameservers|updated

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

OUTFILE="/Users/mike/Desktop/domainhunter/data/whois_raw.txt"
> "$OUTFILE"

for domain in "${DOMAINS[@]}"; do
    echo "Checking: $domain" >&2
    result=$(whois -h whois.verisign-grs.com "$domain" 2>/dev/null)
    
    registrar=$(echo "$result" | grep "Registrar:" | head -1 | sed 's/.*Registrar: //')
    creation=$(echo "$result" | grep "Creation Date:" | head -1 | sed 's/.*Creation Date: //')
    expiry=$(echo "$result" | grep "Registry Expiry Date:" | head -1 | sed 's/.*Registry Expiry Date: //')
    status=$(echo "$result" | grep "Domain Status:" | sed 's/.*Domain Status: //' | tr '\n' ';')
    nameservers=$(echo "$result" | grep "Name Server:" | sed 's/.*Name Server: //' | tr '\n' ';')
    updated=$(echo "$result" | grep "Updated Date:" | head -1 | sed 's/.*Updated Date: //')
    
    if [ -z "$registrar" ]; then
        echo "${domain}|AVAILABLE|||||" >> "$OUTFILE"
    else
        echo "${domain}|${registrar}|${creation}|${expiry}|${status}|${nameservers}|${updated}" >> "$OUTFILE"
    fi
    
    # Small delay to avoid rate limiting
    sleep 0.5
done

echo "Done! Results in $OUTFILE" >&2
