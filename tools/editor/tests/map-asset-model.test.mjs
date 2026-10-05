import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseMapAssets, assetPlacement } from '../src/map-asset-model.ts';

const asset=()=>({id:'custom-gate',name:'Cổng',src:'data:image/png;base64,AAAA',w:163,h:154,pivotX:81,pivotY:154});

test('library survives portable JSON roundtrip without changing native size',()=>{
  const a=asset(), library=parseMapAssets(JSON.parse(JSON.stringify([a])));
  assert.deepEqual(library,[a]);assert.notEqual(library[0],a);
  assert.deepEqual(parseMapAssets(undefined),[]);
});
test('placement aligns chosen pivot to tile center and lower edge without scaling',()=>{
  const a=asset(),p=assetPlacement(a,4,6,64);
  assert.equal(p.x*64+a.pivotX,4.5*64);
  assert.equal(p.y*64+a.pivotY,7*64);
  assert.equal(p.width,163);assert.equal(p.height,154);
});
test('invalid library entries do not silently enter saved projects',()=>{
  for(const patch of [{src:'https://example.com/image.png'},{w:NaN},{pivotX:-1},{pivotY:155},{id:'temple_gate'}]){
    assert.throws(()=>parseMapAssets([{...asset(),...patch}]));
  }
  assert.throws(()=>parseMapAssets([asset(),asset()]));
});
