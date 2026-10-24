const { chromium } = require('C:/Users/游源/AppData/Roaming/npm/node_modules/@playwright/cli/node_modules/playwright-core');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Users/游源/AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto('https://aimall.novo.ccwu.cc/aimall/', { waitUntil: 'networkidle', timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(4000);
  const info = await page.evaluate(() => {
    const q = (s) => document.querySelector(s);
    const rect = (s) => { const el = q(s); if (!el) return null; const r = el.getBoundingClientRect(); return { h: Math.round(r.height), top: Math.round(r.top) }; };
    const img = q('.floor-grid .el-image');
    return {
      heroZone: rect('.hero-zone'),
      banner: rect('.hero-banner'),
      firstFloor: rect('.floor'),
      floorGrid: rect('.floor-grid'),
      firstCard: rect('.floor-grid .product-card'),
      elImage: img ? { h: Math.round(img.getBoundingClientRect().height), innerImgLoaded: img.querySelector('img') ? img.querySelector('img').naturalWidth : 'no-img' } : null,
      imgSrcHead: img ? (img.querySelector('img') ? img.querySelector('img').src.slice(0, 60) : img.getAttribute('src') ? img.getAttribute('src').slice(0, 60) : 'none') : null,
      bodyH: document.body.scrollHeight,
    };
  });
  console.log(JSON.stringify(info, null, 1));
  await browser.close();
})();
