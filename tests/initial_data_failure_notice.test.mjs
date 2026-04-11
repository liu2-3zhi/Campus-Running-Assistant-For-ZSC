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
      if (char === '\n') {
        inLineComment = false;
      }
      continue;
    }

    if (inBlockComment) {
      if (prev === '*' && char === '/') {
        inBlockComment = false;
      }
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

function loadFunction(functionName) {
  const filePath = resolve('scripts/main.new.js');
  const source = readFileSync(filePath, 'utf8');
  const functionSource = extractFunctionSource(source, functionName);
  return Function(`return (${functionSource});`)();
}

test('offline initial data failure produces a user-facing notice', () => {
  const getInitialDataFailureNotice = loadFunction('getInitialDataFailureNotice');

  assert.deepEqual(
    getInitialDataFailureNotice({
      success: false,
      offline: true,
      message: '后端无法连接服务器，已切换到离线模式',
    }),
    {
      title: '离线模式',
      text: '后端无法连接服务器，已切换到离线模式',
      icon: 'warning',
    },
  );
});

test('successful initial data does not produce a failure notice', () => {
  const getInitialDataFailureNotice = loadFunction('getInitialDataFailureNotice');

  assert.equal(
    getInitialDataFailureNotice({
      success: true,
      offline: false,
      message: '',
    }),
    null,
  );
});
