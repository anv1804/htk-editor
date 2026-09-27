import { test } from 'node:test';
import assert from 'node:assert/strict';
import { copyRaster, pixelBounds, pixelLine, removeBorderBackground, reduceItemPalette, outlineItem, transformItem } from '../src/item-pixels.ts';

const raster=(w,h,color=[255,255,255,255])=>({width:w,height:h,data:new Uint8ClampedArray(Array.from({length:w*h},()=>color).flat())});
const put=(r,x,y,color)=>r.data.set(color,(y*r.width+x)*4);
const get=(r,x,y)=>Array.from(r.data.slice((y*r.width+x)*4,(y*r.width+x+1)*4));

test('background removal retains enclosed white detail and does not mutate input',()=>{
  const r=raster(7,7);
  for(let y=1;y<6;y++)for(let x=1;x<6;x++)put(r,x,y,[30,80,150,255]);
  put(r,3,3,[255,255,255,255]);const before=copyRaster(r);
  const result=removeBorderBackground(r,[255,255,255],20);
  assert.equal(get(result,0,0)[3],0);
  assert.deepEqual(get(result,3,3),[255,255,255,255]);
  assert.deepEqual(r,before);
  assert.deepEqual(pixelBounds(result),{x:1,y:1,w:5,h:5});
});
test('background flood compares to requested background, never walks down a color gradient',()=>{
  const r=raster(7,3,[0,0,0,255]);
  [255,240,225,210,195,180,165].forEach((v,x)=>put(r,x,1,[v,v,v,255]));
  const result=removeBorderBackground(r,[255,255,255],20);
  assert.equal(get(result,1,1)[3],0);assert.equal(get(result,2,1)[3],255);
});
test('palette reduction is deterministic, alpha-safe and uses only source colors',()=>{
  const r=raster(20,20,[0,0,0,0]);
  for(let y=3;y<17;y++)for(let x=2;x<18;x++)put(r,x,y,[(x*13)%256,(y*11)%256,100,255]);
  const before=copyRaster(r),out=reduceItemPalette(r,8);
  const colors=new Set(),source=new Set();
  for(let i=0;i<r.data.length;i+=4){
    assert.equal(out.data[i+3],r.data[i+3]);
    if(r.data[i+3]){source.add(r.data.slice(i,i+3).join(','));colors.add(out.data.slice(i,i+3).join(','));}
  }
  assert.ok(colors.size<=8);assert.ok([...colors].every(c=>source.has(c)));
  assert.deepEqual(reduceItemPalette(r,8),out);assert.deepEqual(r,before);
});
test('outlining is idempotent and never grows the silhouette or paints transparent space',()=>{
  const r=raster(8,8,[0,0,0,0]);
  for(let y=2;y<6;y++)for(let x=2;x<6;x++)put(r,x,y,[180,220,230,255]);
  const out=outlineItem(r,[30,20,40]);
  assert.deepEqual(outlineItem(out,[30,20,40]),out);
  assert.deepEqual(get(out,3,3),get(r,3,3));
  for(let i=3;i<r.data.length;i+=4)assert.equal(out.data[i],r.data[i]);
  assert.deepEqual(get(out,2,3),[30,20,40,255]);
});
test('four rotations and two flips preserve all pixels of a non-square image',()=>{
  const r=raster(5,3,[0,0,0,0]);put(r,1,2,[180,150,130,255]);put(r,4,0,[20,40,60,128]);
  let rotated=r;for(let i=0;i<4;i++)rotated=transformItem(rotated,'right');
  assert.deepEqual(rotated,r);assert.deepEqual(transformItem(transformItem(r,'flipX'),'flipX'),r);
  assert.deepEqual(transformItem(transformItem(r,'left'),'right'),r);
});
test('pixel lines connect steep and shallow strokes without gaps in either direction',()=>{
  for(const [a,b] of [[{x:1,y:1},{x:5,y:15}],[{x:20,y:3},{x:2,y:8}],[{x:4,y:4},{x:4,y:4}]]){
    const points=pixelLine(a,b);assert.deepEqual(points[0],a);assert.deepEqual(points.at(-1),b);
    points.slice(1).forEach((p,i)=>{assert.ok(Math.abs(p.x-points[i].x)<=1);assert.ok(Math.abs(p.y-points[i].y)<=1);});
  }
});
test('empty images remain empty through cleanup and palette reduction',()=>{
  const r=raster(32,32,[0,0,0,0]);assert.equal(pixelBounds(r),null);
  assert.deepEqual(reduceItemPalette(r,16),r);assert.deepEqual(outlineItem(r,[10,20,30]),r);
});
