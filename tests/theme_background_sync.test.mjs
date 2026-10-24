import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import vm from 'node:vm';

function extractFunctionSource(source, functionName) {
  const signature = `function ${functionName}`;
  const functionStart = source.indexOf(signature);
  assert.notEqual(functionStart, -1, `${functionName} should exist in scripts/main.js`);
  const start = source.slice(functionStart - 6, functionStart) === 'async '
    ? functionStart - 6
    : functionStart;

  const bodyStart = source.indexOf(') {', start) + 2;
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
  const filePath = resolve('scripts/main.js');
  const source = readFileSync(filePath, 'utf8');
  const functionSources = functionNames.map((name) => extractFunctionSource(source, name));
  return Function(`${functionSources.join('\n\n')} return { ${functionNames.join(', ')} };`)();
}

function loadBackgroundRuntime(overrides = {}) {
  const elements = Object.fromEntries(['auth-login-container', 'mobile-content'].map(id => [id, {
    style: { background: `url("/theme-assets/${id}.jpg")`, backgroundImage: '' },
  }]));
  const context = vm.createContext({
    currentThemeConfig: { global_environment_variables: {} },
    currentThemeBackgroundAssignment: null,
    sessionBindEnsured: { pc: false, mobile: false },
    preLoginBackgroundSnapshot: { pc: '', mobile: '' },
    themeBackgroundRequestCache: new Set(),
    themeBackgroundConsumeDebounceTimer: null,
    pendingThemeBackgroundFeedback: null,
    themeBackgroundLoginSyncInFlight: false,
    authLoginInProgress: false,
    sessionUUID: null,
    initialConsumeCompleted: false,
    currentThemeBackgroundTarget: null,
    currentThemeBackgroundImageUrl: '',
    themeBackgroundAuthStateResolved: false,
    themeBackgroundAuthenticatedSession: false,
    window: { getComputedStyle: () => ({ backgroundImage: '' }) },
    document: { getElementById: id => elements[id] || null },
    clearTimeout: () => {},
    scheduleThemeBackgroundConsumed: () => {},
    ...overrides,
  });
  const source = readFileSync(resolve('scripts/main.js'), 'utf8');
  const names = ['extractThemeBackgroundImageUrl', 'getRenderedThemeBackgroundImageUrlByTarget',
    'shouldSkipThemeBackgroundVisualRewrite', 'shouldSkipThemeBackgroundConsumeDuringLogin',
    'applyThemeLoginContainerStyle', 'getThemeBackgroundRequestCacheKey', 'mergeThemeBackgroundConfig', 'applyThemeGlobalEnvironmentVariables'];
  vm.runInContext(names.map(name => extractFunctionSource(source, name)).join('\n'), context);
  return { context, elements, source };
}

test('empty public backgrounds preserve both rendered backgrounds and current state', () => {
  const previous = { auth_login_container_background: 'url("/theme-assets/pc.jpg")',
    mobile_auth_login_content_background: 'url("/theme-assets/mb.jpg")' };
  const { context, elements } = loadBackgroundRuntime({ currentThemeConfig: { global_environment_variables: previous } });
  context.applyThemeGlobalEnvironmentVariables({ global_environment_variables: {
    auth_login_container_background: '', mobile_auth_login_content_background: '',
  } });
  assert.equal(context.currentThemeConfig.global_environment_variables.auth_login_container_background, previous.auth_login_container_background);
  assert.equal(context.currentThemeConfig.global_environment_variables.mobile_auth_login_content_background, previous.mobile_auth_login_content_background);
  assert.notEqual(elements['auth-login-container'].style.background, '');
  assert.notEqual(elements['mobile-content'].style.background, '');
});

