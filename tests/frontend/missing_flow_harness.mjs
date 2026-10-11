/**
 * 缺密码补全流程的**行为**测试（Node + 最小 DOM 桩）。
 *
 * 为什么必须有这个文件:
 *   源码级契约断言（字符串里有没有某个调用）抓不到控制流错误。
 *   本会话已经栽过一次——测试"通过"了，但函数根本没走到待测分支。
 *   所以这里真的把流程函数接上 DOM 桩跑起来，观察它的行为。
 *
 * 用法（由 tests/test_missing_password_flow_behavior.py 调用）:
 *   node missing_flow_harness.mjs '<流程源码>' '<场景名>'
 * 输出一行 JSON: {"ok": bool, "detail": str, "calls": {...}}
 */

const [, , flowSource, scenario] = process.argv;

// ── 最小 DOM 桩 ──────────────────────────────────────────────
class FakeClassList {
  constructor() {
    this.set = new Set();
  }
  add(...names) {
    names.forEach((n) => this.set.add(n));
  }
  remove(...names) {
    names.forEach((n) => this.set.delete(n));
  }
  contains(name) {
    return this.set.has(name);
  }
}

class FakeElement {
  constructor(id, tag = "div") {
    this.id = id;
    this.tagName = tag.toUpperCase();
    this.classList = new FakeClassList();
    this.dataset = {};
    this.children = [];
    this.textContent = "";
    this.innerHTML = "";
    this.value = "";
    this.checked = false;
    this.style = {};
    this.placeholder = "";
    this.readOnly = false;
    this.onclick = null;
    this.onchange = null;
    this._listeners = {};
  }
  appendChild(child) {
    this.children.push(child);
    return child;
  }
  addEventListener(type, fn) {
    (this._listeners[type] = this._listeners[type] || []).push(fn);
  }
  removeEventListener() {}
  /** 触发已注册的监听器（源码用的是 addEventListener("change")，不是 onchange） */
  dispatch(type) {
    (this._listeners[type] || []).forEach((fn) => fn({ target: this }));
  }
  focus() {}
  querySelectorAll(selector) {
    // 只支持测试需要的三种选择器
    const all = [];
    const walk = (node) => {
      node.children.forEach((c) => {
        all.push(c);
        walk(c);
      });
    };
    walk(this);
    if (selector.includes("checkbox")) {
      return all.filter((e) => String(e.dataset.role) === "checkbox");
    }
    if (selector.includes("input")) {
      return all.filter((e) => e.tagName === "INPUT");
    }
    return all;
  }
  querySelector() {
    return null;
  }
}

const elementRegistry = new Map();

function ensureElement(id) {
  if (!elementRegistry.has(id)) {
    const tag = id.includes("tbody") ? "tbody" : id.includes("input") ? "input" : "div";
    elementRegistry.set(id, new FakeElement(id, tag));
  }
  return elementRegistry.get(id);
}

// 预先注册流程会碰到的元素
[
  "missing-password-modal",
  "missing-password-message",
  "missing-password-list",
  "missing-password-select-modal",
  "missing-pass-select-tbody",
  "missing-pass-select-all",
  "missing-pass-select-count",
  "missing-pass-select-back-btn",
  "missing-pass-select-confirm-btn",
  "missing-pass-abandon-all-btn",
  "missing-pass-fill-all-btn",
  "missing-pass-fill-some-btn",
  "multi-add-user-modal",
  "multi-add-password-account",
  "multi-add-password-progress-text",
  "multi-add-abandon-all-btn",
  "multi-add-skip-current-btn",
  "multi-add-password-actions",
  "multi-add-username-group",
  "multi-add-tag-group",
  "multi-add-password-progress",
  "multi-add-password",
  "multi-add-username",
  "multi-add-tag",
  "import-result-modal",
].forEach(ensureElement);

