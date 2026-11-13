"""Diorama functionality audit. Taps every control with real pointer clicks on phone, landscape phone and desktop.
Usage: python3 diorama_audit.py page.html [phone land desk]   (run screens in parallel, one process each)
Needs the page hooks __orb, __B, __select, __setYear and the house control ids (bHud bSet bFind bStory bViews bOrbit bPlan bTen bData pmT pmX cKey cSum hyY tPlay home zIn zOut compass shX pgBack cardX menu find fq fr mLook mReset)."""
import asyncio, json, sys
from playwright.async_api import async_playwright

URL = 'file://' + __import__('os').path.abspath(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].endswith('.html') else 'file://' + __import__('os').path.abspath('index.html')
ARGS = [a for a in sys.argv[1:] if not a.endswith('.html')]
VPS = {
    'phone': dict(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2),
    'land': dict(viewport={'width': 844, 'height': 390}, is_mobile=True, has_touch=True, device_scale_factor=2),
    'desk': dict(viewport={'width': 1440, 'height': 900}),
}
STATE = """()=>{const v=s=>{const e=document.querySelector(s);if(!e)return false;const c=getComputedStyle(e);return c.display!=='none'&&c.visibility!=='hidden'&&+c.opacity>0.05&&e.getBoundingClientRect().width>0};
 const b=document.body.classList;return {menu:v('#menu'),find:v('#find'),hud:b.contains('hudopen'),
 panel:['sum','key','tl'].filter(k=>b.contains('p-'+k)).join(''),card:v('#card'),sheet:v('#sheet'),page:v('#page'),film:b.contains('filming')}}"""