test('same image skips actual desktop and mobile style writes, new image still applies', () => {
  const { context, elements } = loadBackgroundRuntime();
  let writes = 0;
  for (const element of Object.values(elements)) {
    let value = element.style.background;
    Object.defineProperty(element.style, 'background', { get: () => value, set: next => { writes++; value = next; } });
  }
  context.applyThemeLoginContainerStyle({ global_environment_variables: {
    auth_login_container_background: elements['auth-login-container'].style.background,
    mobile_auth_login_content_background: elements['mobile-content'].style.background,
  } });
  assert.equal(writes, 0);
  context.applyThemeLoginContainerStyle({ global_environment_variables: {
    auth_login_container_background: 'url("/theme-assets/new.jpg")',
    mobile_auth_login_content_background: 'url("/theme-assets/new-mobile.jpg")',
  } });
  assert.equal(writes, 2);
});

test('login request defers consume even before an active business UUID exists', () => {
  const { context } = loadBackgroundRuntime({ authLoginInProgress: true, themeBackgroundLoginSyncInFlight: true });
  assert.equal(context.shouldSkipThemeBackgroundConsumeDuringLogin('pc', '/theme-assets/pc.jpg'), true);
  assert.equal(context.shouldSkipThemeBackgroundConsumeDuringLogin('mobile', '/theme-assets/mb.jpg'), true);
});

test('login bundle completes PC/mobile binding without consume or random fetching', () => {
  const { context, source } = loadBackgroundRuntime();
  vm.runInContext(extractFunctionSource(source, 'applyThemeBackgroundAssignment'), context);
  const assignment = { bundle_id: 'bound', pc: { image_url: '/theme-assets/pc.jpg' }, mobile: { image_url: '/theme-assets/mb.jpg' } };
  context.applyThemeBackgroundAssignment(assignment, { bound: true });
  assert.equal(context.currentThemeBackgroundAssignment.bundle_id, 'bound');
  assert.equal(context.sessionBindEnsured.pc, true);
  assert.equal(context.sessionBindEnsured.mobile, true);
  assert.equal(context.initialConsumeCompleted, true);
  assert.match(context.currentThemeConfig.global_environment_variables.auth_login_container_background, /pc.jpg/);
  assert.match(context.currentThemeConfig.global_environment_variables.mobile_auth_login_content_background, /mb.jpg/);
});

test('anonymous consume response cannot replace the preview image that login will bind', async () => {
  const previewUrl = '/theme-assets/preview.jpg';
  const { context, source } = loadBackgroundRuntime({
    themeBackgroundInitialLoadSettled: true,
    themeBackgroundFeedbackInFlight: false,
    activeThemeBackgroundFeedback: null,
    initialLoadBackgroundCandidateByTarget: { pc: previewUrl, mobile: '' },
    anonConsumedBackgroundByTarget: { pc: '', mobile: '' },
    getThemeBackgroundFeedbackMode: () => 'public',
    fetch: async () => ({ ok: true, json: async () => ({ success: true, theme_config: {
      global_environment_variables: { auth_login_container_background: 'url("/theme-assets/next.jpg")' },
    } }) }),
    logMessage_Warning: () => {},
  });
  vm.runInContext(extractFunctionSource(source, 'applyThemeBackgroundAssignment'), context);
  vm.runInContext(extractFunctionSource(source, 'notifyThemeBackgroundConsumed'), context);
  vm.runInContext(extractFunctionSource(source, 'getBackgroundPreviewPayload'), context);
  context.applyThemeBackgroundAssignment({
    bundle_id: 'preview', source: 'anonymous_preview', pc: { image_url: previewUrl }, mobile: {},
  });

  await context.notifyThemeBackgroundConsumed('pc', previewUrl);

  assert.equal(context.getRenderedThemeBackgroundImageUrlByTarget('pc'), previewUrl);
  assert.equal(context.getBackgroundPreviewPayload().pc.image_url, previewUrl);
});

