import { BufferGeometry, Float32BufferAttribute, Vector3 } from 'three';
/** Short local circuits supply a second scale beneath the long white-matter tracts. */
export function buildMicrocircuits(hemispheres:BufferGeometry[]){
 let seed=915;const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
 const cells=new Map<string,number[]>(),vertices:Vector3[]=[],phases:number[]=[];
 const size=.13;
 for(const geometry of hemispheres){const p=geometry.getAttribute('position'),lat=geometry.getAttribute('aCorticalLateral');for(let i=80;i<p.count;i+=21){if(Math.abs(lat.getX(i))<.15||random()>.76)continue;const d=.65+random()*.33;const vertex=new Vector3(p.getX(i)*d,(p.getY(i)-.1)*d+.1,p.getZ(i)*d);vertices.push(vertex);phases.push(random());}}
 const key=(x:number,y:number,z:number)=>`${x},${y},${z}`;
 vertices.forEach((p,i)=>{const k=key(Math.floor(p.x/size),Math.floor(p.y/size),Math.floor(p.z/size));const c=cells.get(k)||[];c.push(i);cells.set(k,c);});
 const positions:number[]=[],phase:number[]=[],bundle:number[]=[],progress:number[]=[],nodes:number[]=[],nphase:number[]=[],nprogress:number[]=[],nsize:number[]=[];
 vertices.forEach((p,i)=>{
  const x=Math.floor(p.x/size),y=Math.floor(p.y/size),z=Math.floor(p.z/size),nearest:{index:number;distance:number}[]=[];
  for(let dx=-1;dx<=1;dx++)for(let dy=-1;dy<=1;dy++)for(let dz=-1;dz<=1;dz++)for(const j of cells.get(key(x+dx,y+dy,z+dz))||[]){if(j<=i)continue;const distance=p.distanceToSquared(vertices[j]);if(distance>.0007&&distance<.016)nearest.push({index:j,distance});}
  nearest.sort((a,b)=>a.distance-b.distance);
  for(const {index} of nearest.slice(0,3)){const q=vertices[index],ph=phases[i];let last=p;for(let n=1;n<=5;n++){const t=n/5,next=p.clone().lerp(q,t);next.y+=Math.sin(t*Math.PI)*.008;positions.push(...last.toArray(),...next.toArray());phase.push(ph,ph);bundle.push(3,3);progress.push((n-1)/5,t);last=next;}}
  if(i%2===0){nodes.push(...p.toArray());nphase.push(phases[i]);nprogress.push(.18+(p.z+.65)*.46);nsize.push(.75+random()*.4);}
 });
 const lines=new BufferGeometry();lines.setAttribute('position',new Float32BufferAttribute(positions,3));lines.setAttribute('aPhase',new Float32BufferAttribute(phase,1));lines.setAttribute('aBundle',new Float32BufferAttribute(bundle,1));lines.setAttribute('aProgress',new Float32BufferAttribute(progress,1));
 const points=new BufferGeometry();points.setAttribute('position',new Float32BufferAttribute(nodes,3));points.setAttribute('aPhase',new Float32BufferAttribute(nphase,1));points.setAttribute('aProgress',new Float32BufferAttribute(nprogress,1));points.setAttribute('aBundle',new Float32BufferAttribute(nphase.map(()=>3),1));points.setAttribute('aSize',new Float32BufferAttribute(nsize,1));return{lines,points};
}
