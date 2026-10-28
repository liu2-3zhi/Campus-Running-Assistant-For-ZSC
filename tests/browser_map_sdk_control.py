"""Opt-in minimal native Tencent/Baidu SDK teardown control (no app renderer).

Uses authorized origins fulfilled locally and credentials supplied in memory.
The production planner loads the SDK once; all map lifecycle operations below
use only public native APIs, without Vue or the legacy runtime. An explicit
constructor-instrumentation switch reproduces the acceptance fixture for A/B checks.
"""

import json
import logging
import os
from urllib.parse import quote, urlsplit

from playwright.sync_api import sync_playwright

from browser_map_proxy_smoke import browser_step, evaluate_acceptance, production_planner, safe_error, smoke_results_passed


NATIVE_ROUND = """async ({provider,frameSteps=false,instrumentConstructors=false,stableGeometryIds=false,operationProfile='all',settleFrames=0,rebuildOnFirstProgress=false,waitForLabels=false}) => {
    const host=document.createElement('div'); host.style.cssText='width:100vw;height:90vh';
    document.body.appendChild(host);
    const step=()=>frameSteps?new Promise(resolve=>requestAnimationFrame(resolve)):Promise.resolve();
    const profile=new Set(String(operationProfile).split('+'));
    const updateLines=profile.has('all')||profile.has('lines');
    const updateMarkers=profile.has('all')||profile.has('markers');
    const updateLabels=profile.has('all')||profile.has('labels');
    const switchTask=profile.has('all')||profile.has('switch');
    const point=(x)=>provider==='tencent'?new TMap.LatLng(39.916527,x):new BMap.Point(x,39.9225);
    const base=provider==='tencent'?116.397128:116.4035;
    let map,line,marker,label,idleEvents=0;
    const lines=[],markers=[],labels=[],restorers=[],identities=[],geometryEvents={lines:0,markers:0,labels:0};
    if(provider==='tencent' && instrumentConstructors) {
        for(const name of ['MultiPolyline','MultiMarker','MultiLabel']) {
            const Original=TMap[name];
            const replacement=new Proxy(Original,{construct(target,args){
                const value=Reflect.construct(target,args);
                identities.push({name,constructorMatchesGlobal:value.constructor===TMap[name],instanceofGlobal:value instanceof TMap[name]});
                return value;
            }});
            TMap[name]=replacement;
            restorers.push(()=>{if(TMap[name]===replacement) TMap[name]=Original});
        }
    }
    const pendingLabels=new Set();
    const labelReady=label=>{
        const promise=new Promise((resolve,reject)=>{
            const timeout=setTimeout(()=>reject(Error('label geometry deadline')),5000);
            const done=()=>{clearTimeout(timeout);label.off('geometry_processed',done);resolve()};
            label.on('geometry_processed',done);
        });
        promise.catch(()=>{});pendingLabels.add(promise);
    };
    const releaseTencentOverlays=async()=>{
        if(waitForLabels) {await Promise.all(pendingLabels);pendingLabels.clear()}
        for(const value of markers.splice(0)) {value.stopMove?.();value.setMap(null)}
        for(const value of labels.splice(0)) value.destroy();
        for(const value of lines.splice(0)) value.destroy();
    };
    const seedTencent=(offset=0)=>{
        for(let i=0;i<3;i++) {
            const geometry={styleId:'style',paths:[point(base+offset+i*.0003),point(base+offset+(i+1)*.0003)]};
            if(stableGeometryIds) geometry.id='route-'+i;
            const line=new TMap.MultiPolyline({map,styles:{style:new TMap.PolylineStyle({color:['#9ca3af','#2563eb','#ef4444'][i],width:6})},
                geometries:[geometry]});
            line.on('geometry_processed',()=>geometryEvents.lines++);lines.push(line);
            const id=i===2?'runner':'target-'+i, title=i===2?'当前位置':['中点','终点'][i];
            const marker=new TMap.MultiMarker({map,geometries:[{id,position:point(base+offset+i*.0003)}]});
            marker.on('geometry_processed',()=>geometryEvents.markers++);markers.push(marker);
            const label=new TMap.MultiLabel({map,
                styles:{name:new TMap.LabelStyle({color:'#ffffff',backgroundColor:'#059669',padding:'4px 8px',borderRadius:12,offset:{x:0,y:-35}})},
                    geometries:[{id:id+'-name',styleId:'name',position:point(base+offset+i*.0003),content:title}]});
            label.on('geometry_processed',()=>geometryEvents.labels++);labels.push(label);
            if(waitForLabels) labelReady(label);
        }
        const bounds=new TMap.LatLngBounds();
        [0,.0003,.0006,.001,.0014].forEach(delta=>bounds.extend(point(base+offset+delta)));
        map.fitBounds(bounds,{ease:{duration:0}});
    };
    try {
        if(provider==='tencent') {
            map=new TMap.Map(host,{zoom:16,center:point(base)});
            map.on('idle',()=>idleEvents++);
            seedTencent();
        } else {
            map=new BMap.Map(host);map.centerAndZoom(point(base),16);
            line=new BMap.Polyline([point(base),point(base+.001)],{strokeColor:'#0077ff',strokeWeight:6});
            marker=new BMap.Marker(point(base)); map.addOverlay(line);map.addOverlay(marker);
            marker.setTitle('当前位置');
            const content=document.createElement('span');content.textContent='当前位置';
            label=new BMap.Label(content.outerHTML);marker.setLabel(label);
            label.setStyle({backgroundColor:'#10b981',color:'#fff',borderColor:'#10b981'});
        }
        for(let i=0;i<Number(settleFrames)||0;i++) await step();
        await step();
        for(let i=0;i<10;i++) {
            const current=point(base+(i%5)*.0002), end=point(base+.001);
            if(provider==='tencent' && rebuildOnFirstProgress && i===0) { await releaseTencentOverlays(); seedTencent(.001); }
            if(provider==='tencent') {
                if(updateLines) lines.forEach((value,index)=>{
                    const geometry={styleId:'style',paths:[current,end]};
                    if(stableGeometryIds) geometry.id='route-'+index;
                    value.setGeometries([geometry]);
                });
                if(updateMarkers) markers.forEach((value,index)=>value.setGeometries([{id:index===2?'runner':'target-'+index,position:current}]));
                if(updateLabels) labels.forEach((value,index)=>{
                    if(waitForLabels) labelReady(value);
                    const id=index===2?'runner':'target-'+index;
                    value.setGeometries([{id:stableGeometryIds ? id+'-name' : id,styleId:'name',position:current,content:index===2?'当前位置':['中点','终点'][index]}]);
                    value.setStyles({name:new TMap.LabelStyle({color:'#fff',backgroundColor:'#2563eb',offset:{x:0,y:-35}})});
                });
            }
            else {line.setPath([current,end]);marker.setPosition(current);}
            await step();
        }
        // Vue clears the prior task's layers and creates the next task's layers.
        if(provider==='tencent' && switchTask) {await releaseTencentOverlays();seedTencent(.002)}
        else line.setPath([point(base+.002),point(base+.003)]);
        return {progress_updates:10,functional_pass:true,constructor_instrumentation:instrumentConstructors,stable_geometry_ids:stableGeometryIds,
            multi_line_count:provider==='tencent'?lines.length:1,label_count:provider==='tencent'?labels.length:1,identities,geometry_events:geometryEvents,idle_events:idleEvents};
    } finally {
        if(map) {
            if(provider==='tencent') {
                await releaseTencentOverlays();
                await new Promise((resolve,reject)=>{
                    const timeout=setTimeout(()=>reject(Error('native SDK destroy deadline')),5000);
                    const destroyed=()=>{clearTimeout(timeout);map.off('destroyed',destroyed);resolve()};
                    map.on('destroyed',destroyed);try {map.destroy()} catch(error){clearTimeout(timeout);reject(error)}
                });
            } else { marker?.disableDragging?.();map.clearOverlays();map.destroy(); }
        }
        host.remove();
        for(const restore of restorers.reverse()) restore();
    }
}"""


