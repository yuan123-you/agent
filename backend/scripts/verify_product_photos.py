"""Public, read-only production acceptance test for real product photographs.

Run before and after catalog cutover. Validates identity/provenance and actual
raster bytes instead of accepting a successful SVG placeholder request.
"""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
import argparse
import json
from pathlib import Path
from PIL import Image
import requests


def verify(base_url, manifest):
    expected = {p['source_product_id']: p for p in manifest}
    results = []
    def check(name, passed):
        results.append({'check': name, 'passed': bool(passed)})
    def api(path, **params):
        response = requests.get(base_url.rstrip('/') + '/api/v1' + path, params=params, timeout=40)
        response.raise_for_status(); body = response.json()
        if body.get('code') != 0: raise ValueError('API rejected read: ' + path)
        return body['data']
    first = api('/products', page=1, size=100)
    goods = list(first['records'])
    for page in range(2, (first['total'] + 99) // 100 + 1):
        goods.extend(api('/products', page=page, size=100)['records'])
    check('all known demonstration goods retired', not any(1 <= p['id'] <= 512 for p in goods))
    actual = {p.get('sourceProductId'): p for p in goods if p.get('sourceName') == 'www.apple.com.cn'}
    check('every manifest SKU appears exactly once', len(actual) == len(expected) and set(actual) == set(expected))
    check('no SVG category placeholders in storefront', not any(str(p.get('imageUrl', '')).startswith('data:image/svg') for p in goods))
    def product_check(item):
        sku, p = item
        if sku not in actual:return [{'check': 'missing SKU ' + sku, 'passed': False}]
        live = actual[sku]; checks = []
        def local(name, ok):checks.append({'check': sku + ': ' + name, 'passed': bool(ok)})
        try:
            detail = api('/products/' + str(live['id']))
            local('name, source, price, category and picture match the same SKU', all([
                detail.get('name') == p['name'], detail.get('sourceUrl') == p['source_url'],
                detail.get('originalImageUrl') == p['original_image_url'],
                detail.get('imageSha256') == p['image_sha256'], detail.get('imageUrl') == p['image_url'],
                detail.get('currency') == 'CNY', float(detail.get('price', 0)) == float(p['price']),
                detail.get('category') == p['category'], detail.get('categoryId') is not None,
                detail.get('brandId') is not None, detail.get('simulatedCommerceFields') is True,
                json.loads(detail.get('specs') or '{}').get('产品型号') == sku,
            ]))
            response = requests.get(base_url.rstrip('/') + p['image_url'], timeout=40)
            response.raise_for_status()
            local('photo bytes match source-derived SHA256', sha256(response.content).hexdigest() == p['image_sha256'])
            with Image.open(BytesIO(response.content)) as image:
                image.load()
                local('decodable real raster, not SVG or HTML', image.format in {'WEBP', 'JPEG', 'PNG'} and min(image.size) >= 100 and response.headers.get('Content-Type','').startswith('image/'))
        except Exception as exc:
            local('HTTP/API/photo verification ' + type(exc).__name__, False)
        return checks
    with ThreadPoolExecutor(max_workers=3) as pool:
        for checks in pool.map(product_check, expected.items()):results.extend(checks)
    for category in sorted({p['category'] for p in manifest}):
        page = api('/products', category=category, size=100)
        check('category filter ' + category, page['total'] > 0 and all(p['category'] == category for p in page['records']))
    sample = next((p for p in goods if p.get('sourceProductId') in expected), None)
    if sample:
        found = api('/products', keyword=sample['name'], size=100)
        check('search finds the same real product ID', any(p['id'] == sample['id'] for p in found['records']))
    return {'products_expected': len(expected), 'products_in_storefront': len(goods),
            'checks': len(results), 'passed': sum(p['passed'] for p in results),
            'failed': [p for p in results if not p['passed']], 'results': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    rows = [json.loads(l) for l in Path(args.manifest).read_text(encoding='utf-8').splitlines()]
    report = verify(args.base_url, rows)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'results'}, ensure_ascii=False))
    raise SystemExit(bool(report['failed']))
