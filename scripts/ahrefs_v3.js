const puppeteer = require('puppeteer');
const fs = require('fs');

const DOMAINS = [
  'fitocracy.com', 'devhub.io', 'apitools.com', 'codeparrot.ai',
  'locale.ai', 'tune.ai', 'freetail.com', 'codeguide.com',
  'bestdevtools.com', 'prompttools.com', 'fileforge.com', 'toolchain.io',
  'devtools.io', 'mortgagecalc.com', 'seochecker.com',
  'imageeditor.net', 'codetools.com', 'codehelper.com', 'aitoolkit.com',
  'codebench.com', 'sitegrader.com', 'saasmetrics.com', 'codingtools.com',
  'codeanalyzer.com', 'taskplanner.com'
];

async function checkDomain(page, domain, index) {
  try {
    console.log(`[${index+1}/${DOMAINS.length}] Checking ${domain}...`);

    // Go to the authority checker page
    await page.goto('https://ahrefs.com/website-authority-checker', {
      waitUntil: 'networkidle2',
      timeout: 30000
    });

    await new Promise(r => setTimeout(r, 2000));

    // Find the input field and type the domain
    const inputSelector = 'input[type="text"], input[name="input"], input[placeholder*="domain"], input[placeholder*="URL"]';
    await page.waitForSelector(inputSelector, { timeout: 10000 });

    // Clear existing text and type domain
    await page.click(inputSelector, { clickCount: 3 });
    await page.type(inputSelector, domain);

    await new Promise(r => setTimeout(r, 500));

    // Find and click the submit button
    const submitClicked = await page.evaluate(() => {
      // Try multiple selectors for the submit button
      const buttons = document.querySelectorAll('button[type="submit"], button');
      for (const btn of buttons) {
        const text = btn.textContent.trim().toLowerCase();
        if (text.includes('check') || text.includes('analyze') || text.includes('authority')) {
          btn.click();
          return true;
        }
      }
      // Try form submission
      const form = document.querySelector('form');
      if (form) {
        form.submit();
        return true;
      }
      return false;
    });

    if (!submitClicked) {
      // Try pressing Enter on the input
      await page.keyboard.press('Enter');
    }

    // Wait for results to load
    await new Promise(r => setTimeout(r, 10000));

    // Take screenshot of first 3 domains for debugging
    if (index < 3) {
      await page.screenshot({
        path: `/Users/mike/Desktop/domainhunter/data/ahrefs_v3_${domain.replace(/\./g, '_')}.png`,
        fullPage: true
      });
    }

    // Extract results
    const metrics = await page.evaluate((targetDomain) => {
      const allText = document.body.innerText;
      const lines = allText.split('\n').map(l => l.trim()).filter(l => l.length > 0);

      // Debug: dump all lines with numbers
      const numberLines = lines.filter(l => /\d/.test(l) && l.length < 50);

      // Look for the results pattern
      let dr = null;
      let backlinks = null;
      let refDomains = null;
      let dofollow = null;

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].toLowerCase();
        const prev = i > 0 ? lines[i-1].trim() : '';
        const next = i < lines.length - 1 ? lines[i+1].trim() : '';

        if (line.includes('domain rating')) {
          // Check adjacent lines for the number
          for (let j = Math.max(0, i-3); j <= Math.min(lines.length-1, i+3); j++) {
            const val = lines[j].trim();
            if (/^\d{1,2}$/.test(val) && parseInt(val) <= 100 && j !== i) {
              dr = parseInt(val);
              break;
            }
          }
        }

        if (line === 'backlinks' || line.includes('total backlinks')) {
          for (let j = Math.max(0, i-2); j <= Math.min(lines.length-1, i+2); j++) {
            const val = lines[j].trim().replace(/,/g, '');
            if (/^\d+$/.test(val) && j !== i) {
              backlinks = parseInt(val);
              break;
            }
            // Handle K/M notation
            const km = val.match(/^([\d.]+)([KMB])$/i);
            if (km) {
              const multiplier = { K: 1000, M: 1000000, B: 1000000000 }[km[2].toUpperCase()];
              backlinks = Math.round(parseFloat(km[1]) * multiplier);
              break;
            }
          }
        }

        if (line === 'referring domains' || line.includes('referring domain')) {
          for (let j = Math.max(0, i-2); j <= Math.min(lines.length-1, i+2); j++) {
            const val = lines[j].trim().replace(/,/g, '');
            if (/^\d+$/.test(val) && j !== i) {
              refDomains = parseInt(val);
              break;
            }
            const km = val.match(/^([\d.]+)([KMB])$/i);
            if (km) {
              const multiplier = { K: 1000, M: 1000000, B: 1000000000 }[km[2].toUpperCase()];
              refDomains = Math.round(parseFloat(km[1]) * multiplier);
              break;
            }
          }
        }

        if (line === 'dofollow' || line.includes('dofollow links')) {
          for (let j = Math.max(0, i-2); j <= Math.min(lines.length-1, i+2); j++) {
            const val = lines[j].trim().replace(/,/g, '');
            if (/^\d+$/.test(val) && j !== i) {
              dofollow = parseInt(val);
              break;
            }
          }
        }
      }

      // Check for captcha/blocked
      const blocked = allText.includes('CAPTCHA') || allText.includes('Verify you are human') || allText.includes('blocked');

      return {
        dr, backlinks, refDomains, dofollow,
        blocked,
        numberLines: numberLines.slice(0, 20),
        url: window.location.href
      };
    }, domain);

    return { domain, ...metrics, error: null };
  } catch (err) {
    return { domain, error: err.message, dr: null, backlinks: null, refDomains: null };
  }
}

async function main() {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled',
           '--window-size=1280,800']
  });

  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36');
  await page.setViewport({ width: 1280, height: 800 });

  // Intercept API responses
  const apiResponses = {};
  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('authority') || url.includes('backlink') || url.includes('dr') || url.includes('rating') || url.includes('v4/') || url.includes('api/')) {
      try {
        const body = await response.text();
        if (body.length < 10000 && body.includes('{')) {
          apiResponses[url] = body;
          console.log(`  API Response from: ${url.substring(0, 100)}`);
          console.log(`  Body preview: ${body.substring(0, 200)}`);
        }
      } catch (e) {}
    }
  });

  const results = [];
  let blocked = false;

  for (let i = 0; i < DOMAINS.length; i++) {
    if (blocked) {
      results.push({ domain: DOMAINS[i], dr: null, error: 'SKIPPED_BLOCKED' });
      continue;
    }

    const result = await checkDomain(page, DOMAINS[i], i);
    results.push(result);
    console.log(`  => DR: ${result.dr}, BL: ${result.backlinks}, RD: ${result.refDomains}`);

    if (result.blocked) {
      console.log('  CAPTCHA DETECTED - stopping');
      blocked = true;
    }

    // Save API responses for this domain
    result.apiResponses = { ...apiResponses };

    await new Promise(r => setTimeout(r, 4000));
  }

  await browser.close();

  // Save results
  fs.writeFileSync('/Users/mike/Desktop/domainhunter/data/ahrefs_v3_results.json', JSON.stringify(results, null, 2));
  console.log(`\nSaved ${results.length} results.`);

  // Print summary
  const verified = results.filter(r => r.dr !== null);
  console.log(`\nVerified: ${verified.length}/${results.length}`);
  for (const r of verified) {
    console.log(`  ${r.domain}: DR ${r.dr}, BL: ${r.backlinks}, RD: ${r.refDomains}`);
  }
}

main().catch(console.error);
