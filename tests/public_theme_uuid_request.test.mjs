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

function loadFunctions(functionNames) {
  const filePath = resolve('scripts/main.new.js');
  const source = readFileSync(filePath, 'utf8');
  const functionSources = functionNames.map((name) => extractFunctionSource(source, name));
  return Function(`${functionSources.join('\n\n')} return { ${functionNames.join(', ')} };`)();
}

test('public theme styles request includes uuid from pathname before session initialization', () => {
  const { buildPublicThemeStylesUrl } = loadFunctions([
    'resolveThemeRequestSessionUUID',
    'buildPublicThemeStylesUrl',
  ]);

  const url = buildPublicThemeStylesUrl(
    'default',
    'pc',
    '',
    '/uuid=bce408cc-94a7-42b7-afaa-6b19044a69ea',
  );

  assert.equal(
    url,
    '/api/public/theme_styles?style_id=default&background_target=pc&uuid=bce408cc-94a7-42b7-afaa-6b19044a69ea',
  );
});

test('public theme styles request omits uuid when none is available', () => {
  const { buildPublicThemeStylesUrl } = loadFunctions([
    'resolveThemeRequestSessionUUID',
    'buildPublicThemeStylesUrl',
  ]);

  const url = buildPublicThemeStylesUrl('default', 'pc', '', '/');

  assert.equal(
    url,
    '/api/public/theme_styles?style_id=default&background_target=pc',
  );
});
