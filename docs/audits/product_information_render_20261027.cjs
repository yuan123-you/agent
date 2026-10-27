// Offline rendering of the real product-spec template. No browser or API calls.
// Run: node docs/audits/product_information_render_20261027.cjs
const {createRequire} = require('node:module');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const req = createRequire(path.join(root, 'frontend/package.json'));
const {compile} = req('@vue/compiler-ssr');
const {createSSRApp} = req('vue');
const {renderToString} = req('vue/server-renderer');
const source = fs.readFileSync(path.join(root, 'frontend/src/views/ProductDetailView.vue'), 'utf8');
const template = source.match(/<el-descriptions :column[\s\S]*?<\/el-descriptions>/)[0];
const {code} = compile(template, {mode: 'function'});
const ssrRender = new Function('require', code)(req);
const app = createSSRApp({
  data: () => ({isMobile: false, product: {name: '食用面包', category: 'FOOD'}, specs: []}),
  methods: {categoryName: () => '食品'}, ssrRender,
});
app.config.warnHandler = () => {};
// Lightweight wrappers retain real template expressions but avoid UI-library setup.
for (const name of ['el-descriptions', 'el-descriptions-item']) {
  app.component(name, {props: ['label', 'column', 'border'], template: '<div><slot /></div>'});
}
renderToString(app).then(html => {
  const text = html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
  console.log('Rendered a FOOD product with no supplied material, origin, batch or warranty fields:');
  console.log(text);
  const unsupported = ['阳极氧化铝合金', '2026年最新生产', '12 个月官方正品联保'];
  const injected = unsupported.filter(claim => text.includes(claim));
  console.log(injected.length ? `FAIL: ${injected.length} unsupported factual claims inserted` : 'PASS');
  process.exitCode = injected.length ? 1 : 0;
}).catch(error => {console.error(error); process.exitCode = 2;});