def run(credentials):
    assert credentials and set(credentials) <= {"tencent", "baidu"}
    results = []
    frame_steps = os.environ.get("MAP_SMOKE_NATIVE_FRAME_STEPS") == "1"
    instrument_constructors = os.environ.get("MAP_SMOKE_NATIVE_INSTRUMENT_CONSTRUCTORS") == "1"
    stable_geometry_ids = os.environ.get("MAP_SMOKE_NATIVE_STABLE_GEOMETRY_IDS") == "1"
    operation_profile = os.environ.get("MAP_SMOKE_NATIVE_PROFILE", "all")
    settle_frames = int(os.environ.get("MAP_SMOKE_NATIVE_SETTLE_FRAMES", "0") or 0)
    rebuild_on_first_progress = os.environ.get("MAP_SMOKE_NATIVE_REBUILD_FIRST_PROGRESS") == "1"
    wait_for_labels = os.environ.get("MAP_SMOKE_NATIVE_WAIT_LABELS") == "1"
    with sync_playwright() as playwright:
        browser_path = os.environ.get("MAP_SMOKE_BROWSER_PATH")
        browser = playwright.chromium.launch(headless=True, **({"executable_path": browser_path} if browser_path else {}))
        try:
            for provider, credential in credentials.items():
                parsed = urlsplit(credential["origin"])
                assert parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username
                origin = f"{parsed.scheme}://{parsed.netloc}"
                context = browser.new_context(service_workers="block")
                try:
                    context.route(origin + "/**", lambda route: route.fulfill(content_type="text/html", body="<!doctype html><body style='margin:0'></body>") if urlsplit(route.request.url).path == "/map-native-control" else route.fulfill(status=404, content_type="text/plain", body="Not found"))
                    page = context.new_page()
                    errors, rejections, console, failures = [], [], [], []
                    page.expose_function("recordSmokeRejection", lambda value: rejections.append(safe_error(value, credentials)))
                    page.add_init_script("addEventListener('unhandledrejection', event => window.recordSmokeRejection(String(event.reason?.stack || event.reason || 'unhandled rejection')));")
                    page.on("pageerror", lambda error: errors.append(safe_error(getattr(error, "stack", None) or error, credentials)))
                    page.on("console", lambda message: console.append(safe_error(message.text, credentials)) if message.type == "error" else None)
                    page.on("dialog", lambda dialog: dialog.dismiss())
                    page.on("response", lambda response: failures.append({"status": response.status, "path": safe_error(urlsplit(response.url).path, credentials)}) if response.status >= 400 or (response.request.resource_type == "script" and "javascript" not in response.headers.get("content-type", "")) else None)
                    page.goto(origin + "/map-native-control", wait_until="domcontentloaded")
                    route = {}
                    rounds = []
                    try:
                        args = [[[116.397128, 39.916527], [116.398128, 39.916527]], credential["key"], {"api_retries": 0, "api_fallback_line": False}, "walking"]
                        route = browser_step(page, "async ({source,args}) => (0,eval)('('+source+')')(args)", {"source": production_planner(provider), "args": args}, timeout_ms=60000)
                        if provider == "tencent":
                            page.add_script_tag(url="https://map.qq.com/api/gljs?v=1.exp&key=" + quote(credential["key"], safe=""))
                        for mobile in (False, True):
                            page.set_viewport_size({"width": 390 if mobile else 1280, "height": 844 if mobile else 800})
                            for index in range(3):
                                baseline = (len(errors), len(rejections), len(console))
                                row = {"round": index + 1, "viewport": "mobile" if mobile else "desktop", "functional_pass": False}
                                try:
                                    options = {"provider": provider, "frameSteps": frame_steps, "instrumentConstructors": instrument_constructors,
                                        "stableGeometryIds": stable_geometry_ids, "operationProfile": operation_profile,
                                        "settleFrames": settle_frames, "rebuildOnFirstProgress": rebuild_on_first_progress,
                                        "waitForLabels": wait_for_labels}
                                    row.update(browser_step(page, NATIVE_ROUND, options))
                                    # Immediate remount after the native destruction resolves.
                                    row["remount"] = browser_step(page, NATIVE_ROUND, options)["functional_pass"]
                                except Exception as error:
                                    row["error"] = safe_error(error, credentials)
                                    row["functional_pass"] = False
                                page.wait_for_timeout(500)
                                row["script_errors"], row["unhandled_rejections"], row["console_errors"] = (len(errors) - baseline[0], len(rejections) - baseline[1], len(console) - baseline[2])
                                row["lifecycle_pass"] = not any(row[name] for name in ("script_errors", "unhandled_rejections", "console_errors")) and not row.get("error")
                                rounds.append(row)
                    except Exception as error:
                        route["map_error"] = safe_error(error, credentials)
                    page.wait_for_timeout(2000)
                    results.append(evaluate_acceptance({"provider": provider, "native_sdk_control": True, "proxy_enabled": False,
                        "scheduling": "animation_frame" if frame_steps else "microtask",
                        "constructor_instrumentation": instrument_constructors,
                        "stable_geometry_ids": stable_geometry_ids,
                        "operation_profile": operation_profile,
                        "settle_frames": settle_frames,
                        "rebuild_on_first_progress": rebuild_on_first_progress,
                        "route_success": bool(route) and not route.get("error"), "route_points": len(route.get("path", [])),
                        "map_ready": bool(rounds) and all(row["functional_pass"] for row in rounds), "map_error": route.get("map_error"),
                        "rounds": rounds, "upstream_failures": failures, "script_errors": len(errors), "script_error_messages": errors,
                        "unhandled_rejections": len(rejections), "unhandled_rejection_messages": rejections, "console_error_messages": console}))
                finally:
                    context.close()
        finally:
            browser.close()
    return results


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    credentials = json.loads(os.environ.get("MAP_SMOKE_CREDENTIALS", "{}"))
    try:
        results = run(credentials)
    except Exception as error:
        print(json.dumps({"error": safe_error(error, credentials)}, ensure_ascii=True))
        raise SystemExit(1) from None
    print(json.dumps(results, ensure_ascii=True, indent=2))
    raise SystemExit(0 if smoke_results_passed(results) else 1)
