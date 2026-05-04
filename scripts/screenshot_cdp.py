"""Take clean screenshot of a GitHub repo page (minimal UI removal) via CDP."""
import json, base64, time, sys, os
from websocket import create_connection
import urllib.request

DEBUG_PORT = 9222
OUTPUT_DIR = "D:/BaiduSyncdisk/Obsidian/ForCC/.claude/skills/github-trending/remotion/public"

def cdp_screenshot(url, output_filename):
    """Navigate to url, hide only global nav + sidebars, capture screenshot."""
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

    print(f"Navigating to {url}...")
    send('Page.enable')
    send('Page.navigate', {'url': url})
    time.sleep(5)

    # Find star button position for later annotation
    print("Locating star button...")
    pos = send('Runtime.evaluate', {'expression': '''
    (function() {
        var btn = null;
        var allBtns = document.querySelectorAll('button');
        for (var i = 0; i < allBtns.length; i++) {
            var t = allBtns[i].textContent || '';
            var a = allBtns[i].getAttribute('aria-label') || '';
            if (t.includes('Star') || a.includes('star') || a.includes('Star')) {
                btn = allBtns[i]; break;
            }
        }
        if (!btn) {
            var sc = document.querySelector('.starring-container');
            if (sc) btn = sc;
        }
        if (btn) {
            var r = btn.getBoundingClientRect();
            return JSON.stringify({x: r.x, y: r.y, w: r.width, h: r.height, vw: window.innerWidth, vh: window.innerHeight});
        }
        return JSON.stringify({error: 'star button not found'});
    })()
    '''})
    try:
        star_pos = json.loads(pos['result']['result']['value'])
        print(f"Star button: {star_pos}")
    except:
        star_pos = None
        print("Could not locate star button")

    print("Removing only global nav and sidebars...")
    send('Runtime.evaluate', {'expression': '''
    var toHide = [
        "header.AppHeader",
        "header.Header-old",
        ".Layout-sidebar",
        "footer",
        "[data-target='recent-activity-sidebar']"
    ];
    toHide.forEach(function(sel) {
        try { document.querySelectorAll(sel).forEach(function(el) { el.style.display = 'none'; }); } catch(e) {}
    });
    document.body.style.overflow = 'hidden';
    document.body.style.background = '#ffffff';
    '''})
    time.sleep(1)

    print("Capturing screenshot...")
    result = send('Page.captureScreenshot', {'format': 'png', 'fromSurface': True})
    ws.close()

    output_path = os.path.join(OUTPUT_DIR, output_filename)
    img_data = base64.b64decode(result['result']['data'])
    with open(output_path, 'wb') as f:
        f.write(img_data)
    print(f"Screenshot saved: {len(img_data)} bytes to {output_path}")
    if star_pos:
        print(f"STAR_POS: {json.dumps(star_pos)}")
    return output_filename

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python screenshot_cdp.py <github-url> [output-filename]")
        sys.exit(1)

    url = sys.argv[1]
    filename = sys.argv[2] if len(sys.argv) > 2 else 'screenshot.png'
    cdp_screenshot(url, filename)
