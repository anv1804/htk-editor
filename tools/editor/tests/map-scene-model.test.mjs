import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readScene, newScene, sceneFromLayout, placeAsset, snapshot} from '../src/map-scene-model.ts';
const src = 'data:image/png;base64,AAAA';

test('imports synchronized layers once and leaves baked objects only in library', async () => {
  const p = await sceneFromLayout({canvas:{width:1983,height:793},layers:[{file:'layers/a.png',x:3,y:4,z:2},{file:'layers/b.png',z:0}],objects:[{file:'objects/gate.png',x:99,y:77}]},async()=>({src,w:175,h:139}));
  assert.equal(p.assets.length,3); assert.equal(p.layers.length,3);
  assert.equal(p.layers.reduce((n,l)=>n+l.items.length,0),2);
  assert.equal(p.layers[0].name,'b'); assert.equal(p.layers[1].items[0].x,3);
  assert.equal(p.layers[0].locked,true); assert.equal(p.layers[2].locked,false);
});
test('project roundtrip keeps original source and placement metadata',()=>{
  const p=newScene();p.assets.push({id:'gate',name:'Gate',src,originalSrc:src,w:175,h:139,pivotX:87,pivotY:139,category:'module'});
  p.layers[0].items.push(placeAsset(p.assets[0],200,300,16));
  const parsed=readScene(JSON.parse(JSON.stringify(p)));
  assert.equal(parsed.assets[0].originalSrc,src);
  assert.equal(parsed.layers[0].items[0].x+87,208);
  const old=snapshot(parsed);parsed.layers[0].items[0].x=0;assert.notEqual(old.layers[0].items[0].x,0);
});
test('invalid coordinate, image and foreign references are rejected',()=>{
  const p=newScene();p.width=1.5;assert.throws(()=>readScene(p));
  const q=newScene();q.layers[0].items.push({id:'x',assetId:'missing',x:0,y:0,flipX:false,flipY:false});assert.throws(()=>readScene(q));
});
