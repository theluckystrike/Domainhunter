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
    console.log(`Moz: Checking ${domain}...`);

    await page.goto(`https://moz.com/domain-analysis?site=${domain}`, {
      waitUntil: 'networkidle2',
      timeout: 30000
    });

    await new Promise(r => setTimeout(r, 5000));

    const metrics = await page.evaluate(() => {
      const allText = document.body.innerText;

      const daMatch = allText.match(/Domain Authority[^\d]*(\d+)/i);
      const paMatch = allText.match(/Page Authority[^\d]*(\d+)/i);
      const spamMatch = allText.match(/Spam Score[^\d]*(\d+)/i);
      const linkingMatch = allText.match(/Linking Domains[^\d]*(\d[\d,.]*)/i);
      const inboundMatch = allText.match(/Inbound Links[^\d]*(\d[\d,.]*)/i);
      const rankingMatch = allText.match(/Ranking Keywords[^\d]*(\d[\d,.]*)/i);

      // Try number-bearing elements
      const metricEls = document.querySelectorAll('[class*="metric"], [class*="score"], [class*="authority"], [class*="number"], [class*="stat"]');
      const metricTexts = Array.from(metricEls).map(n => `${n.className}: ${n.textContent.trim()}`).filter(t => t.length < 100).slice(0, 15);

      return {
        da: daMatch ? parseInt(daMatch[1]) : null,
        pa: paMatch ? parseInt(paMatch[1]) : null,
        spam_score: spamMatch ? parseInt(spamMatch[1]) : null,
        linking_domains: linkingMatch ? linkingMatch[1].replace(/,/g, '') : null,
        inbound_links: inboundMatch ? inboundMatch[1].replace(/,/g, '') : null,
        ranking_keywords: rankingMatch ? rankingMatch[1].replace(/,/g, '') : null,
        metric_elements: metricTexts,
        page_text_snippet: allText.substring(0, 800)
      };
    });

    return { domain, ...metrics, error: null };
  } catch (err) {
    return { domain, error: err.message, da: null };
  }
}

async function main() {
  console.log('Launching browser for Moz...');
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36');
  await page.setViewport({ width: 1280, height: 800 });

  const results = [];

  for (const domain of DOMAINS) {
    const result = await checkDomain(page, domain);
    results.push(result);
    console.log(`  DA: ${result.da}, Spam: ${result.spam_score}, Linking: ${result.linking_domains}`);

    await new Promise(r => setTimeout(r, 3000));

    // Stop if we get rate limited
    if (result.page_text_snippet && (result.page_text_snippet.includes('rate limit') || result.page_text_snippet.includes('too many'))) {
      console.log('  RATE LIMITED - stopping');
      break;
    }
  }

  await browser.close();

  fs.writeFileSync('/Users/mike/Desktop/domainhunter/data/moz_raw_results.json', JSON.stringify(results, null, 2));
  console.log(`\nDone. ${results.length} domains checked.`);
}

main().catch(console.error);
