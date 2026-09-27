import test from 'node:test';
import assert from 'node:assert/strict';
import { learningKey, readLearning, writeLearning, mergeConfirmedPixels } from '../src/learning-memory.ts';

test('feedback follows image content and grid, not filename or unrelated outfits', async () => {
  const key=await learningKey('base-a','outfit-a',7,4);
  assert.equal(key,await learningKey('base-a','outfit-a',7,4));
  for (const args of [['base-b','outfit-a',7,4],['base-a','outfit-b',7,4],['base-a','outfit-a',4,7]]) {
    assert.notEqual(key,await learningKey(...args));
  }
});

test('confirmed corrections survive storage; damaged records are ignored', () => {
  const values=new Map();
  const storage={getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};
  const value={version:1,mask:'data:image/png;base64,bWFzaw==',paint:'data:image/png;base64,cGFpbnQ=',pixels:12,updatedAt:1};
  writeLearning(storage,'sheet',value);
  assert.deepEqual(readLearning(storage,'sheet'),value);
  assert.equal(readLearning(storage,'other-sheet'),null);
  values.set('sheet','invalid json');
  assert.equal(readLearning(storage,'sheet'),null);
  values.set('sheet',JSON.stringify({...value,version:2}));
  assert.equal(readLearning(storage,'sheet'),null);
});

test('failed saves retain the previous confirmed record', () => {
  const original={version:1,mask:'data:image/png;base64,AA==',paint:'data:image/png;base64,AA==',pixels:1,updatedAt:1};
  const storage={getItem:()=>JSON.stringify(original),setItem:()=>{throw new Error('quota');}};
  assert.throws(()=>writeLearning(storage,'sheet',{...original,pixels:20}));
  assert.deepEqual(readLearning(storage,'sheet'),original);
});

test('saving a new erase does not resurrect old paint on the next visit', () => {
  const old=new Uint8ClampedArray([80,66,52,255,40,50,60,255]);
  const current=new Uint8ClampedArray(8);
  const labels=new Uint8ClampedArray([0,255,0,255,0,0,0,0]);
  assert.deepEqual([...mergeConfirmedPixels(old,current,labels)],[0,0,0,0,40,50,60,255]);
  current.set([90,80,70,255]);
  assert.deepEqual([...mergeConfirmedPixels(old,current,labels)],[90,80,70,255,40,50,60,255]);
  assert.equal(old[3],255);
});
