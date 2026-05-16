const puppeteer = require('puppeteer');
const fs = require('fs');

const DOMAINS = [
  // Priority 1 (claimed DR 20+)
  'fitocracy.com',
  'devhub.io',
  'apitools.com',
  'codeguide.com',
  'bestdevtools.com',
  'prompttools.com',
  'codeparrot.ai',
  'locale.ai',
  'fileforge.com',
  'toolchain.io',
  'freetail.com',
  'tune.ai',
  'devtools.io',
  // Priority 2
  'sitegrader.com',
  'codetools.com',
  'saasmetrics.com',
  'codingtools.com',
  'codebench.com',
  'codehelper.com',
  'codeanalyzer.com',
  'imageeditor.net',
  'aitoolkit.com',
  'taskplanner.com',
  // Special
  'mortgagecalc.com',
  'seochecker.com'
];

async function checkDomain(page, domain) {
  try {
    console.log(`Checking ${domain}...`);

    // Navigate to authority checker with domain
    await page.goto(`https://ahrefs.com/website-authority-checker?input=${domain}`, {
      waitUntil: 'networkidle2',
      timeout: 30000
    });

    // Wait for results to load
    await page.waitForSelector('[class*="AuthorityChecker"]', { timeout: 15000 }).catch(() => {});

    // Wait a bit for JS rendering
    await new Promise(r => setTimeout(r, 3000));

    // Try to extract the metrics
    const metrics = await page.evaluate(() => {
      const getText = (selector) => {
        const el = document.querySelector(selector);
        return el ? el.textContent.trim() : null;
      };

      // Look for the big numbers in the result
      const allText = document.body.innerText;

      // Try to find DR number
      const drMatch = allText.match(/Domain Rating[^\d]*(\d+)/i);
      const backlinkMatch = allText.match(/Backlinks[^\d]*(\d[\d,.]*)/i);
      const refDomainsMatch = allText.match(/Referring domains[^\d]*(\d[\d,.]*)/i);

      // Also try to get structured data
      const numbers = document.querySelectorAll('[class*="number"], [class*="metric"], [class*="score"], [class*="value"]');
      const numberTexts = Array.from(numbers).map(n => n.textContent.trim()).filter(t => t.length < 20);

      // Look for specific data attributes
      const drElements = document.querySelectorAll('[data-testid*="dr"], [data-testid*="rating"], [class*="dr-"], [class*="rating"]');
      const drValues = Array.from(drElements).map(n => n.textContent.trim());

      return {
        dr: drMatch ? parseInt(drMatch[1]) : null,
        backlinks: backlinkMatch ? backlinkMatch[1].replace(/,/g, '') : null,
        referring_domains: refDomainsMatch ? refDomainsMatch[1].replace(/,/g, '') : null,
        numbers: numberTexts.slice(0, 10),
        dr_elements: drValues.slice(0, 5),
        page_text_snippet: allText.substring(0, 500)
      };
    });

    return { domain, ...metrics, error: null };
  } catch (err) {
    return { domain, error: err.message, dr: null, backlinks: null, referring_domains: null };
  }
}

async function main() {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-blink-features=AutomationControlled'
    ]
  });

  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36');
  await page.setViewport({ width: 1280, height: 800 });

  const results = [];

  // Check domains one at a time to avoid rate limits
  for (const domain of DOMAINS) {
    const result = await checkDomain(page, domain);
    results.push(result);
    console.log(`  DR: ${result.dr}, Backlinks: ${result.backlinks}, RefDomains: ${result.referring_domains}`);
    if (result.numbers && result.numbers.length > 0) {
      console.log(`  Numbers found: ${result.numbers.join(', ')}`);
    }

    // Brief pause between checks
    await new Promise(r => setTimeout(r, 2000));

    // If we get blocked, note it and try a different approach
    if (result.page_text_snippet && result.page_text_snippet.includes('blocked')) {
      console.log('  BLOCKED - stopping Ahrefs checks');
      break;
    }
  }

  await browser.close();

  // Save results
  fs.writeFileSync('/Users/mike/Desktop/domainhunter/data/ahrefs_raw_results.json', JSON.stringify(results, null, 2));
  console.log(`\nDone. ${results.length} domains checked. Results saved.`);
}

main().catch(console.error);
