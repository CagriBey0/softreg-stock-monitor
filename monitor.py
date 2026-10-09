"""Read-only public Softreg vendor monitor. Uses a normal Chromium browser; no access-control bypass."""
import json, re, time, os
from pathlib import Path
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode, urljoin

BASE = 'https://www.accsmarket.com'
CATALOG = BASE + '/en/catalog/gmail/avtoregi-24'

class Catalog(HTMLParser):
    def __init__(self):
        super().__init__(); self.items = {}; self.current = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'div' and 'soc-body' in a.get('class', '').split():
            self.current = a.get('data-id')
            if self.current:
                self.items[self.current] = {'total': int(a['data-qty']), 'url': None}
        if tag == 'a' and self.current and '/en/item/' in a.get('href', ''):
            self.items[self.current]['url'] = urljoin(BASE, a['href'])

class Vendors(HTMLParser):
    def __init__(self):
        super().__init__(); self.inside = False; self.rows = {}
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id') == 'item_partners': self.inside = True
        if self.inside and tag == 'li' and a.get('data-id'):
            pid = a['data-id']
            self.rows[pid] = {'stock': int(a['data-qty']), 'price': float(a['data-price'].replace(',', '.'))}
    def handle_endtag(self, tag):
        if tag == 'ul': self.inside = False

def changes(old, new):
    result = []
    for key in sorted(old.keys() | new.keys()):
        if key not in old: result.append({'key': key, 'type': 'added', 'new': new[key]})
        elif key not in new: result.append({'key': key, 'type': 'missing', 'old': old[key]})
        elif any(old[key][f] != new[key][f] for f in ('stock', 'price')):
            result.append({'key': key, 'type': 'changed', 'old': old[key], 'new': new[key]})
    return result

def main():
    from playwright.sync_api import sync_playwright
    now = datetime.now(timezone.utc).isoformat()
    rows, errors = {}, []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(locale='en-US')
        page.set_default_timeout(20000)
        response = page.goto(CATALOG, wait_until='load')
        if not response or response.status >= 400:
            raise RuntimeError('Catalog access failed; baseline retained')
        catalog = Catalog(); catalog.feed(page.content())
        if not catalog.items: raise RuntimeError('No catalog items; baseline retained')
        active = [(item, meta) for item, meta in catalog.items.items() if meta['total'] > 0]
        print(f"Catalog: {len(catalog.items)} products, {len(active)} in stock", flush=True)
        for index, (item, meta) in enumerate(active):
            try:
                page.wait_for_function("typeof window.orders !== 'undefined' && typeof window.orders.basket === 'function'")
                consent = page.get_by_role('button', name='Accept', exact=True)
                if consent.is_visible(): consent.click()
                with page.expect_response(lambda response: '/req/deferred.php' in response.url and 'buy_dialog' in (response.request.post_data or '')) as result:
                    page.locator('button.basket-button[data-id="' + item + '"]').click()
                response = result.value
                if response.status != 200:
                    raise RuntimeError(f'Vendor request HTTP {response.status}; stopping')
                payload = response.json()
                if payload.get('code') != 0:
                    raise RuntimeError('Vendor response rejected: ' + str(payload.get('errormsg', payload.get('code'))))
                vendors = Vendors(); vendors.feed(payload.get('content', ''))
                if not vendors.rows: raise ValueError('Successful response had no vendor rows')
                for pid, value in vendors.rows.items():
                    rows[item + ':' + pid] = dict(value, url=meta['url'])
                page.locator('#buy_dialog').wait_for(state='visible')
                page.keyboard.press('Escape')
                page.locator('#buy_dialog').wait_for(state='hidden')
            except Exception as exc:
                errors.append({'item':item, 'error':type(exc).__name__, 'detail':str(exc)[:1500]})
                print(f'Item {item}: {exc}', flush=True)
                print(page.locator('body').inner_text()[-2500:], flush=True)
                # Stop after repeated failures rather than hammering a blocked site.
                if isinstance(exc, RuntimeError) or len(errors) >= 3: break
                page.goto(CATALOG, wait_until='load')
            print(f"Scanned {index + 1}/{len(active)}; errors {len(errors)}", flush=True)
            time.sleep(2)
        browser.close()
    directory = Path(os.getenv('STATE_DIR', 'state')); directory.mkdir(exist_ok=True)
    last = directory / 'latest.json'
    old = json.loads(last.read_text()) if last.exists() else None
    report = {'time':now, 'items':len(catalog.items), 'vendor_rows':len(rows), 'active_items':len(active), 'catalog':catalog.items, 'errors':errors}
    # Only compare and replace baseline when the entire scan succeeded.
    if errors:
        report['status'] = 'incomplete'; report['changes'] = []
        report['partial_rows'] = rows
    else:
        if old and len(catalog.items) < old['items'] * 0.8:
            raise RuntimeError('Catalog shrank by over 20%; manual review needed; baseline retained')
        report['status'] = 'complete'
        report['changes'] = changes(old['rows'], rows) if old else []
        report['baseline'] = old is None
        last.write_text(json.dumps({'time':now,'items':len(catalog.items),'rows':rows}, indent=2))
    lines = ["# Softreg stok raporu", "", f"Ölçüm başlangıcı (UTC): {now}", "",
             f"Katalog: {len(catalog.items)} ürün; stoklu: {len(active)}; okunan satıcı satırı: {len(rows)}; hata: {len(errors)}.", "",
             "Stok azalması kesin satış anlamına gelmez. Görünmeyen satıcı, sıfır stok olarak yorumlanmaz.", "",
             "## Değişiklikler", ""]
    if not old: lines.append("İlk tam ölçüm karşılaştırma için başlangıç kaydıdır.")
    if errors: lines.append("Eksik tarama: önceki tam kayıt korundu; değişiklik hesabı yapılmadı.")
    for delta in report['changes']:
        before, after = delta.get('old'), delta.get('new')
        def describe(value):
            return f"{value['stock']} adet / ${value['price']}" if value else "görünmüyor"
        lines.append(f"- {delta['key']}: {describe(before)} → {describe(after)}")
    lines += ["", "## Okunan satıcılar", "", "| Ürün | Partner | Stok | Alıcı fiyatı (USD) |", "|---|---|---:|---:|"]
    for key, row in sorted(rows.items()):
        item, partner = key.split(':')
        lines.append(f"| [{item}]({row['url']}) | {partner} | {row['stock']} | {row['price']} |")
    (directory / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    (directory / 'report.json').write_text(json.dumps(report, indent=2))
    with (directory / 'history.jsonl').open('a') as stream:
        stream.write(json.dumps(report) + '\n')
    summary = f"Softreg: {len(catalog.items)} products, {len(rows)} vendor rows, {len(errors)} errors, {len(report['changes'])} changes."
    print(summary)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(summary + '\n\nStock reductions are not proof of sales. See state/report.json for details.\n')
    if errors: raise RuntimeError('Incomplete scan; previous baseline retained')

if __name__ == '__main__': main()
