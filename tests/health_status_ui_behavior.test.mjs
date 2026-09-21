import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function extractFunctionSource(source, functionName) {
  const signature = `function ${functionName}`;
  const start = source.indexOf(signature);
  assert.notEqual(start, -1, `${functionName} should exist in scripts/main.new.js`);

  const bodyStart = source.indexOf('{', start);
  assert.notEqual(bodyStart, -1, `${functionName} should have a body`);

  let depth = 0;
  let inSingleQuote = false;
  let inDoubleQuote = false;
  let inTemplate = false;
  let inLineComment = false;
  let inBlockComment = false;

  for (let i = bodyStart; i < source.length; i += 1) {
    const char = source[i];
    const next = source[i + 1];
    const prev = source[i - 1];

    if (inLineComment) {
      if (char === '\n') inLineComment = false;
      continue;
    }
    if (inBlockComment) {
      if (prev === '*' && char === '/') inBlockComment = false;
      continue;
    }

    if (!inSingleQuote && !inDoubleQuote && !inTemplate) {
      if (char === '/' && next === '/') {
        inLineComment = true;
        continue;
      }
      if (char === '/' && next === '*') {
        inBlockComment = true;
        continue;
      }
    }

    if (!inDoubleQuote && !inTemplate && char === "'" && prev !== '\\') {
      inSingleQuote = !inSingleQuote;
      continue;
    }
    if (!inSingleQuote && !inTemplate && char === '"' && prev !== '\\') {
      inDoubleQuote = !inDoubleQuote;
      continue;
    }
    if (!inSingleQuote && !inDoubleQuote && char === '`' && prev !== '\\') {
      inTemplate = !inTemplate;
      continue;
    }

    if (inSingleQuote || inDoubleQuote || inTemplate) {
      continue;
    }

    if (char === '{') {
      depth += 1;
    } else if (char === '}') {
      depth -= 1;
      if (depth === 0) {
        return source.slice(start, i + 1);
      }
    }
  }

  throw new Error(`Failed to extract ${functionName}`);
}

function loadFunctions(functionNames) {
  const filePath = resolve('scripts/main.new.js');
  const source = readFileSync(filePath, 'utf8');
  const functionSources = functionNames.map((name) => extractFunctionSource(source, name));
  return Function(`${functionSources.join('\n\n')} return { ${functionNames.join(', ')} };`)();
}

test('health status presentation supports ok degraded error and unknown', () => {
  const { getHealthStatusPresentation } = loadFunctions(['getHealthStatusPresentation']);

  assert.deepEqual(getHealthStatusPresentation('ok'), {
    color: 'green',
    text: '运行正常',
  });

  assert.deepEqual(getHealthStatusPresentation('degraded'), {
    color: 'yellow',
    text: '部分异常',
  });

  assert.deepEqual(getHealthStatusPresentation('error'), {
    color: 'red',
    text: '核心异常',
  });

  assert.deepEqual(getHealthStatusPresentation('unknown'), {
    color: 'red',
    text: '状态未知',
  });
});

test('health detail rendering uses dedicated HTML sections and keeps JSON raw block', () => {
  const source = readFileSync(resolve('scripts/main.new.js'), 'utf8');
  const loadHealthStatusSource = extractFunctionSource(source, 'loadHealthStatus');
  const loadMobileHealthStatusSource = extractFunctionSource(source, 'loadMobileMultiHealthStatus');

  assert.ok(loadHealthStatusSource.includes('querySelector("pre")'));
  assert.ok(loadHealthStatusSource.includes('textContent = JSON.stringify(result, null, 2)'));
  assert.ok(loadHealthStatusSource.includes('运行时长'));
  assert.ok(loadHealthStatusSource.includes('result.summary'));
  assert.ok(loadHealthStatusSource.includes('result.components'));
  assert.ok(loadHealthStatusSource.includes('JSON 原文'));

  assert.ok(loadMobileHealthStatusSource.includes('querySelector("pre")'));
  assert.ok(loadMobileHealthStatusSource.includes('textContent = JSON.stringify(result, null, 2)'));
  assert.ok(loadMobileHealthStatusSource.includes('运行时长'));
  assert.ok(loadMobileHealthStatusSource.includes('result.summary'));
  assert.ok(loadMobileHealthStatusSource.includes('result.components'));
  assert.ok(loadMobileHealthStatusSource.includes('JSON 原文'));
});

test('health panel preserves scroll positions while refreshing', () => {
  const previousWindow = globalThis.window;
  const previousDocument = globalThis.document;
  globalThis.window = { scrollX: 0, scrollY: 0 };
  globalThis.document = { body: {}, scrollingElement: null };

  try {
    const { captureHealthScrollPositions, restoreHealthScrollPositions } = loadFunctions([
      'getHealthScrollableElements',
      'captureHealthScrollPositions',
      'restoreHealthScrollPositions',
    ]);
    const contentEl = {
      parentElement: null,
      scrollHeight: 100,
      clientHeight: 50,
      scrollTop: 37,
      scrollLeft: 4,
    };

    const snapshot = captureHealthScrollPositions(contentEl);
    contentEl.scrollTop = 0;
    contentEl.scrollLeft = 0;
    restoreHealthScrollPositions(snapshot);

    assert.equal(contentEl.scrollTop, 37);
    assert.equal(contentEl.scrollLeft, 4);
  } finally {
    globalThis.window = previousWindow;
    globalThis.document = previousDocument;
  }
});

test('desktop and both legacy mobile health loaders use diagnostics and no-store refreshes', () => {
  const source = readFileSync(resolve('scripts/main.new.js'), 'utf8');
  const desktopSource = extractFunctionSource(source, 'loadHealthStatus');
  const multiMobileSource = extractFunctionSource(source, 'loadMobileMultiHealthStatus');
  const mobileTabSource = extractFunctionSource(source, 'switchMobileAdminTab');
  const singleMobileCopySource = extractFunctionSource(source, 'copyAdminContentToPanelVersion');

  for (const loaderSource of [desktopSource, multiMobileSource]) {
    assert.ok(loaderSource.includes('captureHealthScrollPositions'));
    assert.ok(loaderSource.includes('restoreHealthScrollPositions'));
    assert.ok(loaderSource.includes('memory_diagnostics'));
    assert.ok(loaderSource.includes('cache: "no-store"'));
    assert.ok(loaderSource.includes('showHealthRefreshFailure'));
  }

  assert.ok(mobileTabSource.includes('loadHealthStatus().finally'));
  assert.ok(!mobileTabSource.includes('setTimeout(() => copyAdminContentToPanelVersion("health"), 500)'));
  assert.ok(!mobileTabSource.includes('setTimeout(() => copyAdminContentToMobile("health", contentId), 500)'));
  assert.ok(singleMobileCopySource.includes('captureHealthScrollPositions'));
  assert.ok(singleMobileCopySource.includes('restoreHealthScrollPositions'));
});
