import { pixelLine, type PixelPoint } from './item-pixels';

export type PaintTool='brush'|'eraser'|'picker'|'fill';
/** One undo step per stroke; independent histories for each UI component. */
export class UIPaint {
  canvas=document.createElement('canvas');
  ctx=this.canvas.getContext('2d',{willReadFrequently:true})!;
  undoStack:ImageData[]=[];
  redoStack:ImageData[]=[];
  tool:PaintTool='brush';
  color='#e3e9c4';
  size=1;
  private before:ImageData|null=null;
  private last:PixelPoint|null=null;
  constructor(image:CanvasImageSource,width:number,height:number){
    this.canvas.width=width;this.canvas.height=height;this.ctx.drawImage(image,0,0);
  }
  snapshot(){return this.ctx.getImageData(0,0,this.canvas.width,this.canvas.height);}
  begin(p:PixelPoint){
    if(!this.inside(p))return false;
    if(this.tool==='picker'){
      const c=this.ctx.getImageData(p.x,p.y,1,1).data;
      if(c[3])this.color='#'+[c[0]!,c[1]!,c[2]!].map(v=>v.toString(16).padStart(2,'0')).join('');
      return false;
    }
    this.before=this.snapshot();this.last=p;
    if(this.tool==='fill')this.fill(p);else this.dab(p);
    return true;
  }
  move(p:PixelPoint){
    if(!this.before||!this.last||this.tool==='fill')return;
    // Clamp captured pointer to the image, avoiding unbounded off-canvas lines.
    p={x:Math.max(0,Math.min(this.canvas.width-1,p.x)),y:Math.max(0,Math.min(this.canvas.height-1,p.y))};
    for(const q of pixelLine(this.last,p))this.dab(q);
    this.last=p;
  }
  end(){
    if(!this.before)return false;
    const before=this.before;this.before=null;this.last=null;
    const after=this.snapshot();if(before.data.every((v,i)=>v===after.data[i]))return false;
    this.undoStack.push(before);if(this.undoStack.length>40)this.undoStack.shift();this.redoStack=[];return true;
  }
  history(redo=false){
    const source=redo?this.redoStack:this.undoStack,target=redo?this.undoStack:this.redoStack;
    const image=source.pop();if(!image)return false;target.push(this.snapshot());this.ctx.putImageData(image,0,0);return true;
  }
  private inside(p:PixelPoint){return p.x>=0&&p.y>=0&&p.x<this.canvas.width&&p.y<this.canvas.height;}
  private dab(p:PixelPoint){
    const offset=Math.floor(this.size/2);
    if(this.tool==='eraser')this.ctx.clearRect(p.x-offset,p.y-offset,this.size,this.size);
    else{this.ctx.fillStyle=this.color;this.ctx.fillRect(p.x-offset,p.y-offset,this.size,this.size);}
  }
  private fill(p:PixelPoint){
    const image=this.snapshot(),data=image.data,w=image.width,h=image.height,start=p.y*w+p.x;
    const old=Array.from(data.slice(start*4,start*4+4));
    const color=[1,3,5].map(i=>parseInt(this.color.slice(i,i+2),16)).concat(255);
    if(old.every((v,i)=>v===color[i]))return;
    const seen=new Uint8Array(w*h),queue=[start];seen[start]=1;
    for(let at=0;at<queue.length;at++){
      const pos=queue[at]!,base=pos*4;
      if(!old.every((v,i)=>v===data[base+i]))continue;
      data.set(color,base);
      const neighbours=[pos%w?pos-1:-1,pos%w<w-1?pos+1:-1,pos>=w?pos-w:-1,pos<w*(h-1)?pos+w:-1];
      for(const next of neighbours)if(next>=0&&!seen[next]){seen[next]=1;queue.push(next);}
    }
    this.ctx.putImageData(image,0,0);
  }
}