test('late anonymous consume response cannot replace an authenticated background', async () => {
  const previewUrl = '/theme-assets/preview.jpg';
  let finishRequest;
  const response = new Promise(resolve => { finishRequest = resolve; });
  const { context, source } = loadBackgroundRuntime({
    themeBackgroundInitialLoadSettled: true,
    themeBackgroundFeedbackInFlight: false,
    activeThemeBackgroundFeedback: null,
    initialLoadBackgroundCandidateByTarget: { pc: previewUrl, mobile: '' },
    anonConsumedBackgroundByTarget: { pc: '', mobile: '' },
    getThemeBackgroundFeedbackMode: () => 'public',
    fetch: () => response,
    logMessage_Warning: () => {},
  });
  vm.runInContext(extractFunctionSource(source, 'applyThemeBackgroundAssignment'), context);
  vm.runInContext(extractFunctionSource(source, 'notifyThemeBackgroundConsumed'), context);
  context.applyThemeBackgroundAssignment({
    bundle_id: 'preview', source: 'anonymous_preview', pc: { image_url: previewUrl }, mobile: {},
  });
  const consume = context.notifyThemeBackgroundConsumed('pc', previewUrl);
  context.applyThemeBackgroundAssignment({
    bundle_id: 'bound', pc: { image_url: '/theme-assets/bound.jpg' }, mobile: {},
  }, { bound: true });
  finishRequest({ ok: true, json: async () => ({ success: true, theme_config: {
    global_environment_variables: { auth_login_container_background: 'url("/theme-assets/next.jpg")' },
  } }) });

  await consume;

  assert.equal(context.getRenderedThemeBackgroundImageUrlByTarget('pc'), '/theme-assets/bound.jpg');
});

test('public theme config loaded after bootstrap keeps the preview bundle image', () => {
  const previewUrl = '/theme-assets/preview.jpg';
  const { context, source } = loadBackgroundRuntime();
  vm.runInContext(extractFunctionSource(source, 'applyThemeBackgroundAssignment'), context);
  context.applyThemeBackgroundAssignment({
    bundle_id: 'preview', source: 'anonymous_preview', pc: { image_url: previewUrl }, mobile: {},
  });

  const merged = context.mergeThemeBackgroundConfig(context.currentThemeConfig, {
    global_environment_variables: { auth_login_container_background: 'url("/theme-assets/next.jpg")' },
  });

  assert.equal(context.getRenderedThemeBackgroundImageUrlByTarget('pc'), previewUrl);
  assert.match(merged.global_environment_variables.auth_login_container_background, /preview\.jpg/);
});

test('switching to a non-default theme uses that theme background', () => {
  const { context, source } = loadBackgroundRuntime();
  vm.runInContext(extractFunctionSource(source, 'applyThemeBackgroundAssignment'), context);
  context.applyThemeBackgroundAssignment({
    bundle_id: 'preview', source: 'anonymous_preview',
    pc: { image_url: '/theme-assets/preview.jpg' }, mobile: {},
  });

  const merged = context.mergeThemeBackgroundConfig(context.currentThemeConfig, {
    basic_information: { id: 'retro' },
    global_environment_variables: { auth_login_container_background: 'url("/static/retro.jpg")' },
  });

  assert.equal(merged.global_environment_variables.auth_login_container_background, 'url("/static/retro.jpg")');
});

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

test('uuid page defers initial theme config apply until uuid auth status resolves', () => {
  const { shouldApplyThemeConfigImmediately } = loadFunctions(['shouldApplyThemeConfigImmediately']);

  assert.equal(
    shouldApplyThemeConfigImmediately({
      sessionId: '',
      pathname: '/uuid=bce408cc-94a7-42b7-afaa-6b19044a69ea',
      authStateResolved: false,
    }),
    false,
  );
});

test('uuid page applies theme config after uuid auth status resolves', () => {
  const { shouldApplyThemeConfigImmediately } = loadFunctions(['shouldApplyThemeConfigImmediately']);

  assert.equal(
    shouldApplyThemeConfigImmediately({
      sessionId: '',
      pathname: '/uuid=bce408cc-94a7-42b7-afaa-6b19044a69ea',
      authStateResolved: true,
    }),
    true,
  );
});

test('plain public page still applies theme config immediately without uuid', () => {
  const { shouldApplyThemeConfigImmediately } = loadFunctions(['shouldApplyThemeConfigImmediately']);

  assert.equal(
    shouldApplyThemeConfigImmediately({
      sessionId: '',
      pathname: '/',
      authStateResolved: false,
    }),
    true,
  );
});

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

