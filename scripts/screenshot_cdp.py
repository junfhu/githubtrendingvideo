"""Take 2 viewport-height screenshots of a GitHub repo page via CDP.

Shot 1 (top):   page header + star button area
Shot 2 (intro): README / introduction section below the fold
"""
import json, base64, time, sys, os, re
from websocket import create_connection
import urllib.request

DEBUG_PORT = 9222
VIEWPORT_W = 1920
VIEWPORT_H = 1080
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(SKILL_DIR, "remotion", "public")


def cdp_screenshots(url, base_name, heading=None, heading_index=0):
    """Take screenshots: top area and intro/README section.

    heading/heading_index: target the S5 intro section.
    """
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

    # Locate star element AND inject red ring
    print("Locating star button and adding red ring...")
    pos = send('Runtime.evaluate', {'expression': '''
    (function() {
        var star = null;
        var spans = document.querySelectorAll('span.d-inline');
        for (var i = 0; i < spans.length; i++) {
            var t = spans[i].textContent.trim();
            if (t === 'Star' || t === 'Unstar') {
                star = spans[i].closest('a, button, form');
                break;
            }
        }
        if (!star) {
            var links = document.querySelectorAll('a.btn-sm.btn');
            for (var j = 0; j < links.length; j++) {
                if (links[j].textContent.includes('Star')) { star = links[j]; break; }
            }
        }
        if (!star) {
            var btns = document.querySelectorAll('button[aria-label*="star" i], a[aria-label*="star" i]');
            if (btns.length > 0) star = btns[0];
        }
        if (!star) return JSON.stringify({error: 'star button not found'});
        var r = star.getBoundingClientRect();
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

    # Screenshot 1: Top area
    print("Capturing screenshot 1 (top)...")
    send('Runtime.evaluate', {'expression': 'window.scrollTo(0, 0);'})
    time.sleep(0.5)
    result1 = send('Page.captureScreenshot', {'format': 'png', 'fromSurface': True})
    top_name = f"{base_name}_top.png"
    top_path = os.path.join(OUTPUT_DIR, top_name)
    top_data = base64.b64decode(result1['result']['data'])
    with open(top_path, 'wb') as f:
        f.write(top_data)
    t_size = os.path.getsize(top_path)
    t_png = top_data[:4] == b'\x89PNG'
    if t_size < 500 or not t_png:
        raise RuntimeError(f"Top screenshot validation FAILED: size={t_size}, is_png={t_png}")
    print(f"Screenshot 1 saved: {top_path} ({t_size:,} bytes, valid PNG)")

    # Remove red ring
    send('Runtime.evaluate', {'expression': '''
    var ring = document.getElementById('__star_red_ring__');
    if (ring) ring.remove();
    '''})
    time.sleep(0.3)

    # ── Screenshot 2: Intro section ──────────────────────────────────────
    # Approach: find heading, measure section, resize viewport to section size,
    # scroll section to viewport top, capture FULL viewport (no clip).
    # This avoids all clip-coordinate issues.

    # Step A: find target heading + measure section dimensions
    if heading:
        search_text = re.sub(r'[#*_`]', '', heading).strip()
        print(f"Targeting heading: {search_text} (index={heading_index})")
        dims = send('Runtime.evaluate', {'expression': f'''
        (function() {{
            var container = document.querySelector('article.markdown-body')
                         || document.querySelector('#readme')
                         || document.querySelector('.markdown-body')
                         || document.querySelector('[data-target="readme-toc"]')
                         || document.querySelector('.Box-body')
                         || document.querySelector('main');
            if (!container) return JSON.stringify({{pageX: 0, pageY: 600, w: 900, h: 3000}});

            var searchText = {json.dumps(search_text)};
            var headingIdx = {heading_index};
            var allH2s = container.querySelectorAll('h2');
            var targetEl = null;

            // Strategy 1: text match
            for (var i = 0; i < allH2s.length; i++) {{
                var hText = allH2s[i].textContent.replace(/[#*_`\\s]+/g, ' ').trim().toLowerCase();
                if (hText.indexOf(searchText.toLowerCase()) !== -1) {{
                    targetEl = allH2s[i]; break;
                }}
            }}
            // Strategy 2: h2 index (reliable — same order as markdown)
            if (!targetEl && headingIdx > 0 && headingIdx <= allH2s.length) {{
                targetEl = allH2s[headingIdx - 1];
            }}
            // Strategy 3: first non-boilerplate h2
            if (!targetEl) {{
                for (var j = 0; j < allH2s.length; j++) {{
                    var t = allH2s[j].textContent.trim().toLowerCase();
                    if (t.length > 3 && !/install|usage|getting started|contribut|license|table of contents/i.test(t)) {{
                        targetEl = allH2s[j]; break;
                    }}
                }}
            }}
            if (!targetEl) targetEl = allH2s[0] || container;

            // Scroll heading to viewport top
            var rect = targetEl.getBoundingClientRect();
            window.scrollTo(0, window.scrollY + rect.top - 20);
            rect = targetEl.getBoundingClientRect();

            // Find section end: next h2 or container bottom
            var endY = container.getBoundingClientRect().bottom + window.scrollY;
            for (var k = 0; k < allH2s.length; k++) {{
                if (allH2s[k].compareDocumentPosition(targetEl) & Node.DOCUMENT_POSITION_FOLLOWING) {{
                    if (allH2s[k] !== targetEl) {{
                        var nr = allH2s[k].getBoundingClientRect();
                        endY = window.scrollY + nr.top;
                        break;
                    }}
                }}
            }}

            var sectionTop = window.scrollY + rect.top;
            var sectionH = Math.min(Math.max(endY - sectionTop, 400), 6000);

            return JSON.stringify({{
                pageX: Math.round(window.scrollX + rect.left),
                pageY: Math.round(sectionTop),
                w: Math.round(rect.width),
                h: Math.round(sectionH),
                vpTop: Math.round(rect.top)
            }});
        }})()
        '''})
    else:
        # Full README (fallback)
        print("Capturing full README...")
        dims = send('Runtime.evaluate', {'expression': '''
        (function() {
            var target = document.querySelector('article.markdown-body')
                      || document.querySelector('#readme')
                      || document.querySelector('.markdown-body')
                      || document.querySelector('[data-target="readme-toc"]');
            if (!target) target = document.querySelector('.Box-row') || document.querySelector('main');
            if (!target) return JSON.stringify({pageX: 0, pageY: 600, w: 900, h: 3000});
            var rect = target.getBoundingClientRect();
            window.scrollTo(0, window.scrollY + rect.top);
            rect = target.getBoundingClientRect();
            return JSON.stringify({
                pageX: Math.round(window.scrollX + rect.left),
                pageY: Math.round(window.scrollY + rect.top),
                w: Math.round(rect.width),
                h: Math.min(target.scrollHeight + 20, 12000),
                vpTop: Math.round(rect.top)
            });
        })()
        '''})

    try:
        info = json.loads(dims['result']['result']['value'])
        section_page_x = int(info['pageX'])
        section_page_y = int(info['pageY'])
        content_w = int(info['w'])
        content_h = int(info['h'])
        vp_top = int(info.get('vpTop', 20))
        print(f"Section page coords: x={section_page_x}, y={section_page_y}, w={content_w}, h={content_h}, vpTop={vp_top}")
    except Exception as e:
        print(f"Measure failed: {e}, using defaults")
        section_page_x, section_page_y, content_w, content_h, vp_top = 378, 2496, 838, 4000, 20

    if content_w <= 0 or content_h <= 0:
        raise RuntimeError(f"Invalid section dimensions: {content_w}x{content_h}")

    # Step B: resize viewport to section height, capped at 1080px (one screen)
    viewport_h = min(max(content_h + 60, 600), 1080)
    print(f"Resizing viewport to 1920x{viewport_h}...")
    send('Emulation.setDeviceMetricsOverride', {
        'width': 1920,
        'height': viewport_h,
        'deviceScaleFactor': 1,
        'mobile': False
    })
    time.sleep(0.6)

    # Step C: scroll so the section starts at viewport top
    send('Runtime.evaluate', {'expression': f'''
    window.scrollTo({section_page_x}, {section_page_y - 20});
    '''})
    time.sleep(0.4)

    # Step D: capture FULL viewport — no clip needed since viewport = section
    print(f"Capturing full viewport ({viewport_h}px)...")
    result2 = send('Page.captureScreenshot', {
        'format': 'png',
        'fromSurface': True
    })

    intro_name = f"{base_name}_intro.png"
    intro_path = os.path.join(OUTPUT_DIR, intro_name)
    intro_data = base64.b64decode(result2['result']['data'])
    with open(intro_path, 'wb') as f:
        f.write(intro_data)

    # Validate: file must be a real PNG with actual content (not blank)
    file_size = os.path.getsize(intro_path)
    is_png = intro_data[:4] == b'\x89PNG'
    if file_size < 500 or not is_png:
        raise RuntimeError(
            f"Intro screenshot validation FAILED: size={file_size}, is_png={is_png}. "
            f"Likely blank capture."
        )

    # Image content check — verify it's not a blank/white image
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(intro_data))
        w, h = img.size
        # Sample center strip to check for content variance
        gray = img.convert('L')
        # Take center 60% of the image, compute std deviation
        crop = gray.crop((w*2//10, h*1//10, w*8//10, h*2//10))
        import numpy as np
        arr = np.array(crop)
        std = float(arr.std())
        mean = float(arr.mean())
        if std < 8:
            raise RuntimeError(
                f"Intro screenshot appears BLANK: {w}x{h}, std={std:.1f}, mean={mean:.1f}. "
                f"Image has no visible content — section may not have rendered."
            )
        print(f"Screenshot 2 saved: {intro_path} ({file_size:,} bytes, {w}x{h}, std={std:.1f}, mean={mean:.1f})")
    except ImportError:
        print(f"Screenshot 2 saved: {intro_path} ({file_size:,} bytes, valid PNG — PIL not available for content check)")
    except RuntimeError:
        raise
    except Exception as e:
        print(f"Screenshot 2 saved: {intro_path} ({file_size:,} bytes) — content check skipped: {e}")

    # Reset viewport
    send('Emulation.setDeviceMetricsOverride', {
        'width': VIEWPORT_W, 'height': VIEWPORT_H,
        'deviceScaleFactor': 1, 'mobile': False
    })

    ws.close()
    return top_name, intro_name, star_pos, viewport_h


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python screenshot_cdp.py <github-url> <base-name> [--heading <text>]")
        sys.exit(1)

    url = sys.argv[1]
    base_name = sys.argv[2] if len(sys.argv) > 2 else 'screenshot'
    heading = None
    heading_index = 0
    if '--heading' in sys.argv:
        idx = sys.argv.index('--heading')
        if idx + 1 < len(sys.argv):
            heading = sys.argv[idx + 1]
    if '--heading-index' in sys.argv:
        idx = sys.argv.index('--heading-index')
        if idx + 1 < len(sys.argv):
            heading_index = int(sys.argv[idx + 1])
    top, intro, star, intro_h = cdp_screenshots(
        url, base_name,
        heading=heading, heading_index=heading_index)
    print(f"TOP: {top}")
    print(f"INTRO: {intro}")
    print(f"INTRO_H: {intro_h}")
    if star:
        print(f"STAR_POS: {json.dumps(star)}")
