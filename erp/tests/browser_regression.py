"""Isolated browser regression tests; never use production credentials or endpoints."""
import json, os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "erp-next" / "operating.html"
ART = ROOT / "erp" / "tests" / "artifacts"
ART.mkdir(parents=True, exist_ok=True)
SOURCE = APP.read_text(encoding="utf-8")
ORIGIN = "http://erp-test.invalid"
HOST = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><style>html,body,iframe{margin:0;width:100%;height:100%;border:0;display:block}</style></head><body><script>
window.testState={};window.testSaves=0;window.testReject=false;
window.erpNextHost={ready:()=>true,initial:()=>structuredClone(window.testState),actor:()=>({id:'test-only',name:'테스트',admin:true}),save:s=>{if(window.testReject)return false;window.testState=structuredClone(s);window.testSaves++;return true},work:async()=>({staff:[],messages:[]}),account:()=>{},refresh:()=>{},logout:()=>{}};
</script><iframe src="/erp-next/operating.html"></iframe></body></html>"""
def run(browser, label, width, height, mobile):
    context = browser.new_context(viewport={"width":width,"height":height}, is_mobile=mobile, has_touch=mobile, device_scale_factor=1)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    # Serve only local synthetic content. Block all external network requests.
    def route(req):
        url = req.request.url
        if url == ORIGIN + "/":
            req.fulfill(status=200, content_type="text/html; charset=utf-8", body=HOST)
        elif url == ORIGIN + "/erp-next/operating.html":
            req.fulfill(status=200, content_type="text/html; charset=utf-8", body=SOURCE)
        else:
            req.abort()
    context.route("**/*", route)
    try:
        page.goto(ORIGIN + "/", wait_until="domcontentloaded")
        frame = page.frame_locator("iframe")
        main = frame.locator("#main")
        expect(main.locator("h1")).to_be_visible(timeout=10000)
        app = page.frames[1]
        dimensions = app.evaluate("()=>({width:innerWidth,mobile:matchMedia('(max-width:760px)').matches})")
        print(label+": viewport "+str(dimensions),flush=True)
        assert abs(dimensions["width"]-width)<=2 and dimensions["mobile"]==mobile, dimensions
        if mobile:
            expect(frame.locator("#hamb")).to_be_visible(timeout=5000)
        def nav(group, target):
            if mobile:
                frame.locator("#hamb").click()
            g = frame.locator('[data-group="'+group+'"]')
            if g.get_attribute("aria-expanded") != "true":
                g.click()
            frame.locator('#sidebar [data-page="'+target+'"]').click()
            expect(main.locator("h1")).to_have_text(target)
        def layout(name):
            bounds = app.evaluate("""()=>{const d=document.documentElement;return {width:innerWidth,scroll:d.scrollWidth}}""")
            assert bounds["scroll"] <= bounds["width"] + 2, (name,bounds)
            page.screenshot(path=str(ART / (label+"-"+name+".png")))
        layout("dashboard")
        nav("재고관리","입고입력")
        layout("inbound")
        main.locator('[data-new="입고입력"]').click()
        expect(frame.locator("#editor")).to_be_visible()
        form=frame.locator("#editorform")
        def field(name): return form.locator('[name="'+name+'"]')
        def setfield(name,value):
            el=field(name)
            if el.count():
                if el.evaluate("(e)=>e.tagName")== "SELECT": el.select_option(label=value)
                else: el.fill(value)
        for k,v in {"날짜":"2026-11-20","품목명":"자동검증꽃갈비","업체명":"테스트업체","분류":"원료육","하위분류":"소고기","원산지":"미국","브랜드":"TEST","보관상태":"냉동","창고":"냉동고","LOT":"TEST-1","수량":"10","단위":"kg"}.items():
            setfield(k,v)
        if field("거래유형").count():
            setfield("거래유형","매입")
            setfield("단가","0")
        page.screenshot(path=str(ART/(label+"-editor.png")))
        box=frame.locator("#editor").bounding_box()
        assert box and box["x"]>=-2 and box["x"]+box["width"]<=width+2, box
        form.locator('button[type="submit"]').click()
        expect(frame.locator("#editor")).not_to_be_visible()
        state=page.evaluate("window.testState")
        assert len(state["입고입력"])==1, state
        assert float(state["입고입력"][0]["수량"])==10
        expect(main.locator("#resultcount")).to_contain_text("1")
        main.locator("#search").fill("없는품목")
        expect(main.locator("#resultcount")).to_contain_text("0")
        main.locator("#search").fill("자동검증꽃")
        expect(main.locator("#resultcount")).to_contain_text("1")
        main.locator("#reset").click()
        main.locator('[data-new="입고입력"]').click()
        frame.locator("#closeEditor").click()
        expect(frame.locator("#editor")).not_to_be_visible()
        assert len(page.evaluate("window.testState")["입고입력"])==1
        # Exercise actual application inventory replay and sequence/identity logic with isolated state.
        result=app.evaluate("""()=>{const r=rows('입고입력')[0], original=structuredClone(r); const move={...r,'날짜':'2026-11-21','구분':'해동','출발상태':'냉동','도착상태':'해동','출발창고':'냉동고','도착창고':'냉장고','수량':4};const moved=saveEvent('이동입력',move);const afterMove=inventory().map(x=>[x['보관상태'],Number(x['수량'])]);const out={...r,'날짜':'2026-11-22','구분':'출고','수량':2};const sold=saveEvent('출고입력',out);const bad=saveEvent('출고입력',{...out,'수량':100});const after=inventory().reduce((a,x)=>a+Number(x['수량']),0);const edit=saveEvent('입고입력',{...r,'비고':'수정 테스트'},0);const kept=rows('입고입력')[0];return {moved,afterMove,sold,bad,after,edit,seq:kept._seq===original._seq&&move._seq<out._seq&&original._seq<move._seq,registered:kept._registeredAt===original._registeredAt&&kept._registeredBy===original._registeredBy}}""")
        assert result["moved"] and result["sold"] and not result["bad"], result
        assert sorted(x[1] for x in result["afterMove"])==[4,6] and result["after"]==8, result
        assert result["edit"] and result["seq"] and result["registered"],result
        nav("재고관리","입출고내역")
        layout("transactions")
        # Price module tests run when that feature exists, not on the pre-feature baseline.
        if app.evaluate("typeof parsePrice === 'function'"):
            price=app.evaluate("""()=>({missing:parsePrice('')===null,zero:parsePrice('0')===0,bad:Number.isNaN(parsePrice('-1')),free:priceAmount({'단가':0,'수량':3})===0,unknown:priceAmount({'단가':null,'수량':3})===null,vat:priceAmount({'단가':100,'수량':3,'세금구분':'과세(별도)'})===330})""")
            assert all(price.values()),price
        assert not errors, errors
        print(label+": browser regression passed", flush=True)
    except Exception:
        page.screenshot(path=str(ART/(label+"-failure.png")))
        print("Browser errors:",errors,flush=True)
        raise
    finally:
        context.close()

if __name__=="__main__":
    with sync_playwright() as p:
        executable=os.environ.get("CHROMIUM_EXECUTABLE")
        browser=p.chromium.launch(headless=True, **({"executable_path":executable} if executable else {}))
        try:
            for args in [("pc",1440,900,False),("mobile",390,844,True),("small-mobile",360,800,True)]:
                run(browser,*args)
        finally:
            browser.close()
