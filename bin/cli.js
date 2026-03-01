#!/usr/bin/env node
'use strict';

const { spawnSync } = require('child_process');
const path = require('path');

const pythonCandidates = process.platform === 'win32'
  ? ['python', 'python3', 'py']
  : ['python3', 'python'];

// The package root is one level up from bin/
const pkgRoot = path.join(__dirname, '..');

let python = null;
for (const candidate of pythonCandidates) {
  const probe = spawnSync(candidate, ['--version'], { encoding: 'utf8' });
  if (probe.status === 0) {
    python = candidate;
    break;
  }
}

if (!python) {
  console.error(
    '\n  Error: Python 3 is required but was not found in PATH.\n' +
    '  Install Python 3 from https://python.org and try again.\n'
  );
  process.exit(1);
}

const result = spawnSync(
  python,
  ['-m', 'vue3_migration', ...process.argv.slice(2)],
  {
    cwd: pkgRoot,
    stdio: 'inherit',
    env: process.env,
  }
);

process.exit(result.status ?? 1);