globalThis.document = {
  body: new FakeElement("body"),
  getElementById: (id) => elementRegistry.get(id) || null,
  querySelector: () => null,
  createElement: (tag) => new FakeElement("", tag),
  addEventListener: () => {},
};

// legacy JS 里的全局选择器简写
globalThis.$ = (id) => elementRegistry.get(id) || null;

// 测试替身：记录调用
const log = { info: [], warning: [], error: [] };
globalThis.logMessage_Info = (m) => log.info.push(String(m));
globalThis.logMessage_Warning = (m) => log.warning.push(String(m));
globalThis.logMessage_Error = (...a) => log.error.push(a.map(String).join(" "));

const refreshCalls = [];
globalThis.openMultiAddUserModalForPassword = (username, tag) =>
  refreshCalls.push({ username, tag: tag ?? null });
globalThis.closeMultiAddUserModal = () => {};

// 暴露桩给测试脚本使用
globalThis.__element = (id) => elementRegistry.get(id) || null;
globalThis.__refreshCalls = refreshCalls;
globalThis.__log = log;

// ── 加载被测源码 ─────────────────────────────────────────────
// 流程源码是普通函数声明，直接 eval 到当前作用域。
// 额外暴露 missingFlowDoneCallback 的读写口，用于断言"收尾回调恰好触发一次"
// —— 这是导入结果弹窗能否弹出的唯一依据。
const factory = new Function(
  `${flowSource}
   return {
     startMissingPasswordFlow,
     openMissingPasswordSelection,
     startMissingPasswordQueue,
     showMissingPasswordProgress,
     advanceMissingPasswordQueue,
     finishMissingPasswordQueue,
     abandonRemainingMissingPasswords,
     flushMissingFlowDone,
     isMissingPasswordFlowActive,
     updateMissingSelectionCount,
     __setDone: (fn) => { missingFlowDoneCallback = fn; },
     __getDoneCount: () => missingFlowDoneCallback === null ? 0 : 1,
   };`,
);
const flow = factory();

// ── 场景 ─────────────────────────────────────────────────────
const MISSING = [
  { username: "acc1", tag: "A组" },
  { username: "acc2", tag: null },
  { username: "acc3", tag: null },
];

let scenarios = {};

scenarios["list-shows-all-without-truncation"] = () => {
  flow.startMissingPasswordFlow(MISSING);
  const list = globalThis.__element("missing-password-list");
  return {
    ok: list.children.length === 3,
    detail: `卡片数=${list.children.length}（应为 3，不限数量）`,
    calls: { stage: flow.isMissingPasswordFlowActive() },
  };
};

scenarios["list-message-shows-exact-count"] = () => {
  flow.startMissingPasswordFlow(MISSING);
  const msg = globalThis.__element("missing-password-message").textContent;
  return {
    ok: msg.includes("共 3 个账号缺少密码"),
    detail: `文案="${msg}"`,
    calls: {},
  };
};

scenarios["fill-some-requires-selection"] = () => {
  // 阶段 1 → 阶段 2
  flow.startMissingPasswordFlow(MISSING);
  globalThis.__element("missing-pass-fill-some-btn").onclick();
  return {
    ok:
      flow.isMissingPasswordFlowActive() &&
      globalThis.__element("missing-password-select-modal").classList.contains(
        "hidden",
      ) === false,
    detail: "应打开勾选弹窗",
    calls: {},
  };
};

scenarios["zero-selection-flows-to-done"] = () => {
  // 关键边界：选「补全部分」但一个都不勾选
  let doneCalls = 0;
  flow.startMissingPasswordFlow(MISSING);
  globalThis.__element("missing-pass-fill-some-btn").onclick();
  // 不勾任何账号，直接确认
  globalThis.__element("missing-pass-select-confirm-btn").onclick();

  const refreshBefore = refreshCalls.length;
  const active = flow.isMissingPasswordFlowActive();

  return {
    ok: !active && refreshBefore === 0,
    detail: `流程应结束且不进入补密码弹窗；active=${active}, 弹窗次数=${refreshBefore}`,
    calls: {},
  };
};

