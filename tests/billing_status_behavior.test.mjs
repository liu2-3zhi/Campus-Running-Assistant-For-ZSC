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
  assert.ok(message.includes('请检查您的设备是否成功连接互联网'));
  assert.ok(message.includes('中华人民共和国福建省、江苏省、贵州省或广西省'));
  assert.ok(message.includes('更换网络访问'));
  assert.ok(message.includes('使用加密 DNS：开启方法'));
  assert.ok(message.includes('使用国际联网工具访问'));
  assert.ok(message.includes('广告拦截工具'));
  assert.ok(message.includes('Zelly 的服务器受到攻击'));
  assert.ok(message.includes('手机请开启再关闭飞行模式并重启浏览器'));
  assert.ok(message.includes('电脑请参考：刷新DNS方法'));
});
