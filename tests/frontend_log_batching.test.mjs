import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(resolve('scripts/main.js'), 'utf8');
const redactionStart = source.indexOf('const CLIENT_LOG_SENSITIVE_KEYS =');
const redactionEnd = source.indexOf('const mobileAdminUnifiedScrollState =', redactionStart);
const batchingStart = source.indexOf('// ==================== 日志批处理逻辑');
const batchingEnd = source.indexOf('const routeDiagnosticMessages =', batchingStart);

function createHarness({ failUpload = false } = {}) {
  const timers = new Map();
  const requests = [];
  const originalErrors = [];
  const initialDataCalls = [];
  let nextTimer = 1;
  let active = 0;
  let maxActive = 0;
  let context;
  function upload(url, options) {
    active += 1;
    maxActive = Math.max(maxActive, active);
    return new Promise((resolveUpload, rejectUpload) => {
      requests.push({
        url, options,
        finish() {
          active -= 1;
          if (failUpload === 'network') rejectUpload(new Error('upload unavailable'));
          else if (failUpload === 'http') resolveUpload({ ok: false, status: 503 });
          else resolveUpload({ ok: true, status: 200 });
        },
      });
    });
  }
  const console = {
    log() {}, info() {}, warn() {}, debug() {},
    error: (...args) => originalErrors.push(args),
  };
  context = vm.createContext({
    console,
    window: { addEventListener() {} },
    sessionUUID: 'business-session',
    isInNetworkErrorState: false,
    getApiRequestSessionHeaderValue: () => 'business-session',
    addAdminViewOriginSessionHeader: headers => {
      headers['X-Admin-Origin-Session-ID'] = 'origin-session';
    },
    setTimeout(callback, delay) {
      const id = nextTimer++;
      timers.set(id, { callback, delay });
      return id;
    },
    clearTimeout: id => timers.delete(id),
    fetch: upload,
    loadInitialData(options) {
      initialDataCalls.push(options);
      context.console.info('[初始化] get_initial_data 请求开始');
      return upload('/api/get_initial_data', { body: JSON.stringify(options) });
    },
  });
  const exports = `
    globalThis.batchLogs = {
      flush: flushLogQueue,
      schedule: scheduleLogFlush,
      enqueue(entry) { logQueue.push(entry); scheduleLogFlush(); },
      queue() { return logQueue; },
    };
  `;
  vm.runInContext(
    `${source.slice(redactionStart, redactionEnd)}\n${source.slice(batchingStart, batchingEnd)}\n${exports}`,
    context,
  );
  return {
    context, requests, timers, originalErrors, initialDataCalls,
    maxActive: () => maxActive,
    async runTimer() {
      assert.equal(timers.size, 1, 'a pending batch has one timer');
      const [id, timer] = timers.entries().next().value;
      timers.delete(id);
      const result = timer.callback();
      await Promise.resolve();
      return { result };
    },
    async settle() {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    },
  };
}

test('a log batch uses the dedicated endpoint without reinitializing business data', async () => {
  const harness = createHarness();
  harness.context.console.info('request password=temporary-secret');
  await harness.runTimer();

  assert.equal(harness.initialDataCalls.length, 0);
  assert.equal(harness.requests.length, 1);
  const request = harness.requests[0];
  assert.equal(request.url, '/api/log_frontend');
  assert.equal(request.options.method, 'POST');
  assert.equal(request.options.credentials, 'include');
  assert.equal(request.options.headers['Content-Type'], 'application/json');
  assert.equal(request.options.headers['X-Session-ID'], 'business-session');
  assert.equal(request.options.headers['X-Admin-Origin-Session-ID'], 'origin-session');
  const payload = JSON.parse(request.options.body);
  assert.equal(payload.batch.length, 1);
  assert.equal(payload.batch[0].message, 'request password=[已隐藏]');
  assert.equal(payload.batch[0].level, 'INFO');
  assert.equal(payload.batch[0].source, '第三方JS');
  assert.equal(harness.context.batchLogs.queue().length, 0);
  request.finish();
  await harness.settle();
  assert.equal(harness.timers.size, 0);
});

test('logs arriving during an upload wait for its completion and form the next batch', async () => {
  const harness = createHarness();
  harness.context.console.info('first');
  await harness.runTimer();
  harness.context.console.info('second');
  harness.context.console.info('third');
  await harness.context.batchLogs.flush();

  assert.equal(harness.requests.length, 1, 'pending upload must not overlap another upload');
  assert.equal(harness.timers.size, 0, 'new batch waits until upload completion');
  harness.requests[0].finish();
  await harness.settle();
  await harness.runTimer();

  assert.equal(harness.requests.length, 2);
  assert.deepEqual(JSON.parse(harness.requests[1].options.body).batch.map(item => item.message), ['second', 'third']);
  assert.equal(harness.maxActive(), 1);
  harness.requests[1].finish();
  await harness.settle();
  assert.equal(harness.timers.size, 0);
});

for (const failure of ['network', 'http']) {
  test(`a ${failure} upload failure uses the original console without a feedback batch`, async () => {
    const harness = createHarness({ failUpload: failure });
    harness.context.console.info('first');
    await harness.runTimer();
    harness.requests[0].finish();
    await harness.settle();

    assert.equal(harness.originalErrors.length, 1);
    assert.equal(harness.context.batchLogs.queue().length, 0);
    assert.equal(harness.timers.size, 0);
    assert.equal(harness.initialDataCalls.length, 0);
    assert.equal(harness.requests.length, 1);
  });
}
