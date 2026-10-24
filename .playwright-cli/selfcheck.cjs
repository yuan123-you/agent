const { chromium } = require('C:/Users/游源/AppData/Roaming/npm/node_modules/@playwright/cli/node_modules/playwright-core');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Users/游源/AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  const apiCalls = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
  page.on('requestfailed', (r) => errors.push('REQFAIL ' + r.url().slice(0, 140) + ' :: ' + (r.failure() && r.failure().errorText)));
  page.on('response', (r) => { if (r.url().includes('/api/')) apiCalls.push(r.status() + ' ' + r.url().replace('https://aimall.novo.ccwu.cc', '')); });
  await page.goto('https://aimall.novo.ccwu.cc/aimall/', { waitUntil: 'networkidle', timeout: 60000 }).catch((e) => errors.push('GOTO ' + e.message.slice(0, 100)));
  await page.waitForTimeout(4000);
  const floors = await page.evaluate(() => document.querySelectorAll('.floor-grid').length);
  const seckill = await page.evaluate(() => !!document.getElementById('seckill-zone'));
  console.log('API_CALLS:', JSON.stringify(apiCalls, null, 1));
  console.log('JS_ERRORS:', JSON.stringify(errors, null, 1));
  console.log('DOM: floorGrids=' + floors + ' seckillZone=' + seckill);
  await page.screenshot({ path: '.playwright-cli/selfcheck.png' });
  await browser.close();
})();
