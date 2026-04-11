import test from 'node:test';
import assert from 'node:assert/strict';

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
