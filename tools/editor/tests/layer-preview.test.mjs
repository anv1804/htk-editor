import test from 'node:test';
import assert from 'node:assert/strict';
import { previewLayerEdits } from '../src/layer-preview.ts';

const pixels = (...rgba) => new Uint8ClampedArray(rgba.flat());
test('hair and outfit edits stay in their own exported layer', () => {
  const source=pixels([30,20,10,255],[40,90,120,255]);
  const labels=pixels([255,200,0,255],[0,0,255,255]);
  const empty=new Uint8ClampedArray(8);
  for (const view of ['outfit','headwear']) {
    const out=source.slice();
    previewLayerEdits(out,empty,source,labels,empty,empty,view);
    assert.deepEqual([...out],view==='outfit'?[0,0,0,0,40,90,120,255]:[30,20,10,255,0,0,0,0]);
  }
});
test('paint respects automatic hair ownership and manual reclassification', () => {
  const paint=pixels([12,34,56,255]);const mask=pixels([255,200,0,255]);const empty=new Uint8ClampedArray(4);
  const hair=empty.slice(), outfit=empty.slice();
  previewLayerEdits(hair,empty,empty,empty,paint,mask,'headwear');
  previewLayerEdits(outfit,empty,empty,empty,paint,mask,'outfit');
  assert.deepEqual(hair,paint);assert.deepEqual(outfit,empty);
  previewLayerEdits(outfit,empty,empty,pixels([0,0,255,255]),paint,mask,'outfit');
  assert.deepEqual(outfit,paint);
});
test('revealed skin comes only from base and base reference stays untouched', () => {
  const base=pixels([246,184,139,255]); const labels=pixels([255,0,0,255]);const empty=new Uint8ClampedArray(4);
  const result=empty.slice(), hair=pixels([30,20,10,255]);
  previewLayerEdits(result,base,empty,labels,empty,empty,'result');
  previewLayerEdits(hair,base,empty,labels,empty,empty,'headwear');
  assert.deepEqual(result,base);assert.deepEqual(hair,empty);
  previewLayerEdits(base,empty,empty,labels,pixels([0,0,0,255]),empty,'base');
  assert.deepEqual([...base],[246,184,139,255]);
});