scenarios["zero-selection-fires-done-callback-exactly-once"] = () => {
  // 核心回归：选「补全部分」但一个都不勾选时，
  // 收尾回调必须触发且**恰好一次** —— 它决定导入结果弹窗会不会出现。
  let done = 0;
  flow.__setDone(() => {
    done += 1;
  });

  flow.startMissingPasswordFlow(MISSING);
  globalThis.__element("missing-pass-fill-some-btn").onclick();
  const refreshBefore = refreshCalls.length;
  globalThis.__element("missing-pass-select-confirm-btn").onclick();

  return {
    ok: done === 1 && refreshBefore === 0 && !flow.isMissingPasswordFlowActive(),
    detail: `doneCallback 次数=${done}（应为 1）；补密码弹窗次数=${refreshBefore}（应为 0）；active=${flow.isMissingPasswordFlowActive()}`,
    calls: { done },
  };
};

scenarios["done-callback-fires-after-full-queue"] = () => {
  let done = 0;
  flow.__setDone(() => {
    done += 1;
  });
  flow.startMissingPasswordFlow(MISSING);
  globalThis.__element("missing-pass-fill-all-btn").onclick();
  flow.advanceMissingPasswordQueue(); // 2/3
  flow.advanceMissingPasswordQueue(); // 3/3
  flow.advanceMissingPasswordQueue(); // 结束后收尾
  return {
    ok: done === 1,
    detail: `doneCallback 次数=${done}（应为 1）`,
    calls: { done },
  };
};

scenarios["done-callback-fires-on-abandon"] = () => {
  let done = 0;
  flow.__setDone(() => {
    done += 1;
  });
  flow.startMissingPasswordFlow(MISSING);
  globalThis.__element("missing-pass-abandon-all-btn").onclick();
  return {
    ok: done === 1 && !flow.isMissingPasswordFlowActive(),
    detail: `doneCallback 次数=${done}；active=${flow.isMissingPasswordFlowActive()}`,
    calls: { done },
  };
};

scenarios["done-callback-is-consumed-not-repeated"] = () => {
  // 收尾后再次触发不得重复调用（否则导入结果会弹两次）
  let done = 0;
  flow.__setDone(() => {
    done += 1;
  });
  flow.startMissingPasswordFlow(MISSING);
  globalThis.__element("missing-pass-abandon-all-btn").onclick();
  flow.flushMissingFlowDone();
  flow.flushMissingFlowDone();
  return {
    ok: done === 1,
    detail: `doneCallback 次数=${done}（应恰好 1，回调必须被消费掉）`,
    calls: { done },
  };
};

scenarios["no-selection-then-back-still-works"] = () => {
  // 阶段 2 点「返回」应回到阶段 1，且不触发收尾
  let done = 0;
  flow.__setDone(() => {
    done += 1;
  });
  flow.startMissingPasswordFlow(MISSING);
  globalThis.__element("missing-pass-fill-some-btn").onclick();
  globalThis.__element("missing-pass-select-back-btn").onclick();

  const list = globalThis.__element("missing-password-list");
  return {
    ok: done === 0 && flow.isMissingPasswordFlowActive(),
    detail: `返回后不应收尾；doneCallback=${done}，active=${flow.isMissingPasswordFlowActive()}，卡片数=${list.children.length}`,
    calls: { done },
  };
};

scenarios["selected-subset-honors-choices"] = () => {
  // 勾选其中 1 个：队列应只有它，进度分母为 1
  flow.startMissingPasswordFlow(MISSING);
  globalThis.__element("missing-pass-fill-some-btn").onclick();

  const tbody = globalThis.__element("missing-pass-select-tbody");
  const rows = tbody.children;
  // 勾选第二行（源码用 addEventListener("change") 绑定，因此要走 dispatch）
  const secondRow = rows[1];
  const cb = secondRow.children[0].children[0];
  cb.checked = true;
  cb.dispatch("change");

  const countText = globalThis.__element("missing-pass-select-count").textContent;
  globalThis.__element("missing-pass-select-confirm-btn").onclick();

  const progress = globalThis.__element(
    "multi-add-password-progress-text",
  ).textContent;
  const account = globalThis.__element("multi-add-password-account").textContent;

  return {
    ok:
      countText.includes("已选 1") &&
      progress.includes("当前进度 1/1") &&
      account === "acc2",
    detail: `count="${countText}" progress="${progress}" account="${account}"`,
    calls: {},
  };
};

