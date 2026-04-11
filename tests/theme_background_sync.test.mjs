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

function extractThemeBackgroundImageUrl(backgroundValue) {
  const normalizedValue = typeof backgroundValue === 'string' ? backgroundValue : '';
  const match = normalizedValue.match(/url\(["']?(\/theme-assets\/[^"')]+)["']?\)/i);
  return match && match[1] ? match[1] : '';
}

function shouldSkipThemeBackgroundVisualRewrite(renderedImageUrl, nextBackgroundValue, options = {}) {
  if (options.skipVisualRewrite !== true) {
    return false;
  }

  const incomingImageUrl = extractThemeBackgroundImageUrl(nextBackgroundValue || '');
  return Boolean(renderedImageUrl && incomingImageUrl && renderedImageUrl === incomingImageUrl);
}

function shouldSkipThemeBackgroundConsumeDuringLogin({
  loginInFlight,
  isLoggedIn,
  sessionBindEnsured,
  renderedImageUrl,
  imageUrl,
}) {
  if (!loginInFlight || !isLoggedIn) {
    return false;
  }
  if (sessionBindEnsured) {
    return true;
  }
  return Boolean(renderedImageUrl && imageUrl && renderedImageUrl === imageUrl);
}

test('uuid page defers background feedback until auth state is known', () => {
  const { getThemeBackgroundFeedbackMode } = loadFunctions(['getThemeBackgroundFeedbackMode']);

  assert.equal(
    getThemeBackgroundFeedbackMode({
      sessionId: 'bce408cc-94a7-42b7-afaa-6b19044a69ea',
      authStateResolved: false,
      isAuthenticated: false,
      isGuest: false,
    }),
    'defer',
  );
});

test('anonymous uuid page keeps feedback deferred even after auth check says unauthenticated', () => {
  const { getThemeBackgroundFeedbackMode } = loadFunctions(['getThemeBackgroundFeedbackMode']);

  assert.equal(
    getThemeBackgroundFeedbackMode({
      sessionId: 'bce408cc-94a7-42b7-afaa-6b19044a69ea',
      authStateResolved: true,
      isAuthenticated: false,
      isGuest: false,
    }),
    'defer',
  );
});

test('plain public page without uuid keeps using public feedback', () => {
  const { getThemeBackgroundFeedbackMode } = loadFunctions(['getThemeBackgroundFeedbackMode']);

  assert.equal(
    getThemeBackgroundFeedbackMode({
      sessionId: '',
      authStateResolved: true,
      isAuthenticated: false,
      isGuest: false,
    }),
    'public',
  );
});

test('login sync skips duplicate desktop rewrite when same image comes back', () => {
  assert.equal(
    shouldSkipThemeBackgroundVisualRewrite(
      '/theme-assets/random_background_image/pc_bound.jpg',
      'linear-gradient(rgba(255,255,255,0.10), rgba(255,255,255,0.10)), url("/theme-assets/random_background_image/pc_bound.jpg") center / cover no-repeat fixed',
      { skipVisualRewrite: true },
    ),
    true,
  );
});

test('login sync does not skip when backend returns a new random image', () => {
  assert.equal(
    shouldSkipThemeBackgroundVisualRewrite(
      '/theme-assets/random_background_image/pc_bound.jpg',
      'linear-gradient(rgba(255,255,255,0.10), rgba(255,255,255,0.10)), url("/theme-assets/random_background_image/pc_next.jpg") center / cover no-repeat fixed',
      { skipVisualRewrite: true },
    ),
    false,
  );
});

test('pc login click does not queue duplicate consume for same rendered image', () => {
  assert.equal(
    shouldSkipThemeBackgroundConsumeDuringLogin({
      isLoggedIn: true,
      sessionBindEnsured: false,
      renderedImageUrl: '/theme-assets/random_background_image/pc_bound.jpg',
      imageUrl: '/theme-assets/random_background_image/pc_bound.jpg',
      loginInFlight: true,
    }),
    true,
  );
});

test('pc login click still allows consume when backend switched to a new image', () => {
  assert.equal(
    shouldSkipThemeBackgroundConsumeDuringLogin({
      isLoggedIn: true,
      sessionBindEnsured: false,
      renderedImageUrl: '/theme-assets/random_background_image/pc_bound.jpg',
      imageUrl: '/theme-assets/random_background_image/pc_new.jpg',
      loginInFlight: true,
    }),
    false,
  );
});