async def run(name, opts, fails, log):
    async with async_playwright() as p:
        br = await p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--ignore-gpu-blocklist'])
        ctx = await br.new_context(**opts)
        pg = await ctx.new_page()
        pg.set_default_timeout(20000)
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
        # simulate an old saved state from an earlier version: Earth, plain look
        await pg.goto(URL, wait_until='load', timeout=180000)
        await pg.evaluate("localStorage.setItem('rvdio5',JSON.stringify({p:'Earth',l:0,s:{}}))")
        await pg.reload(wait_until='load', timeout=180000)
        await pg.wait_for_timeout(4000)
        orb0 = await pg.evaluate("document.querySelector('#bOrbit').classList.contains('on')")
        log.append(f"{name:5} info orbit on at load: {orb0}")
        await pg.evaluate("__orb(false)"); await pg.wait_for_timeout(3000)

        async def st():
            return await pg.evaluate(STATE)

        def check(label, cond, s):
            log.append(f"{name:5} {'ok  ' if cond else 'FAIL'} {label}  {json.dumps(s)}");print(log[-1],flush=True)
            if not cond:
                fails.append(f"{name}: {label} {json.dumps(s)}")

        async def vis(sel):
            return await pg.evaluate(f"(()=>{{const e=document.querySelector('{sel}');if(!e)return false;const r=e.getBoundingClientRect();const c=getComputedStyle(e);return r.width>0&&c.display!=='none'&&c.visibility!=='hidden'}})()")

        async def ctl(sel):
            # reveal the control row on compact screens, then tap with a real pointer
            if not await vis(sel) and await vis('#bHud'):
                await pg.click('#bHud', force=True); await pg.wait_for_timeout(250)
            await pg.click(sel, force=True); await pg.wait_for_timeout(350)

        def only(s, k):
            on = [x for x in ('menu', 'find', 'hud') if s[x]] + (['panel'] if s['panel'] else [])
            return on == ([k] if k else [])

        async def canvas_tap():
            vp = opts['viewport']
            r = await pg.evaluate("(()=>{const m=document.querySelector('#menu').getBoundingClientRect();return [m.left,m.right,m.top,m.bottom]})()")
            x = (r[0] - 20) if r[0] > 60 else min(vp['width'] - 10, r[1] + 20)
            if r[1] - r[0] > vp['width'] - 60: x = vp['width'] * 0.5
            y = vp['height'] * 0.55 if (r[1] - r[0] < vp['width'] - 60) else min(vp['height'] - 90, r[3] + 30)
            await pg.mouse.click(x, y); await pg.wait_for_timeout(350)

        # defaults: the owner's palette is the first tile
        await ctl('#bSet'); s = await st()
        OWN = await pg.evaluate("document.querySelector('#menu .pals button .pn')?.textContent")
        pal = await pg.evaluate("document.querySelector('#menu .pals .on .pn')?.textContent")
        lk = await pg.evaluate("[...document.querySelectorAll('#mLook i')].findIndex(i=>i.classList.contains('on'))")
        check(f'opens on the owner palette ({pal})', pal == OWN, s)
        check(f'opens on hatched look (dot {lk})', lk == 2, s)
        check('settings is the only open panel', only(s, 'menu'), s)
        await pg.screenshot(path=f'shots/au_{name}_menu.png')
        # cycling inside settings keeps it open
        await pg.click('#menu .pals button:nth-child(2)', force=True); await pg.wait_for_timeout(300); s = await st()
        check('palette tap keeps settings open', s['menu'], s)
        await pg.click('#mLook', force=True); await pg.wait_for_timeout(300); s = await st()
        check('Look tap keeps settings open', s['menu'], s)
        await pg.click('#menu [data-s="trees"]', force=True); await pg.wait_for_timeout(300)
        await pg.click('#menu [data-s="trees"]', force=True); await pg.wait_for_timeout(300); s = await st()
        check('toggle taps keep settings open', s['menu'], s)
        await pg.click('#mReset', force=True); await pg.wait_for_timeout(300); s = await st()
        pal = await pg.evaluate("document.querySelector('#menu .pals .on .pn')?.textContent")
        check(f'Reset returns to the owner palette ({pal})', pal == OWN and s['menu'], s)
        # the reported bug: the menu button must close settings
        if await vis('#bHud'):
            await pg.click('#bHud', force=True); await pg.wait_for_timeout(350); s = await st()
            check('menu button closes settings and nothing else opens', only(s, None), s)
            await pg.click('#bHud', force=True); await pg.wait_for_timeout(350); s = await st()
            check('menu button reopens the control row alone', only(s, 'hud'), s)
            await pg.click('#bHud', force=True); await pg.wait_for_timeout(350); s = await st()
            check('menu button closes the control row', only(s, None), s)
        await pg.keyboard.press('Escape'); await pg.wait_for_timeout(300)
        await ctl('#bSet')
        if await vis('#bSet'):
            await pg.click('#bSet', force=True); await pg.wait_for_timeout(350)
        else:
            await pg.click('#bHud', force=True); await pg.wait_for_timeout(350)
        s = await st(); check('settings closes from its own control', only(s, None), s)
        # outside tap, Escape
        await ctl('#bSet'); await canvas_tap(); s = await st()
        check('tap on the model closes settings and selects nothing', not s['menu'] and not s['card'], s)
        await ctl('#bSet'); await pg.keyboard.press('Escape'); await pg.wait_for_timeout(300); s = await st()
        check('Escape closes settings', not s['menu'], s)
        # dock panels
        dock = await vis('#cKey')
        log.append(f"{name:5} info dock shown: {dock}")
        if not dock:
            await pg.evaluate("document.body.classList.add('hudopen')"); await pg.wait_for_timeout(300)
            dock = await vis('#cKey'); await pg.evaluate("document.body.classList.remove('hudopen')")
        await ctl('#bSet')
        if not await vis('#cKey'):
            log.append(f"{name:5} info Key, Summary and timeline chips hidden on this screen; skipping")
            await pg.keyboard.press('Escape')
        else:
          await pg.click('#cKey', force=True); await pg.wait_for_timeout(350); s = await st()
          check('Key opens and closes settings', only(s, 'panel') and s['panel'] == 'key', s)
          await pg.click('#cSum', force=True); await pg.wait_for_timeout(350); s = await st()
          check('Summary replaces Key', s['panel'] == 'sum', s)
          await pg.click('#cSum', force=True); await pg.wait_for_timeout(350); s = await st()
          check('Summary closes', s['panel'] == '', s)
          await pg.click('#hyY', force=True); await pg.wait_for_timeout(350); s = await st()
          check('Timeline opens', s['panel'] == 'tl', s)
          await pg.click('#tPlay', force=True) if await vis('#tPlay') else None
          await pg.wait_for_timeout(1200)
          await pg.click('#tPlay', force=True) if await vis('#tPlay') else None
          await pg.click('#hyY', force=True); await pg.wait_for_timeout(350); s = await st()
          check('Timeline closes', s['panel'] == '', s)
        await pg.evaluate("window.__setYear&&__setYear(2026)")
        # find
        if await vis('#cKey'): await pg.click('#cKey', force=True)
        await ctl('#bFind'); s = await st()
        check('Find opens alone', only(s, 'find'), s)
        q = await pg.evaluate("(()=>{for(const b of __B){for(const x of (b.suites||[]))if(x.n&&x.n.length>3)return x.n.split(' ')[0]}return 'a'})()")
        await pg.fill('#fq', q); await pg.wait_for_timeout(400)
        n = await pg.evaluate("document.querySelectorAll('#fr > *').length")
        check(f'Find returns results ({n})', n > 0, s)
        if n:
            await pg.click('#fr > *:first-child', force=True); await pg.wait_for_timeout(1800); s = await st()
            check('Find result opens the card and closes Find', s['card'] and not s['find'], s)
        await pg.screenshot(path=f'shots/au_{name}_card.png')
        if await vis('#cardX'):
            await pg.click('#cardX', force=True); await pg.wait_for_timeout(600); s = await st()
            check('card closes', not s['card'], s)
        # views, orbit
        c0 = await pg.evaluate("JSON.stringify(window.__cam?__cam():0)")
        await ctl('#bViews'); await pg.wait_for_timeout(1500)
        await ctl('#bOrbit'); await pg.wait_for_timeout(800); await ctl('#bOrbit'); s = await st()
        check('Views and Orbit run', True, s)
        # nav
        for sel in ('#zIn', '#zOut', '#compass', '#home'):
            if await vis(sel):
                await pg.click(sel, force=True); await pg.wait_for_timeout(500)
            else:
                log.append(f"{name:5} info {sel} not shown on this screen")
        s = await st(); check('zoom, compass, home run', only(s, None) or s['hud'], s)
        # plan: top-down 3D first, then the 2D toggle
        await ctl('#bPlan'); await pg.wait_for_timeout(2500); s = await st()
        pm = await pg.evaluate("document.body.classList.contains('pm')")
        check('Plan opens the top-down 3D view with the toggle shown', pm and await vis('#pmT') and not s['sheet'] and not s['menu'], s)
        await pg.click('#pmT [data-pm="2d"]', force=True)
        for _ in range(20):
            await pg.wait_for_timeout(1000)
            if (await st())['sheet']: break
        s = await st(); check('2D toggle opens the site plan', s['sheet'], s)
        await pg.click('#pmT [data-pm="3d"]', force=True); await pg.wait_for_timeout(1500); s = await st()
        check('3D toggle returns to the top-down model', not s['sheet'] and await pg.evaluate("document.body.classList.contains('pm')"), s)
        await pg.click('#pmX', force=True); await pg.wait_for_timeout(2500); s = await st()
        check('Exit leaves plan', not s['sheet'] and not await pg.evaluate("document.body.classList.contains('pm')"), s)
        # tenants dashboard
        if await vis('#strip [data-go="rv"]'):
            await pg.click('#strip [data-go="rv"]', force=True); await pg.wait_for_timeout(1200)
        else:
            await ctl('#bTen'); await pg.wait_for_timeout(1200)
        s = await st(); n0 = await pg.evaluate("document.querySelectorAll('.tnt tr[data-ti]').length")
        check(f'Tenants page opens with a tenant list ({n0})', s['page'] and n0 > 0, s)
        await pg.click('.mixt tr[data-solo]', force=True); await pg.wait_for_timeout(500)
        n1 = await pg.evaluate("document.querySelectorAll('.tnt tr[data-ti]').length")
        check(f'Tapping a use filters the list ({n1} of {n0})', 0 < n1 < n0, await st())
        await pg.click('#tnScope [data-k="all"]', force=True); await pg.wait_for_timeout(500)
        n2 = await pg.evaluate("document.querySelectorAll('.tnt tr[data-ti]').length")
        check(f'All owners widens the list ({n2})', n2 > n0, await st())
        await pg.click('.tnt tr[data-ti]', force=True); await pg.wait_for_timeout(1800); s = await st()
        check('Tapping a tenant shows it on the model', s['card'] and not s['page'], s)
        await pg.keyboard.press('Escape'); await pg.wait_for_timeout(600)
        # data page
        await ctl('#bData'); await pg.wait_for_timeout(700); s = await st()
        check('Data page opens', s['page'] and not s['menu'], s)
        await pg.click('#pgBack', force=True); await pg.wait_for_timeout(700); s = await st()
        check('Data page closes', not s['page'], s)
        # building page from a card
        await pg.evaluate("__select((__B.find(b=>b.role==='rv'&&(b.suites||[]).length)||__B.find(b=>b.role!=='context')).id)"); await pg.wait_for_timeout(1800); s = await st()
        check('building card opens', s['card'], s)
        if await vis('#bHud') and not await vis('#bData'):
            await pg.click('#bHud', force=True); await pg.wait_for_timeout(400)
        cov = await pg.evaluate("[...document.querySelectorAll('#ctl .btn')].filter(b=>b.getBoundingClientRect().width>0&&getComputedStyle(b).display!=='none').filter(b=>{const r=b.getBoundingClientRect();const e=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return !(e&&b.contains(e))}).map(b=>b.id)")
        check(f'every control stays tappable with a card open (covered: {cov})', not cov, await st())
        if await pg.evaluate("document.body.classList.contains('hudopen')"):
            await pg.evaluate("document.body.classList.remove('hudopen')"); await pg.wait_for_timeout(300)
        more = await pg.evaluate("(()=>{const b=[...document.querySelectorAll('#cardB button,#cardB a')].find(x=>/building page|open|more/i.test(x.textContent));if(b){b.click();return b.textContent}return ''})()")
        await pg.wait_for_timeout(1500); s = await st()
        check(f'card opens the building page ({more.strip()[:20]})', s['page'], s)
        await pg.screenshot(path=f'shots/au_{name}_bp.png')
        await pg.click('#pgBack', force=True); await pg.wait_for_timeout(1200); s = await st()
        check('building page back', not s['page'], s)
        await pg.keyboard.press('Escape'); await pg.wait_for_timeout(600)
        # floors: a building with upper-floor tenants switches floors in the 3D view and the plans together
        up = await pg.evaluate("(__B.find(b=>(b.l2||[]).some(t=>t.n)&&(b.suites||[]).length)||{}).id||''")
        if up:
            await pg.evaluate(f"__select('{up}')"); await pg.wait_for_timeout(1500)
            await pg.evaluate("(()=>{const b=[...document.querySelectorAll('#cardB button,#cardB a')].find(x=>/building page/i.test(x.textContent));b&&b.click()})()"); await pg.wait_for_timeout(1500)
            if await vis('.fsw3'):
                await pg.click('.fsw3 button[data-fl="2"]', force=True); await pg.wait_for_timeout(500)
                ok = await pg.evaluate("getComputedStyle(document.querySelector('.flp[data-fl=\"2\"]')).display!=='none'&&document.querySelector('.fhd .fsw button[data-fl=\"2\"]').classList.contains('on')")
                check('Second floor switch moves the 3D view and the plans together', ok, await st())
                await pg.click('.fhd .fsw button[data-fl="1"]', force=True); await pg.wait_for_timeout(500)
                ok = await pg.evaluate("document.querySelector('.fsw3 button[data-fl=\"1\"]').classList.contains('on')")
                check('Ground floor switch from the plans moves the 3D view', ok, await st())
            else:
                check('building with upper floors shows a floor switch', False, await st())
            await pg.click('#pgBack', force=True); await pg.wait_for_timeout(1000)
            await pg.keyboard.press('Escape'); await pg.wait_for_timeout(600)
        # deal story
        await ctl('#bStory'); await pg.wait_for_timeout(2000); s = await st()
        check('Deal story plays', s['film'], s)
        await pg.keyboard.press('Escape'); await pg.wait_for_timeout(1200); s = await st()
        check('Deal story ends', not s['film'], s)
        await pg.screenshot(path=f'shots/au_{name}_end.png')
        # a reload still opens on the owner palette
        await pg.reload(wait_until='load', timeout=180000); await pg.wait_for_timeout(2000)
        await ctl('#bSet')
        pal = await pg.evaluate("document.querySelector('#menu .pals .on .pn')?.textContent")
        check(f'reload opens on the owner palette ({pal})', pal == OWN, await st())
        bad = [e for e in errs if 'favicon' not in e]
        check(f'console clean ({len(bad)})', not bad, {'errors': bad[:5]})
        await br.close()

async def main():
    __import__('os').makedirs('shots', exist_ok=True)
    fails, log = [], []
    for k, v in VPS.items():
        if ARGS and k not in ARGS:
            continue
        try:
            await run(k, v, fails, log)
        except Exception as e:
            import traceback; tb=traceback.extract_tb(e.__traceback__)[-1]
            fails.append(f'{k}: crashed at line {tb.lineno}: {tb.line} :: {str(e).splitlines()[0][:200]}')
    print('\n'.join(log))
    print('\nFAILURES:' if fails else '\nALL PASS', *fails, sep='\n')

asyncio.run(main())
