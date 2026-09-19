#!/usr/bin/env python3
"""Exercise the real Vue dialogs in Chromium against deterministic API fixtures.

Run with the frontend Vite dev server running; no payment requests reach a backend.
"""
import argparse
import json
import re
import urllib.request
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, expect


HARNESS = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="/api/cdn/zilla-slab"><link rel="stylesheet" href="/api/cdn/noto-sans-sc"></head>
<body><div id="fixture"></div><script type="module">
import {createApp, h, ref} from '/node_modules/.vite/deps/vue.js';
import {createPinia} from '/node_modules/.vite/deps/pinia.js';
import Swal from '/node_modules/.vite/deps/sweetalert2.js';
import AppModal from '/src/components/common/AppModal.vue';
import PaymentModal from '/src/components/main/PaymentModal.vue';
import OrdersModal from '/src/components/main/OrdersModal.vue';
import '/src/assets/style.css';
window.Swal = Swal;
const opened = ref('');
const initial = ref(true);
const nested = ref(false);
window.fixture = {opened, initial, nested};
const app = createApp({setup: () => () => h('main', [
 h('header', {class: 'mobile-header'}, '移动导航'),
 h(AppModal, {visible: initial.value, title: '初始弹窗', onClose: () => initial.value = false}, () => '初始内容'),
 h(AppModal, {visible: opened.value === 'generic', title: '外层弹窗', width: 'max-w-2xl', onClose: () => opened.value = ''}, () => [
   h('input', {class: 'input-field', placeholder: '输入内容'}),
   h('button', {onClick: () => nested.value = true}, '打开内层'),
   h('button', {onClick: () => Swal.fire({title: '确认操作', confirmButtonText: '确定'})}, '显示确认'),
 ]),
 h(AppModal, {visible: nested.value, title: '内层弹窗', onClose: () => nested.value = false}, () => '内层内容'),
 h(PaymentModal, {visible: opened.value === 'payment', onClose: () => opened.value = ''}),
 h(OrdersModal, {visible: opened.value === 'orders', onClose: () => opened.value = ''}),
 h('nav', {class: 'mobile-bottom-nav'}, '底部导航'),
])});
app.use(createPinia()); app.mount('#fixture'); window.fixture.ready = true;
</script></body></html>"""


def run(vue_url, output_dir):
    failures = []
    with urllib.request.urlopen(vue_url.rstrip('/') + '/src/main.js') as response:
        entry = response.read().decode('utf-8')
    harness = HARNESS
    for dependency in ('vue', 'pinia', 'sweetalert2'):
        resolved = re.search(r'[\"\'](/node_modules/\.vite/deps/' + dependency + r'\.js[^\"\']*)', entry)
        if resolved:
            harness = harness.replace('/node_modules/.vite/deps/' + dependency + '.js', resolved[1])
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for mobile in (False, True):
            context = browser.new_context(viewport={"width": 390 if mobile else 1440, "height": 844 if mobile else 900})
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            enabled = ['wxpay']
            requests = []

            def api(route):
                if '/api/cdn/' in route.request.url:
                    route.continue_()
                    return
                requests.append(route.request.url)
                if '/methods_config' in route.request.url:
                    body = {"success": True, "methods": {"wxpay": {"name": "微信支付"}, "disabled": {"name": "已停用方式"}}, "enabled_methods": enabled.copy()}
                elif '/payment/config' in route.request.url:
                    body = {"success": True, "enabled_payment_methods": enabled.copy()}
                elif '/payment/orders' in route.request.url:
                    body = {"success": True, "orders": [], "total": 0}
                else:
                    body = {"success": False, "message": "Unexpected fixture request"}
                route.fulfill(json=body)

            page.route('**/api/**', api)
            page.route('**/__parity_dialogs__', lambda route: route.fulfill(content_type='text/html; charset=utf-8', body=harness))
            page.goto(vue_url.rstrip('/') + '/__parity_dialogs__')
            page.wait_for_function('window.fixture?.ready')
            page.evaluate('document.fonts.ready')
            page.evaluate('(mobile) => document.body.classList.toggle("mobile-mode", mobile)', mobile)

            def check(name, action):
                try:
                    action()
                    print(f'PASS {"mobile" if mobile else "desktop"}: {name}')
                except Exception as error:
                    failures.append(f'{"mobile" if mobile else "desktop"}: {name}: {str(error)[:300]}')
                    print('FAIL ' + failures[-1])

            check('initially visible dialog isolates map', lambda: expect(page.locator('body')).to_have_class(__import__('re').compile(r'.*modal-visible.*')))
            page.evaluate("window.fixture.initial.value = false; window.fixture.opened.value = 'generic'")
            panel = page.locator('.modal-content').last
            expect(panel).to_be_visible()
            check('content accepts pointer input', lambda: panel.get_by_placeholder('输入内容').click(timeout=1500))
            bounds = panel.bounding_box()
            check('requested desktop width / mobile viewport fit', lambda: assert_width(bounds, mobile))
            check('modal overlays mobile navigation', lambda: assert_true(page.evaluate("document.elementFromPoint(10, 20).closest('[data-modal-open]') !== null"), 'navigation is above modal'))
            page.evaluate('window.fixture.nested.value = true')
            expect(page.locator('.modal-content')).to_have_count(2)
            page.evaluate('window.fixture.nested.value = false')
            check('closing nested dialog keeps parent isolation', lambda: expect(page.locator('body')).to_have_class(__import__('re').compile(r'.*modal-visible.*')))
            page.evaluate("void window.Swal.fire({title:'确认操作', confirmButtonText:'确定'})")
            check('confirmation stays above parent modal', lambda: page.get_by_role('button', name='确定', exact=True).click(timeout=1500))
            page.evaluate('window.Swal.close()')
            page.evaluate("document.body.classList.add('dark-mode')")
            check('dark input retains legacy foreground', lambda: assert_true(panel.locator('input').evaluate("el => getComputedStyle(el).color === 'rgb(229, 231, 235)'"), 'dark foreground differs'))
            page.evaluate("document.body.classList.remove('dark-mode'); window.fixture.opened.value = 'payment'")
            expect(page.get_by_text('微信支付', exact=True)).to_be_visible()
            check('disabled payment method is hidden', lambda: expect(page.get_by_text('已停用方式', exact=True)).to_have_count(0))
            check('payment amount is editable', lambda: page.locator('input[type=number]').click(timeout=1500))
            page.locator('input[type=number]').blur()
            page.mouse.move(0, 0)
            output_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output_dir / f'payment-{"mobile" if mobile else "desktop"}.png'))
            page.get_by_role('dialog', name='在线支付').screenshot(path=str(output_dir / f'vue-payment-{"mobile" if mobile else "desktop"}.png'))
            metrics = page.get_by_role('dialog', name='在线支付').evaluate("""root => [root, ...root.querySelectorAll('h3,label,input,button')].map(el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el); return {tag:el.tagName,id:el.id,text:el.textContent.trim().slice(0,30),x:r.x,y:r.y,w:r.width,h:r.height,font:s.font,color:s.color,padding:s.padding,border:s.border,bg:s.background}})""")
            (output_dir / f'vue-payment-{"mobile" if mobile else "desktop"}-metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
            page.evaluate("window.fixture.opened.value = ''")
            expect(page.locator('.modal-content')).to_have_count(0)
            enabled.clear()
            page.evaluate("window.fixture.opened.value = 'payment'")
            check('explicit empty enabled list stays empty', lambda: expect(page.get_by_text('暂无可用的支付方式', exact=True)).to_be_visible(timeout=2000))
            check('cannot submit with no enabled methods', lambda: expect(page.locator('.modal-content button').last).to_be_disabled())
            page.evaluate("window.fixture.opened.value = 'orders'")
            expect(page.get_by_text('暂无订单', exact=True)).to_be_visible()
            if not mobile:
                check('orders retain legacy 672px width', lambda: assert_true(page.get_by_role('dialog', name='我的订单').bounding_box()['width'] >= 660, 'order list too narrow'))
            page.evaluate("window.fixture.opened.value = ''")
            check('last close clears map isolation', lambda: expect(page.locator('body')).not_to_have_class(__import__('re').compile(r'.*modal-visible.*')))
            check('no Vue runtime errors', lambda: assert_true(not errors, str(errors)))
            context.close()
        browser.close()
    for failure in failures:
        print('FAIL ' + failure)
    return len(failures)


def assert_true(value, message):
    assert value, message


def assert_width(bounds, mobile):
    assert bounds is not None
    if mobile:
        assert bounds['x'] >= 16 and bounds['x'] + bounds['width'] <= 374, bounds
    else:
        assert 660 <= bounds['width'] <= 680, bounds


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vue-url', default='http://127.0.0.1:5173')
    parser.add_argument('--output-dir', type=Path, default=Path('output/ui-parity-dialogs'))
    args = parser.parse_args()
    raise SystemExit(1 if run(args.vue_url, args.output_dir) else 0)
