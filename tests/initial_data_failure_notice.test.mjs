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
      message: '暂时无法连接到后端服务器，请刷新重试。如果问题依旧，请联系管理员。',
    }),
    {
      title: '后端连接异常',
      text: '暂时无法连接到后端服务器，请刷新重试。如果问题依旧，请联系管理员。',
      icon: 'warning',
    },
  );
});

test('offline initial data failure defaults to refresh-first guidance', () => {
  const getInitialDataFailureNotice = loadFunction('getInitialDataFailureNotice');

  assert.deepEqual(
    getInitialDataFailureNotice({
      success: false,
      offline: true,
      message: '',
    }),
    {
      title: '后端连接异常',
      text: '暂时无法连接到后端服务器，请刷新重试。如果问题依旧，请联系管理员。',
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

test('suppressed stale auth responses do not produce an initial data notice', () => {
  const getInitialDataFailureNotice = loadFunction('getInitialDataFailureNotice');

  assert.equal(
    getInitialDataFailureNotice({
      success: false,
      stale_auth_response: true,
      suppressed: true,
      message: '令牌验证失败，可能账号在其他设备登录',
    }),
    null,
  );
});

test('stale logged-out-elsewhere API responses are suppressed after a fresh login starts', () => {
  const shouldSuppressLoggedOutElsewhereNotice = loadFunction(
    'shouldSuppressLoggedOutElsewhereNotice',
  );

  assert.equal(
    shouldSuppressLoggedOutElsewhereNotice(
      { logged_out_elsewhere: true },
      { authGeneration: 1, sessionUUID: 'old-session' },
      { authGeneration: 2, sessionUUID: 'new-session', authLoginInProgress: false },
    ),
    true,
  );

  assert.equal(
    shouldSuppressLoggedOutElsewhereNotice(
      { logged_out_elsewhere: true },
      { authGeneration: 2, sessionUUID: 'new-session' },
      { authGeneration: 2, sessionUUID: '', authLoginInProgress: false },
    ),
    true,
  );
});

test('session expired notices are suppressed on the login screen and for empty sessions', () => {
  const shouldSuppressSessionExpiredNotice = loadFunction(
    'shouldSuppressSessionExpiredNotice',
  );

  assert.equal(
    shouldSuppressSessionExpiredNotice(
      'get_initial_data',
      { authGeneration: 4, sessionUUID: '11111111-1111-4111-8111-111111111111' },
      {
        authGeneration: 4,
        sessionUUID: '11111111-1111-4111-8111-111111111111',
        authLoginInProgress: false,
        authLoginVisible: true,
      },
    ),
    true,
  );

  assert.equal(
    shouldSuppressSessionExpiredNotice(
      'get_initial_data',
      { authGeneration: 4, sessionUUID: '11111111-1111-4111-8111-111111111111' },
      {
        authGeneration: 4,
        sessionUUID: '',
        authLoginInProgress: false,
        authLoginVisible: false,
      },
    ),
    true,
  );

  assert.equal(
    shouldSuppressSessionExpiredNotice(
      'get_initial_data',
      { authGeneration: 4, sessionUUID: '11111111-1111-4111-8111-111111111111' },
      {
        authGeneration: 4,
        sessionUUID: '11111111-1111-4111-8111-111111111111',
        authLoginInProgress: false,
        authLoginVisible: false,
      },
    ),
    false,
  );
});

test('logged-out-elsewhere API responses are suppressed while login is in progress', () => {
  const shouldSuppressLoggedOutElsewhereNotice = loadFunction(
    'shouldSuppressLoggedOutElsewhereNotice',
  );

  assert.equal(
    shouldSuppressLoggedOutElsewhereNotice(
      { logged_out_elsewhere: true },
      { authGeneration: 3, sessionUUID: 'same-session' },
      { authGeneration: 3, sessionUUID: 'same-session', authLoginInProgress: true },
    ),
    true,
  );

  assert.equal(
    shouldSuppressLoggedOutElsewhereNotice(
      { logged_out_elsewhere: false },
      { authGeneration: 3, sessionUUID: 'same-session' },
      { authGeneration: 4, sessionUUID: 'other-session', authLoginInProgress: true },
    ),
    false,
  );
});

test('showAuthLogin clears stale session notices before displaying the auth view', () => {
  const showAuthLogin = loadFunction('showAuthLogin');
  const clearCalls = [];

  const elements = new Map();
  function createElement(initialHidden = false) {
    const classes = new Set(initialHidden ? ['hidden'] : []);
    return {
      classList: {
        add: (...tokens) => tokens.forEach((token) => classes.add(token)),
        remove: (...tokens) => tokens.forEach((token) => classes.delete(token)),
        contains: (token) => classes.has(token),
      },
    };
  }

  elements.set('loading-overlay', createElement(false));
  elements.set('auth-login-container', createElement(true));
  elements.set('login-container', createElement(false));
  elements.set('main-app', createElement(false));
  elements.set('exit-app-btn', createElement(false));

  globalThis.$ = (id) => elements.get(id) || null;
  globalThis.checkGuestLoginEnabled = () => {
    clearCalls.push('guest');
  };
  globalThis.clearLogoutElsewhereOverlay = () => {
    clearCalls.push('clear');
  };

  try {
    showAuthLogin();

    assert.equal(elements.get('auth-login-container').classList.contains('hidden'), false);
    assert.equal(elements.get('login-container').classList.contains('hidden'), true);
    assert.equal(elements.get('main-app').classList.contains('hidden'), true);
    assert.equal(elements.get('exit-app-btn').classList.contains('hidden'), true);
    assert.deepEqual(clearCalls, ['clear', 'guest']);
  } finally {
    delete globalThis.$;
    delete globalThis.checkGuestLoginEnabled;
    delete globalThis.clearLogoutElsewhereOverlay;
  }
});
