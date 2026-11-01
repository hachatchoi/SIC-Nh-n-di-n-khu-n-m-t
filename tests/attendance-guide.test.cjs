const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../frontend/app.js'), 'utf8');
const fn = source.match(/function attendanceCrop\([^]*?\n\}/)[0];
const crop = vm.runInNewContext(`(${fn})`);
test('wide camera maps to the visible centered square without stretching', () => {
  const r = crop(1280, 720, 300, 300);
  assert.equal(r.x, 280); assert.equal(r.y, 0);
  assert.equal(r.width, 720); assert.equal(r.height, 720);
});
test('portrait camera crops top and bottom for a wide preview', () => {
  const r = crop(720, 1280, 600, 300);
  assert.equal(r.x, 0); assert.equal(r.y, 460);
  assert.equal(r.width, 720); assert.equal(r.height, 360);
});
test('matching aspect ratio preserves the full frame', () => {
  const r = crop(1280, 720, 640, 360);
  assert.equal(r.x, 0); assert.equal(r.y, 0);
  assert.equal(r.width, 1280); assert.equal(r.height, 720);
});
