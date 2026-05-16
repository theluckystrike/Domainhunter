const puppeteer = require('puppeteer');
const fs = require('fs');

const DOMAINS = [
  'fitocracy.com', 'devhub.io', 'apitools.com', 'codeguide.com',
  'bestdevtools.com', 'prompttools.com', 'codeparrot.ai', 'locale.ai',
  'fileforge.com', 'toolchain.io', 'freetail.com', 'tune.ai',
  'devtools.io', 'sitegrader.com', 'codetools.com', 'saasmetrics.com',
  'codingtools.com', 'codebench.com', 'codehelper.com', 'codeanalyzer.com',
  'imageeditor.net', 'aitoolkit.com', 'taskplanner.com',
  'mortgagecalc.com', 'seochecker.com'
];

async function checkDomain(page, domain) {
  try {
    console.log(`Checking ${domain}...`);

    await page.goto(`https://ahrefs.com/website-authority-checker?input=${domain}`, {
      waitUntil: 'networkidle2',
      timeout: 30000
    });

    // Wait for dynamic content
    await new Promise(r => setTimeout(r, 8000));

    // Take a screenshot for debugging first domain
    if (domain === 'fitocracy.com') {
      await page.screenshot({ path: '/Users/mike/Desktop/domainhunter/data/ahrefs_screenshot.png', fullPage: true });
    }

    const metrics = await page.evaluate((targetDomain) => {
      const allText = document.body.innerText;

      // The Ahrefs checker shows results in a specific pattern:
      // Domain Rating: XX
      // OR shows results after the domain name

      // Look for the result section that contains our domain
      const sections = allText.split('\n');
      let dr = null;
      let backlinks = null;
      let refDomains = null;
      let foundDomain = false;

      for (let i = 0; i < sections.length; i++) {
        const line = sections[i].trim();

        // Look for the domain we're checking
        if (line.includes(targetDomain)) {
          foundDomain = true;
        }

        // After finding domain, look for metrics
        if (foundDomain) {
          // DR is usually a number between 0-100
          if (line === 'Domain Rating (DR)' || line === 'Domain Rating') {
            // The number is usually in the preceding or following line
            const prevLine = sections[i-1] ? sections[i-1].trim() : '';
            const nextLine = sections[i+1] ? sections[i+1].trim() : '';
            if (/^\d+$/.test(prevLine) && parseInt(prevLine) <= 100) dr = parseInt(prevLine);
            else if (/^\d+$/.test(nextLine) && parseInt(nextLine) <= 100) dr = parseInt(nextLine);
          }

          if (line === 'Backlinks') {
            const prevLine = sections[i-1] ? sections[i-1].trim() : '';
            const nextLine = sections[i+1] ? sections[i+1].trim() : '';
            const parseLine = (l) => {
              const m = l.replace(/,/g, '').match(/^(\d+(?:\.\d+)?[KMB]?)$/);
              if (m) {
                let val = m[1];
                if (val.endsWith('K')) return parseFloat(val) * 1000;
                if (val.endsWith('M')) return parseFloat(val) * 1000000;
                if (val.endsWith('B')) return parseFloat(val) * 1000000000;
                return parseInt(val);
              }
              return null;
            };
            backlinks = parseLine(prevLine) || parseLine(nextLine);
          }

          if (line === 'Referring domains' || line === 'Referring Domains') {
            const prevLine = sections[i-1] ? sections[i-1].trim() : '';
            const nextLine = sections[i+1] ? sections[i+1].trim() : '';
            const parseLine = (l) => {
              const m = l.replace(/,/g, '').match(/^(\d+(?:\.\d+)?[KMB]?)$/);
              if (m) {
                let val = m[1];
                if (val.endsWith('K')) return parseFloat(val) * 1000;
                if (val.endsWith('M')) return parseFloat(val) * 1000000;
                return parseInt(val);
              }
              return null;
            };
            refDomains = parseLine(prevLine) || parseLine(nextLine);
          }
        }
      }

      // Also dump relevant chunks for debugging
      const resultSection = allText.indexOf(targetDomain);
      let debugText = '';
      if (resultSection >= 0) {
        debugText = allText.substring(Math.max(0, resultSection - 200), resultSection + 500);
      } else {
        // Find "Domain Rating" text
        const drIdx = allText.indexOf('Domain Rating');
        if (drIdx >= 0) {
          debugText = allText.substring(Math.max(0, drIdx - 200), drIdx + 300);
        }
      }

      return { dr, backlinks, refDomains, debugText: debugText.substring(0, 600) };
    }, domain);

    return { domain, ...metrics, error: null };
  } catch (err) {
    return { domain, error: err.message, dr: null, backlinks: null, refDomains: null };
  }
}

async function main() {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled']
  });

  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36');
  await page.setViewport({ width: 1280, height: 800 });

  // Accept cookies if prompted
  page.on('dialog', async dialog => await dialog.accept());

  const results = [];
  let blocked = false;

  for (const domain of DOMAINS) {
    if (blocked) {
      results.push({ domain, dr: null, backlinks: null, refDomains: null, error: 'SKIPPED_AFTER_BLOCK' });
      continue;
    }

    const result = await checkDomain(page, domain);
    results.push(result);
    console.log(`  DR: ${result.dr}, BL: ${result.backlinks}, RD: ${result.refDomains}`);
    if (result.debugText) {
      console.log(`  Debug: ${result.debugText.substring(0, 200)}`);
    }

    // Detect captcha/block
    if (result.debugText && (result.debugText.includes('CAPTCHA') || result.debugText.includes('blocked') || result.debugText.includes('security'))) {
      console.log('  BLOCKED - stopping');
      blocked = true;
    }

    await new Promise(r => setTimeout(r, 3000));
  }

  await browser.close();
  fs.writeFileSync('/Users/mike/Desktop/domainhunter/data/ahrefs_v2_results.json', JSON.stringify(results, null, 2));
  console.log(`\nDone. Saved ${results.length} results.`);
}

main().catch(console.error);
