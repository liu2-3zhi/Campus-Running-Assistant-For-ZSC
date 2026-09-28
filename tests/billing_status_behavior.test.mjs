import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function extractFunctionSource(source, functionName) {
  const signature = `function ${functionName}`;
  const start = source.indexOf(signature);
  assert.notEqual(start, -1, `${functionName} should exist in scripts/main.js`);

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
  const filePath = resolve('scripts/main.js');
  const source = readFileSync(filePath, 'utf8');
  const functionSources = functionNames.map((name) => extractFunctionSource(source, name));
  return Function(`${functionSources.join('\n\n')} return { ${functionNames.join(', ')} };`)();
}

test('terminal statuses are not payable', () => {
  const { isBillingStatusPayable } = loadFunctions(['isBillingStatusPayable']);
  assert.equal(isBillingStatusPayable('paid'), false);
  assert.equal(isBillingStatusPayable('refunded_partial'), false);
  assert.equal(isBillingStatusPayable('refunded_full'), false);
  assert.equal(isBillingStatusPayable('pending'), true);
  assert.equal(isBillingStatusPayable('closed'), true);
});

test('network connectivity guidance text is complete', () => {
  const { getServerConnectionGuidanceMessage } = loadFunctions(['getServerConnectionGuidanceMessage']);
  const message = getServerConnectionGuidanceMessage();

  assert.equal(typeof message, 'string');
  assert.ok(message.includes('请确认设备已正常联网。'));
  assert.ok(message.includes('运营商网络干扰'));
  assert.ok(message.includes('切换网络'));
  assert.ok(message.includes('启用加密 DNS'));
  assert.ok(message.includes('使用国际联网工具'));
  assert.ok(message.includes('广告拦截工具'));
  assert.ok(message.includes('开关飞行模式并重启浏览器'));
  assert.ok(message.includes('刷新 DNS 缓存后重新访问'));
  assert.ok(message.includes('若问题持续存在，请联系支持人员。'));
});

test('network connectivity guidance text uses structured popup html', () => {
  const source = readFileSync(resolve('scripts/main.js'), 'utf8');
  const guidanceSource = extractFunctionSource(source, 'getServerConnectionGuidanceMessage');

  assert.ok(guidanceSource.includes('<div style="'));
  assert.ok(guidanceSource.includes('<ul style="'));
  assert.ok(guidanceSource.includes('<li>'));
  assert.ok(guidanceSource.includes('运营商网络干扰'));
  assert.ok(guidanceSource.includes('广告拦截工具'));
  assert.ok(guidanceSource.includes('刷新 DNS 缓存后重新访问'));
});