scenarios["fill-all-enters-password-stage-with-progress"] = () => {
  flow.startMissingPasswordFlow(MISSING);
  globalThis.__element("missing-pass-fill-all-btn").onclick();

  const progress = globalThis.__element(
    "multi-add-password-progress-text",
  ).textContent;
  const account = globalThis.__element("multi-add-password-account").textContent;
  const abandon = globalThis.__element("multi-add-abandon-all-btn").textContent;

  return {
    ok:
      refreshCalls.length === 1 &&
      refreshCalls[0].username === "acc1" &&
      progress.includes("当前进度 1/3") &&
      progress.includes("还有 3 个账号待补密码") &&
      account === "acc1" &&
      abandon === "放弃所有无密码账号",
    detail: `progress="${progress}" account="${account}" abandon="${abandon}"`,
    calls: { refresh: refreshCalls.length },
  };
};

scenarios["second-account-abandon-label-changes"] = () => {
  flow.startMissingPasswordFlow(MISSING);
  globalThis.__element("missing-pass-fill-all-btn").onclick(); // 第 1 个
  flow.advanceMissingPasswordQueue(); // 推进到第 2 个

  const progress = globalThis.__element(
    "multi-add-password-progress-text",
  ).textContent;
  const abandon = globalThis.__element("multi-add-abandon-all-btn").textContent;

  return {
    ok:
      progress.includes("当前进度 2/3") &&
      progress.includes("还有 2 个账号待补密码") &&
      abandon === "放弃剩余 2 个账号",
    detail: `progress="${progress}" abandon="${abandon}"`,
    calls: {},
  };
};

scenarios["abandon-all-ends-flow"] = () => {
  flow.startMissingPasswordFlow(MISSING);
  globalThis.__element("missing-pass-fill-all-btn").onclick();
  globalThis.__element("multi-add-abandon-all-btn").onclick();

  return {
    ok: !flow.isMissingPasswordFlowActive(),
    detail: `active=${flow.isMissingPasswordFlowActive()}`,
    calls: {},
  };
};

scenarios["last-account-advance-finishes-flow"] = () => {
  flow.startMissingPasswordFlow(MISSING);
  globalThis.__element("missing-pass-fill-all-btn").onclick();
  flow.advanceMissingPasswordQueue();
  flow.advanceMissingPasswordQueue();
  flow.advanceMissingPasswordQueue();
  return {
    ok: !flow.isMissingPasswordFlowActive(),
    detail: `active=${flow.isMissingPasswordFlowActive()}`,
    calls: {},
  };
};

scenarios["empty-list-finishes-immediately"] = () => {
  flow.startMissingPasswordFlow([]);
  return {
    ok: !flow.isMissingPasswordFlowActive(),
    detail: `active=${flow.isMissingPasswordFlowActive()}`,
    calls: {},
  };
};

// ── 执行 ─────────────────────────────────────────────────────
const runner = scenarios[scenario];
if (!runner) {
  console.log(
    JSON.stringify({
      ok: false,
      detail: `未知场景: ${scenario}（可选: ${Object.keys(scenarios).join(", ")}）`,
      calls: {},
    }),
  );
  process.exit(0);
}

try {
  const result = runner();
  console.log(JSON.stringify(result));
} catch (err) {
  console.log(
    JSON.stringify({ ok: false, detail: `抛错: ${err.message}`, calls: {} }),
  );
}
