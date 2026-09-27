import { test } from 'node:test';
import assert from 'node:assert/strict';
import { connectedRegion } from '../src/region.ts';

const pixels = values => new Uint8ClampedArray(values.flatMap(v => v === null ? [0,0,0,0] : [v,v,v,255]));
test('stops at color boundaries and cannot reach disconnected same-color pixels', () => {
  assert.deepEqual(connectedRegion(pixels([10,10,100,10,100,10]),3,2,0,0,0).sort(),[0,1,3]);
});
test('compares with seed so a gradient cannot progressively leak', () => {
  assert.deepEqual(connectedRegion(pixels([10,20,30,40]),4,1,0,0,15),[0,1]);
});
test('transparent areas never connect to opaque black', () => {
  assert.deepEqual(connectedRegion(pixels([null,null,0]),3,1,0,0,60),[0,1]);
});
test('row ends never wrap and points outside frame are ignored', () => {
  const data=pixels([100,10,10,100]);
  assert.deepEqual(connectedRegion(data,2,2,1,0,0),[1]);
  assert.deepEqual(connectedRegion(data,2,2,2,0,0),[]);
});
