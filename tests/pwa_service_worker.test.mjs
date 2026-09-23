import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../PWA/sw.js', import.meta.url), 'utf8');

test('health endpoint bypasses the service worker cache', () => {
  assert.match(
    source,
    /const NETWORK_FIRST_PATH_PREFIXES\s*=\s*\[[\s\S]*['"]\/health['"]/,
    'the /health endpoint must use the network-first strategy',
  );
});
