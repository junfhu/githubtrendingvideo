"""Take 2 viewport-height screenshots of a GitHub repo page via CDP.

Shot 1 (top):    page header + star button area
Shot 2 (intro):  README / introduction section below the fold
"""
import json, base64, time, sys, os
from websocket import create_connection
import urllib.request

DEBUG_PORT = 9222
VIEWPORT_W = 1920
VIEWPORT_H = 1080
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(SKILL_DIR, "remotion", "public")


def cdp_screenshots(url, base_name):
    """Take two screenshots: top area and intro/README area."""
    tabs = json.loads(urllib.request.urlopen(f"http://localhost:{DEBUG_PORT}/json").read())
    tab = next((t for t in tabs if t['type'] == 'page'), tabs[0])
    ws_url = tab['webSocketDebuggerUrl']
    ws = create_connection(ws_url, timeout=15)

    def send(method, params=None):
        ws.send(json.dumps({'id': 1, 'method': method, 'params': params or {}}))
        while True:
            resp = json.loads(ws.recv())
            if resp.get('id') == 1:
                return resp

    # Set viewport
    send('Emulation.setDeviceMetricsOverride', {
        'width': VIEWPORT_W, 'height': VIEWPORT_H,
        'deviceScaleFactor': 1, 'mobile': False
    })

    print(f"Navigating to {url}...")
    send('Page.enable')
    send('Page.navigate', {'url': url})
    time.sleep(5)

    # Remove nav + sidebars
    print("Hiding nav and sidebars...")
    send('Runtime.evaluate', {'expression': '''
    var toHide = [
        "header.AppHeader", "header.Header-old", ".Layout-sidebar",
        "footer", "[data-target='recent-activity-sidebar']"
    ];
    toHide.forEach(function(sel) {
        try { document.querySelectorAll(sel).forEach(function(el) { el.style.display = 'none'; }); } catch(e) {}
    });
    document.body.style.background = '#ffffff';
    window.scrollTo(0, 0);
    '''})
    time.sleep(1)

    # Locate star element AND inject red ring — single JS call for reliability
    print("Locating star button and adding red ring...")
    pos = send('Runtime.evaluate', {'expression': '''
    (function() {
        // GitHub now uses <a> tags for star/fork, not <button>
        var star = null;

        // Strategy 1: find <a> or <button> containing span.d-inline with text 'Star' or 'Unstar'
        var spans = document.querySelectorAll('span.d-inline');
        for (var i = 0; i < spans.length; i++) {
            var t = spans[i].textContent.trim();
            if (t === 'Star' || t === 'Unstar') {
                star = spans[i].closest('a, button, form');
                break;
            }
        }

        // Strategy 2: find <a> whose text includes 'Star' (the whole star button link)
        if (!star) {
            var links = document.querySelectorAll('a.btn-sm.btn');
            for (var j = 0; j < links.length; j++) {
                if (links[j].textContent.includes('Star')) {
                    star = links[j]; break;
                }
            }
        }

        // Strategy 3: any button with 'star' in aria-label
        if (!star) {
            var btns = document.querySelectorAll('button[aria-label*="star" i], button[aria-label*="Star"], a[aria-label*="star" i]');
            if (btns.length > 0) star = btns[0];
        }

        if (!star) return JSON.stringify({error: 'star button not found'});

        var r = star.getBoundingClientRect();

        // Inject red ring overlay
        var ring = document.createElement('div');
        ring.id = '__star_red_ring__';
        ring.style.cssText =
            'position:fixed;z-index:99999;pointer-events:none;' +
            'left:' + (r.x - 5) + 'px;top:' + (r.y - 5) + 'px;' +
            'width:' + (r.width + 10) + 'px;height:' + (r.height + 10) + 'px;' +
            'border:3px solid #ff3333;border-radius:8px;' +
            'box-shadow:0 0 16px rgba(255,51,51,0.6),0 0 32px rgba(255,51,51,0.3);' +
            'background:transparent;';
        document.body.appendChild(ring);

        // Also highlight the star element itself
        star.style.outline = '3px solid #ff3333';
        star.style.outlineOffset = '2px';
        star.style.borderRadius = '6px';
        star.style.boxShadow = '0 0 16px rgba(255,51,51,0.5)';

        return JSON.stringify({x: r.x, y: r.y, w: r.width, h: r.height, vw: window.innerWidth, vh: window.innerHeight});
    })()
    '''})
    try:
        star_pos = json.loads(pos['result']['result']['value'])
        print(f"Star button: {star_pos}")
    except Exception as e:
        star_pos = None
        print(f"Could not locate star button: {e}")
        print(f"Raw response: {json.dumps(pos, indent=2)[:500]}")

    # Screenshot 1: Top area (header + stars)
    print("Capturing screenshot 1 (top)...")
    send('Runtime.evaluate', {'expression': 'window.scrollTo(0, 0);'})
    time.sleep(0.5)
    result1 = send('Page.captureScreenshot', {'format': 'png', 'fromSurface': True})

    top_name = f"{base_name}_top.png"
    top_path = os.path.join(OUTPUT_DIR, top_name)
    with open(top_path, 'wb') as f:
        f.write(base64.b64decode(result1['result']['data']))
    print(f"Screenshot 1 saved: {top_path}")

    # Remove red ring before taking intro screenshot
    send('Runtime.evaluate', {'expression': '''
    var ring = document.getElementById('__star_red_ring__');
    if (ring) ring.remove();
    '''})
    time.sleep(0.3)

    # Screenshot 2: Scroll README to viewport top, clip using page coordinates
    print("Capturing README...")
    dims = send('Runtime.evaluate', {'expression': '''
    (function() {
        var target = document.querySelector('article.markdown-body')
                  || document.querySelector('#readme')
                  || document.querySelector('[data-target=\"readme-toc\"]');
        if (!target) target = document.querySelector('.Box-row') || document.querySelector('main');
        if (!target) return JSON.stringify({pageX: 0, pageY: 600, w: 900, h: 3000});

        // Scroll README to top of viewport
        var rect = target.getBoundingClientRect();
        window.scrollTo(0, window.scrollY + rect.top);

        // Re-measure — use PAGE coordinates (scrollY + viewport-relative rect)
        rect = target.getBoundingClientRect();
        return JSON.stringify({
            pageX: Math.round(window.scrollX + rect.left),
            pageY: Math.round(window.scrollY + rect.top),
            w: Math.round(rect.width),
            h: Math.max(target.scrollHeight, Math.round(rect.height), 600)
        });
    })()
    '''})
    try:
        info = json.loads(dims['result']['result']['value'])
        px = info['pageX']
        py = info['pageY']
        pw = info['w']
        ph = min(info['h'] + 20, 12000)
        print(f"README page: x={px}, y={py}, w={pw}, h={ph}")
    except:
        px, py, pw, ph = 378, 2496, 838, 6000
    time.sleep(0.5)

    # Tall viewport so full README is rendered, keep 1920 width
    send('Emulation.setDeviceMetricsOverride', {
        'width': 1920,
        'height': ph + 40,
        'deviceScaleFactor': 1,
        'mobile': False
    })
    time.sleep(0.5)

    print(f"Capturing intro: clip(x={px}, y={py}, w={pw}, h={ph})")
    result2 = send('Page.captureScreenshot', {
        'format': 'png',
        'fromSurface': True,
        'clip': {'x': px, 'y': py, 'width': pw, 'height': ph, 'scale': 1}
    })

    intro_name = f"{base_name}_intro.png"
    intro_path = os.path.join(OUTPUT_DIR, intro_name)
    with open(intro_path, 'wb') as f:
        f.write(base64.b64decode(result2['result']['data']))
    print(f"Screenshot 2 saved: {intro_path}")

    # Reset viewport
    send('Emulation.setDeviceMetricsOverride', {
        'width': VIEWPORT_W, 'height': VIEWPORT_H,
        'deviceScaleFactor': 1, 'mobile': False
    })

    ws.close()
    return top_name, intro_name, star_pos


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python screenshot_cdp.py <github-url> <base-name>")
        sys.exit(1)

    url = sys.argv[1]
    base_name = sys.argv[2] if len(sys.argv) > 2 else 'screenshot'
    top, intro, star = cdp_screenshots(url, base_name)
    print(f"TOP: {top}")
    print(f"INTRO: {intro}")
    if star:
        print(f"STAR_POS: {json.dumps(star)}")
