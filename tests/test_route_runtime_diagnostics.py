import ast
import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import main
from background_task_manager import ChromeBrowserPool
from map_error_catalog import map_error_retry_policy


class TestRouteRuntimeDiagnostics(unittest.TestCase):
    def setUp(self):
        origin = patch.object(main, "resolve_backend_page_origin", return_value=("https://runtime.test", "request"))
        origin.start()
        self.addCleanup(origin.stop)

    def _provider_source(self, provider):
        module = ast.parse(Path(main.__file__).read_text(encoding="utf-8"))
        helper = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == f"_plan_route_path_with_{provider}_runtime")
        call = next(node for node in ast.walk(helper) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "execute_js")
        return call.args[1].value

    def _execute_provider(self, provider, prelude, args):
        args = list(args)
        args[2] = dict(args[2], _map_error_retry_policy=map_error_retry_policy(provider))
        code = prelude + "\nconst fn=" + self._provider_source(provider) + ";\nfn(" + json.dumps(args) + ").then(result=>console.log(JSON.stringify(result)));"
        proc = subprocess.run(["node", "-e", code], capture_output=True, encoding="utf-8", timeout=10)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def _failure_prelude(self, code, http_status=200):
        return r'''
globalThis.window=globalThis;
const failureCode=FAILURE_CODE;
const nativeTimeout=setTimeout;
globalThis.setTimeout=(fn,delay)=>delay>=15000?0:nativeTimeout(fn,0);
globalThis.clearTimeout=()=>{};
globalThis.document={getElementById:()=>null,createElement:()=>({style:{}}),body:{appendChild(){}},
head:{appendChild(script){const callback=new URL(script.src).searchParams.get('callback');globalThis[callback]({status:failureCode,message:'vendor failure'});}}};
globalThis.fetch=async()=>({ok:HTTP_STATUS===200,status:HTTP_STATUS,text:async()=>JSON.stringify({code:failureCode,msg:'vendor failure'})});
globalThis.BMAP_STATUS_SUCCESS=0;
globalThis.BMap={Point:class{constructor(lng,lat){this.lng=lng;this.lat=lat;}},
Map:class{centerAndZoom(){}},WalkingRoute:class{constructor(map,options){this.options=options;}getStatus(){return failureCode;}search(){this.options.onSearchComplete({getPlan:()=>null});}}};
globalThis.AMapLoader={load:async()=>{}};
globalThis.AMap={LngLat:class{constructor(lng,lat){this.lng=lng;this.lat=lat;}},Walking:class{search(a,b,cb){cb('error',{info:failureCode});}}};
'''.replace("FAILURE_CODE", json.dumps(code)).replace("HTTP_STATUS", str(http_status))

    def _failure_args(self, provider, retries=99):
        args = [[[113.39, 22.52], [113.40, 22.53]], "test-key", {"api_retries": retries, "api_retry_delay_s": 0}]
        return args + ([[], "walking"] if provider == "amap" else ["walking"])

    def test_known_permanent_errors_do_not_consume_additional_retry_waves(self):
        cases = (("amap", "INVALID_USER_SCODE"), ("amap", "INVALID_USER_DOMAIN"),
                 ("tencent", 121), ("tencent", 408), ("baidu", 4), ("baidu", 6),
                 ("tianditu", 301001), ("tianditu", 301012), ("tianditu", 308011))
        for provider, code in cases:
            with self.subTest(provider=provider, code=code):
                result = self._execute_provider(provider, self._failure_prelude(code), self._failure_args(provider))
                segment = result["diagnostic"]["segments"][0]
                self.assertIn("error", result)
                self.assertEqual(str(code), str(segment["error_code"]))
                self.assertEqual(1, segment["attempts"])
                self.assertEqual(1, result["diagnostic"]["waves"])

    def test_transient_failures_have_bounded_real_attempts_even_with_large_retry_budget(self):
        cases = (("amap", "SERVICE_NOT_AVAILABLE", 200, 2), ("tencent", 120, 200, 10),
                 ("tencent", 510, 200, 2), ("baidu", 7, 200, 2), ("baidu", 8, 200, 2),
                 ("tianditu", 99999, 503, 2))
        for provider, code, http_status, attempts in cases:
            with self.subTest(provider=provider, code=code):
                result = self._execute_provider(provider, self._failure_prelude(code, http_status), self._failure_args(provider))
                self.assertEqual(attempts, result["diagnostic"]["segments"][0]["attempts"])
                self.assertEqual(2, result["diagnostic"]["waves"])
                self.assertLessEqual(len(result["diagnostic"]["segments"][0]["callback_history"]), 4)

    def test_tencent_qps_retry_success_retains_history_without_final_error(self):
        prelude = self._failure_prelude(120) + r'''
let requests=0;
document.head.appendChild=(script)=>{
 const callback=new URL(script.src).searchParams.get('callback');
 globalThis[callback](++requests===1?{status:120,message:'QPS limit'}:{status:0,result:{routes:[{polyline:[22.52,113.39,10000,10000]}]}});
};
'''
        result = self._execute_provider("tencent", prelude, self._failure_args("tencent"))
        self.assertNotIn("error", result)
        self.assertEqual([{"lng": 113.39, "lat": 22.52}, {"lng": 113.4, "lat": 22.53}], result["path"])
        self.assertEqual(2, result["diagnostic"]["segments"][0]["attempts"])
        self.assertEqual(["120", "0"], [row["status"] for row in result["diagnostic"]["segments"][0]["callback_history"]])
        self.assertEqual(1, result["diagnostic"]["waves"])

    def test_tianditu_request_mode_uses_walking_three_and_driving_zero(self):
        prelude = self._failure_prelude(308010) + r'''
fetch=async(url)=>{
 const post=JSON.parse(new URL(url).searchParams.get('postStr'));
 return {ok:true,status:200,text:async()=>JSON.stringify({code:308010,msg:'STYLE_'+post.style})};
};
'''
        for mode, style in (("walking", "3"), ("driving", "0")):
            with self.subTest(mode=mode):
                args = self._failure_args("tianditu", retries=0)
                args[3] = mode
                result = self._execute_provider("tianditu", prelude, args)
                self.assertIn("STYLE_" + style, result["error"])

    def test_common_entry_attaches_explanations_without_losing_vendor_codes(self):
        cases = (("amap", "INVALID_USER_SCODE", "安全码未通过验证"),
                 ("amap", "INVALID_USER_DOMAIN", "绑定域名无效"),
                 ("tencent", 408, "自定义 Referer 错误"),
                 ("baidu", 4, "路线 SDK 密钥无效"),
                 ("tianditu", 301012, "权限类型错误"))
        for provider, code, explanation in cases:
            with self.subTest(provider=provider, code=code):
                payload = {"error": "vendor failure", "diagnostic": {"segment": 1, "segments": [{"segment": 1, "error_code": code}]}}
                with patch.object(main, "chrome_pool", SimpleNamespace(), create=True), patch.object(
                    main, "_plan_route_with_map_provider", return_value={"provider": provider}
                ), patch.object(main, f"_plan_route_path_with_{provider}_runtime", return_value=payload):
                    result = main._plan_route_path_with_provider_runtime("session-1", [[113.39, 22.52], [113.40, 22.53]])
                self.assertEqual(code, result["error_code"])
                self.assertEqual(explanation, result["error_explanation"])
                self.assertTrue(result["error_hint"])
                self.assertTrue(result["diagnostic_id"])

    def test_common_entry_always_adds_identifier_and_contains_executor_exception(self):
        plan = {"provider": "amap", "provider_config": {"js_key": "known-secret"}}
        pool = SimpleNamespace(get_context=Mock(return_value={"page": Mock()}))
        with patch.object(main, "chrome_pool", pool, create=True), patch.object(
            main, "_plan_route_with_map_provider", return_value=plan
        ), patch.object(main, "_install_map_runtime_guard"), patch.object(
            main, "_plan_route_path_with_amap_runtime", side_effect=RuntimeError("known-secret rejected")
        ):
            result = main._plan_route_path_with_provider_runtime("session-1", [[1, 2], [3, 4]])
        self.assertTrue(result["diagnostic_id"])
        self.assertIn("rejected", result["error"])
        self.assertNotIn("known-secret", result["error"])

    def test_configuration_failure_is_returned_with_identifier(self):
        with patch.object(main, "_read_config_ini", side_effect=RuntimeError("bad config")):
            result = main._plan_route_path_with_provider_runtime("session-1", [[1, 2], [3, 4]])
        self.assertTrue(result["diagnostic_id"])
        self.assertIn("bad config", result["error"])

    def test_success_also_has_identifier(self):
        pool = SimpleNamespace(get_context=Mock(return_value={"page": Mock()}))
        with patch.object(main, "chrome_pool", pool, create=True), patch.object(
            main, "_plan_route_with_map_provider", return_value={"provider": "amap"}
        ), patch.object(main, "_install_map_runtime_guard"), patch.object(
            main, "_plan_route_path_with_amap_runtime", return_value={"path": [{"lng": 1, "lat": 2}]}
        ):
            result = main._plan_route_path_with_provider_runtime("session-1", [[1, 2], [3, 4]])
        self.assertTrue(result["diagnostic_id"])
        self.assertIn("path", result)

    def test_common_entry_rejects_missing_empty_and_unusable_geometry(self):
        for provider in ("amap", "tencent", "tianditu", "baidu"):
            for payload in ({}, {"path": []}, {"path": [None, {"lng": "bad", "lat": 2}, [float("nan"), 3]]}):
                with self.subTest(provider=provider, payload=payload):
                    pool = SimpleNamespace(get_context=Mock(return_value={"page": Mock()}))
                    with patch.object(main, "chrome_pool", pool, create=True), patch.object(
                        main, "_plan_route_with_map_provider", return_value={"provider": provider}
                    ), patch.object(main, "_install_map_runtime_guard"), patch.object(
                        main, f"_plan_route_path_with_{provider}_runtime", return_value=dict(payload)
                    ):
                        result = main._plan_route_path_with_provider_runtime("session-1", [[1, 2], [3, 4]])
                    self.assertTrue(result["diagnostic_id"])
                    self.assertIn("几何", result.get("error", ""))
                    self.assertFalse(result.get("path"))

    def test_common_entry_accepts_normalizable_nonempty_geometry(self):
        for provider in ("amap", "tencent", "tianditu", "baidu"):
            with self.subTest(provider=provider):
                pool = SimpleNamespace(get_context=Mock(return_value={"page": Mock()}))
                with patch.object(main, "chrome_pool", pool, create=True), patch.object(
                    main, "_plan_route_with_map_provider", return_value={"provider": provider}
                ), patch.object(main, "_install_map_runtime_guard"), patch.object(
                    main, f"_plan_route_path_with_{provider}_runtime", return_value={"path": [["1", "2"], [3, 4]]}
                ):
                    result = main._plan_route_path_with_provider_runtime("session-1", [[1, 2], [3, 4]])
                self.assertNotIn("error", result)
                self.assertEqual([{"lng": 1.0, "lat": 2.0}, {"lng": 3.0, "lat": 4.0}], result["path"])

    def test_context_logs_share_id_and_only_include_failed_segment_endpoints(self):
        pool = SimpleNamespace(get_context=Mock(return_value={"page": Mock()}))
        payload = {"error": "Segment 2 failed", "diagnostic": {
            "segment": 2, "waves": 2, "segments": [{
                "segment": 2, "attempts": 2, "reason": "known-secret rejected",
                "callback_history": [{"attempt": 1, "status": "error", "reason": "first known-secret failure"}],
            }],
        }}
        with patch.object(main, "chrome_pool", pool, create=True), patch.object(
            main, "_plan_route_with_map_provider", return_value={
                "provider": "amap", "actual_mode": "driving", "provider_config": {"js_key": "known-secret"},
            }
        ), patch.object(main, "_install_map_runtime_guard"), patch.object(
            main, "_plan_route_path_with_amap_runtime", return_value=payload
        ), self.assertLogs(level="DEBUG") as captured:
            result = main._plan_route_path_with_provider_runtime(
                "session-1", [[10, 11], [20, 21], [30, 31], [40, 41]],
                guard_label="SingleManualPathPlanning",
            )
        logs = "\n".join(captured.output)
        for phase in ("start", "result"):
            entry = next(line for line in captured.output if f"phase={phase}" in line)
            self.assertIn(f"id={result['diagnostic_id']}", entry)
            self.assertIn("guard_label=SingleManualPathPlanning", entry)
            self.assertIn("actual_mode=driving", entry)
            self.assertIn("waypoint_count=4", entry)
        self.assertIn('"lng": 20.0', logs)
        self.assertIn('"lng": 30.0', logs)
        self.assertNotIn('"lng": 10.0', logs)
        self.assertNotIn('"lng": 40.0', logs)
        self.assertNotIn("known-secret", logs)
        self.assertIn("callback_history", logs)
        self.assertEqual(4, result["diagnostic"]["waypoint_count"])
        self.assertEqual("driving", result["diagnostic"]["actual_mode"])

    def test_large_diagnostic_with_callback_history_stays_within_four_kib(self):
        pool = SimpleNamespace(get_context=Mock(return_value={"page": Mock()}))
        payload = {"error": "Segment 2 failed", "diagnostic": {
            "segment": 2, "waves": 2, "segments": [{
                "segment": index, "attempts": 8, "reason": "回调失败" * 200,
                "callback_detail": "回调数据" * 300,
                "callback_history": [{"attempt": attempt, "status": "error", "reason": "中间失败" * 80} for attempt in range(1, 5)],
            } for index in range(1, 13)],
        }}
        with patch.object(main, "chrome_pool", pool, create=True), patch.object(
            main, "_plan_route_with_map_provider", return_value={"provider": "amap"}
        ), patch.object(main, "_install_map_runtime_guard"), patch.object(
            main, "_plan_route_path_with_amap_runtime", return_value=payload
        ):
            result = main._plan_route_path_with_provider_runtime("session-1", [[10, 11], [20, 21], [30, 31]])
        for ascii_only in (False, True):
            self.assertLessEqual(len(json.dumps(result["diagnostic"], ensure_ascii=ascii_only).encode("utf-8")), 4096)
        self.assertEqual(2, result["diagnostic"]["segment"])
        self.assertTrue(result["diagnostic"]["segments"][0]["callback_history"])

    def test_other_provider_failures_record_real_attempts_and_status(self):
        prelude = r'''
globalThis.window=globalThis;
const nativeTimeout=setTimeout;
globalThis.setTimeout=(fn,delay)=>delay>=15000?0:nativeTimeout(fn,0);
globalThis.clearTimeout=()=>{};
globalThis.document={getElementById:()=>null,createElement:()=>({style:{}}),body:{appendChild(){}},
head:{appendChild(script){const callback=new URL(script.src).searchParams.get('callback');globalThis[callback]({status:110,message:'INVALID_USER_KEY'});}}};
globalThis.fetch=async()=>({ok:false,status:403,text:async()=> 'permission denied'});
globalThis.BMAP_STATUS_SUCCESS=0;
globalThis.BMap={Point:class{constructor(lng,lat){this.lng=lng;this.lat=lat;}},
Map:class{centerAndZoom(){}},WalkingRoute:class{constructor(map,options){this.options=options;}getStatus(){return 2;}search(){this.options.onSearchComplete({getPlan:()=>null});}}};
'''
        for provider, mode, expected, status in (("tencent", "walking", "INVALID_USER_KEY", "110"), ("tianditu", "driving", "permission denied", "response"), ("baidu", "walking", "状态码：2", "2")):
            with self.subTest(provider=provider):
                result = self._execute_provider(provider, prelude, [[[1, 2], [3, 4]], "fake-key", {"api_retries": 0, "api_retry_delay_s": 0}, mode])
                self.assertIn(expected, result["error"])
                self.assertEqual(1, result["diagnostic"]["waves"])
                self.assertEqual(1, result["diagnostic"]["segments"][0]["attempts"])
                self.assertEqual(status, result["diagnostic"]["segments"][0]["status"])
                if provider == "tianditu":
                    self.assertEqual(403, result["diagnostic"]["segments"][0]["http_status"])

    def test_each_provider_keeps_bounded_retry_callback_history(self):
        prelude = r'''
globalThis.window=globalThis;
const nativeTimeout=setTimeout;
globalThis.setTimeout=(fn,delay)=>delay>=15000?0:nativeTimeout(fn,0);
globalThis.clearTimeout=()=>{};
globalThis.document={getElementById:()=>null,createElement:()=>({style:{}}),body:{appendChild(){}},
head:{appendChild(script){const callback=new URL(script.src).searchParams.get('callback');globalThis[callback]({status:510,message:'RETRY_FAILURE'});}}};
globalThis.fetch=async()=>({ok:false,status:503,text:async()=> 'RETRY_FAILURE'});
globalThis.BMAP_STATUS_SUCCESS=0;
globalThis.BMap={Point:class{constructor(lng,lat){this.lng=lng;this.lat=lat;}},
Map:class{centerAndZoom(){}},WalkingRoute:class{constructor(map,options){this.options=options;}getStatus(){return 7;}search(){this.options.onSearchComplete({getPlan:()=>null});}}};
globalThis.AMapLoader={load:async()=>{}};
globalThis.AMap={LngLat:class{constructor(lng,lat){this.lng=lng;this.lat=lat;}},Walking:class{search(a,b,cb){cb('error','RETRY_FAILURE');}}};
'''
        for provider in ("amap", "tencent", "tianditu", "baidu"):
            with self.subTest(provider=provider):
                args = [[[1, 2], [3, 4]], "fake-key", {"api_retries": 1, "api_retry_delay_s": 0}]
                args += [[], "walking"] if provider == "amap" else ["driving" if provider == "tianditu" else "walking"]
                result = self._execute_provider(provider, prelude, args)
                segment = result["diagnostic"]["segments"][0]
                self.assertEqual(2, segment["attempts"])
                self.assertEqual([1, 2], [item["attempt"] for item in segment["callback_history"]])
                self.assertTrue(all("status" in item and "response_type" in item for item in segment["callback_history"]))

    def test_amap_callback_history_caps_entries_and_counts_dropped_callbacks(self):
        prelude = r'''
globalThis.window=globalThis;
const nativeTimeout=setTimeout;
globalThis.setTimeout=(fn,delay)=>delay>=15000?0:nativeTimeout(fn,0);
globalThis.clearTimeout=()=>{};
globalThis.AMapLoader={load:async()=>{}};
let requests=0;
globalThis.AMap={LngLat:class{constructor(lng,lat){this.lng=lng;this.lat=lat;}},
Walking:class{search(a,b,cb){requests++;cb('error',requests<5?'CUQPS known-secret':'REJECT_'+requests);}}};
'''
        result = self._execute_provider("amap", prelude, [
            [[1, 2], [3, 4]], "known-secret", {"api_retries": 1, "api_retry_delay_s": 0}, [], "walking",
        ])
        segment = result["diagnostic"]["segments"][0]
        self.assertEqual(6, segment["attempts"])
        self.assertEqual([3, 4, 5, 6], [item["attempt"] for item in segment["callback_history"]])
        self.assertEqual(2, segment["callbacks_dropped"])
        self.assertNotIn("known-secret", json.dumps(segment))

    def test_worker_exception_keeps_redacted_reason_and_clears_active_context(self):
        page = Mock()
        page.evaluate.side_effect = RuntimeError("known-secret net::ERR_FAILED")
        pool = ChromeBrowserPool.__new__(ChromeBrowserPool)
        pool._initialized = True
        pool._contexts = {"session-1": {"page": page, "context": Mock()}}
        result = pool._do_execute_js("session-1", "script", [], diagnostic_context={"diagnostic_id": "diag-one", "provider": "amap", "sensitive_values": ["known-secret"]})
        self.assertFalse(result["success"])
        self.assertIn("net::ERR_FAILED", result["error"])
        self.assertNotIn("known-secret", result["error"])
        self.assertIsNone(pool._contexts["session-1"]["route_diagnostic_context"])

    def test_worker_listeners_attach_once_and_only_capture_active_command(self):
        listeners = {}
        page = Mock()
        page.on.side_effect = lambda event, callback: listeners.setdefault(event, []).append(callback)
        pool = ChromeBrowserPool.__new__(ChromeBrowserPool)
        pool._initialized = True
        pool._contexts = {"session-1": {"page": page, "context": Mock()}}

        def evaluate(*_args):
            listeners["requestfailed"][0](SimpleNamespace(url="https://maps.test/route?key=known-secret", failure="net::ERR_FAILED"))
            listeners["pageerror"][0](RuntimeError("known-secret runtime failure"))
            return {"error": "SDK error"}

        page.evaluate.side_effect = evaluate
        context = {"diagnostic_id": "diag-one", "provider": "amap", "sensitive_values": ["known-secret"]}
        result = pool._do_execute_js("session-1", "script", [], diagnostic_context=context)
        self.assertIn("browser_events", result["result"]["diagnostic"])
        events = json.dumps(result["result"]["diagnostic"]["browser_events"])
        self.assertIn("net::ERR_FAILED", events)
        self.assertNotIn("known-secret", events)
        page.evaluate.side_effect = lambda *_args: {"path": []}
        pool._do_execute_js("session-1", "script", [], diagnostic_context=context)
        self.assertEqual(1, len(listeners["requestfailed"]))
        self.assertEqual(1, len(listeners["pageerror"]))
        self.assertIsNone(pool._contexts["session-1"].get("route_diagnostic_context"))
        dialog = Mock()
        listeners["dialog"][0](dialog)
        dialog.dismiss.assert_called_once()

    def test_malformed_planner_result_is_contained(self):
        with patch.object(main, "_plan_route_with_map_provider", return_value=None):
            result = main._plan_route_path_with_provider_runtime("session-1", [[1, 2], [3, 4]])
        self.assertTrue(result["diagnostic_id"])
        self.assertIn("error", result)

    def test_amap_callback_string_and_object_keep_reason_and_actual_attempts(self):
        module = ast.parse(Path(main.__file__).read_text(encoding="utf-8"))
        helper = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "_plan_route_path_with_amap_runtime")
        call = next(node for node in ast.walk(helper) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "execute_js")
        source = call.args[1].value
        for payload in ("INVALID_USER_KEY", {"message": "INVALID_USER_KEY", "infocode": "10001"}):
            with self.subTest(payload=payload):
                prelude = r'''
globalThis.window = globalThis;
const nativeTimeout = setTimeout;
globalThis.setTimeout = (fn, delay) => delay >= 15000 ? 0 : nativeTimeout(fn, 0);
globalThis.clearTimeout = () => {};
globalThis.AMapLoader = {load: async () => {}};
globalThis.AMap = {LngLat: class {constructor(lng,lat){this.lng=lng;this.lat=lat;}},
 Walking: class {search(a,b,cb){cb('error', PAYLOAD);}}};
'''.replace("PAYLOAD", json.dumps(payload))
                code = prelude + "\nconst fn=" + source + ";\nfn([[[1,2],[3,4]], 'known-secret', {api_retries:0,api_retry_delay_s:0,api_queue_interval_s:0}, [], 'walking']).then(result=>console.log(JSON.stringify(result)));"
                proc = subprocess.run(["node", "-e", code], capture_output=True, encoding="utf-8", timeout=10)
                self.assertEqual(0, proc.returncode, proc.stderr)
                result = json.loads(proc.stdout)
                self.assertIn("INVALID_USER_KEY", result["error"])
                self.assertEqual(1, result["diagnostic"]["segments"][0]["attempts"])
                self.assertEqual(1, result["diagnostic"]["waves"])
                self.assertIn("1 waves", result["error"])

    def test_amap_complete_without_geometry_explains_callback_structure(self):
        cases = (
            ({"info": "OK", "routes": [], "error": {"code": "EMPTY_GEOMETRY", "detail": "upstream empty", "key": "known-secret"}}, 0, 0, 0),
            ({"info": "OK", "routes": [{"steps": []}]}, 1, 0, 0),
            ({"info": "OK", "routes": [{"steps": [{"path": [{"lng": "bad", "lat": 2}]}]}]}, 1, 1, 1),
        )
        for payload, routes_count, steps_count, path_count in cases:
            with self.subTest(payload=payload):
                prelude = r'''
globalThis.window = globalThis;
const nativeTimeout = setTimeout;
globalThis.setTimeout = (fn, delay) => delay >= 15000 ? 0 : nativeTimeout(fn, 0);
globalThis.clearTimeout = () => {};
globalThis.AMapLoader = {load: async () => {}};
globalThis.AMap = {LngLat: class {constructor(lng,lat){this.lng=lng;this.lat=lat;}},
 Walking: class {search(a,b,cb){cb('complete', PAYLOAD);}}};
'''.replace("PAYLOAD", json.dumps(payload))
                result = self._execute_provider("amap", prelude, [
                    [[1, 2], [3, 4]], "known-secret",
                    {"api_retries": 0, "api_retry_delay_s": 0, "api_queue_interval_s": 0}, [], "walking",
                ])
                self.assertIn("无可用几何", result.get("error", ""))
                segment = result["diagnostic"]["segments"][0]
                self.assertEqual("complete", segment["status"])
                self.assertEqual(routes_count, segment["routes_count"])
                self.assertEqual(steps_count, segment["steps_count"])
                self.assertEqual(path_count, segment["path_count"])
                self.assertEqual(0, segment["valid_path_count"])
                callback = json.loads(segment["callback_detail"])
                self.assertEqual("OK", callback["info"])
                self.assertNotIn("known-secret", json.dumps(callback))
                if "error" in payload:
                    self.assertEqual("EMPTY_GEOMETRY", callback["error"]["code"])


if __name__ == "__main__":
    unittest.main()
