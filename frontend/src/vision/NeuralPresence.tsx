import { Component, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Bloom, EffectComposer } from '@react-three/postprocessing';
import { AdditiveBlending, BufferGeometry, DoubleSide, Float32BufferAttribute, Group, ShaderMaterial, Vector3 } from 'three';
import { buildBrainGeometry } from './anatomy';
import { buildTractography } from './tractography';
import { buildMicrocircuits } from './microcircuits';
import { cortexVertex,cortexFragment,fiberVertex,fiberFragment,pointVertex,pointFragment } from './neuralShaders';
import type { CognitiveState } from './types';
const stateIndex:Record<CognitiveState,number>={idle:0,listening:1,thinking:2,speaking:3,working:4,waiting:5,error:6,focus:7};
function attributes(geometry:BufferGeometry, data:Record<string,number[]>){for(const [name,values] of Object.entries(data))geometry.setAttribute(name,new Float32BufferAttribute(values,name==='position'?3:1));return geometry;}
function cortexTopology(hemispheres:BufferGeometry[]){
 let seed=726;const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
 const pos:number[]=[],phase:number[]=[],bundle:number[]=[],progress:number[]=[],size:number[]=[];
 const lpos:number[]=[],lphase:number[]=[],lbundle:number[]=[],lprogress:number[]=[];
 hemispheres.forEach((g,side)=>{
  const p=g.getAttribute('position'), lateral=g.getAttribute('aCorticalLateral');
  const get=(u:number,r:number)=>{u=Math.max(1,Math.min(191,u));r=(r+144)%144;const a=Math.floor(u),b=Math.floor(r),fu=u-a,fr=r-b;const v=new Vector3();for(const [index,w] of [[a*145+b,(1-fu)*(1-fr)],[(a+1)*145+b,fu*(1-fr)],[a*145+b+1,(1-fu)*fr],[(a+1)*145+b+1,fu*fr]]){v.x+=p.getX(index)*w;v.y+=p.getY(index)*w;v.z+=p.getZ(index)*w;}return v.multiplyScalar(1.002);};
  for(let i=0;i<p.count;i+=2){if(Math.abs(lateral.getX(i))<.12||random()>.76)continue;pos.push(p.getX(i)*1.002,p.getY(i)*1.002,p.getZ(i)*1.002);phase.push(random());bundle.push(side);progress.push(Math.floor(i/145)/192);size.push(.7+random()*.65);}
  for(let f=0;f<160;f++){
   let u=10+random()*172,r=random()*144;const ph=random(),direction=random()<.5?-1:1;let previous=get(u,r);const angle=random()*Math.PI*2;
   for(let n=1;n<=70;n++){const t=n/70;u+=Math.cos(angle+Math.sin(t*6+ph*8)*.4)*direction*.55;r+=Math.sin(angle+Math.cos(t*5)*.28)*.62;const next=get(u,r);lpos.push(...previous.toArray(),...next.toArray());lphase.push(ph,ph);lbundle.push(side,side);lprogress.push((n-1)/70,t);previous=next;}
  }
 });
 return {points:attributes(new BufferGeometry(),{position:pos,aPhase:phase,aBundle:bundle,aProgress:progress,aSize:size}),lines:attributes(new BufferGeometry(),{position:lpos,aPhase:lphase,aBundle:lbundle,aProgress:lprogress})};
}
function fieldGeometry(){
 const pos:number[]=[],phase:number[]=[],bundle:number[]=[],progress:number[]=[];
 for(let i=0;i<23;i++){
  const a=i*2.399963,bias=(i%5)/5;
  const start=new Vector3(Math.cos(a)*(.33+bias*.1),Math.sin(a)*.30+.1,Math.cos(a*.73)*.5);
  const outward=new Vector3(start.x*2.9,start.y*2.4+.25,start.z*2.1);
  let previous=start;
  for(let n=1;n<=70;n++){const t=n/70;const next=start.clone().lerp(outward,t);next.x+=Math.sin(t*Math.PI)*Math.sin(a)*.22;next.y+=Math.sin(t*Math.PI)*.12;next.z+=Math.sin(t*Math.PI)*Math.cos(a)*.20;pos.push(...previous.toArray(),...next.toArray());phase.push(i/23,i/23);bundle.push(2,2);progress.push((n-1)/70,t);previous=next;}
 }
 return attributes(new BufferGeometry(),{position:pos,aPhase:phase,aBundle:bundle,aProgress:progress});
}
function Brain({state,reduced}:{state:CognitiveState;reduced:boolean}){
 const group=useRef<Group>(null);const rotation=useRef(-.92);const targetMode=useRef(stateIndex[state]);
 const geometry=useMemo(()=>[buildBrainGeometry(-1),buildBrainGeometry(1)],[]);
 const cortex=useMemo(()=>cortexTopology(geometry),[geometry]);
 const connectome=useMemo(()=>{const value=buildTractography(geometry);const count=value.nuclei.getAttribute('position').count;value.nuclei.setAttribute('aSize',new Float32BufferAttribute(Array.from({length:count},(_,i)=>1.+(i%7)*.12),1));return value;},[geometry]);
 const micro=useMemo(()=>buildMicrocircuits(geometry),[geometry]);
 const field=useMemo(fieldGeometry,[]);
 const materials=useMemo(()=>{
  const uni=(layer:number)=>({uTime:{value:0},uActivity:{value:.2},uMode:{value:0},uPrevious:{value:0},uTransition:{value:1},uLayer:{value:layer}});
  const line=(layer:number)=>new ShaderMaterial({uniforms:uni(layer),vertexShader:fiberVertex,fragmentShader:fiberFragment,transparent:true,depthWrite:false,blending:AdditiveBlending});
  const point=(layer:number)=>new ShaderMaterial({uniforms:uni(layer),vertexShader:pointVertex,fragmentShader:pointFragment,transparent:true,depthWrite:false,blending:AdditiveBlending});
  return {veil:new ShaderMaterial({uniforms:uni(0),vertexShader:cortexVertex,fragmentShader:cortexFragment,transparent:true,depthWrite:false,side:DoubleSide}),surface:line(0),tracts:line(1),field:line(2),points:point(0),nuclei:point(1)};
 },[]);
 useEffect(()=>{const next=stateIndex[state];for(const mat of Object.values(materials)){mat.uniforms.uPrevious.value=targetMode.current;mat.uniforms.uMode.value=next;mat.uniforms.uTransition.value=0;}targetMode.current=next;},[state,materials]);
 useEffect(()=>()=>{geometry.forEach(g=>g.dispose());cortex.points.dispose();cortex.lines.dispose();connectome.tracts.dispose();connectome.nuclei.dispose();micro.lines.dispose();micro.points.dispose();field.dispose();Object.values(materials).forEach(m=>m.dispose());},[geometry,cortex,connectome,micro,field,materials]);
 useFrame(({clock,pointer},delta)=>{
  const t=clock.elapsedTime;
  for(const material of Object.values(materials)){material.uniforms.uTime.value=reduced?0:t;material.uniforms.uTransition.value=Math.min(1,material.uniforms.uTransition.value+delta*.9);}
  if(group.current){rotation.current+=reduced?0:Math.min(delta,.05)*(state==='waiting'?.007:state==='focus'?.022:.055);group.current.rotation.y+=(rotation.current+pointer.x*.10-group.current.rotation.y)*Math.min(delta*2,1);group.current.rotation.x+=(.20+(reduced?0:Math.sin(t*.13)*.04)-pointer.y*.04-group.current.rotation.x)*Math.min(delta*2,1);group.current.rotation.z=-.055+(reduced?0:Math.sin(t*.16)*.02);group.current.position.y=reduced?0:Math.sin(t*.52)*.012;group.current.scale.setScalar(1.91+(reduced?0:Math.sin(t*.82)*.009));}
 });
 return <group ref={group} scale={1.91} rotation={[.2,-.92,-.055]}>
  {geometry.map((g,i)=><mesh key={i} geometry={g} material={materials.veil} renderOrder={0}/>)}
  <lineSegments geometry={connectome.tracts} material={materials.tracts} renderOrder={1}/>
  <lineSegments geometry={micro.lines} material={materials.surface} renderOrder={1}/>
  <points geometry={micro.points} material={materials.nuclei} renderOrder={2}/>
  <points geometry={connectome.nuclei} material={materials.nuclei} renderOrder={2}/>
  <lineSegments geometry={cortex.lines} material={materials.surface} renderOrder={3}/>
  <points geometry={cortex.points} material={materials.points} renderOrder={4}/>
  <lineSegments geometry={field} material={materials.field} renderOrder={5}/>
 </group>;
}
class SceneBoundary extends Component<{children:ReactNode},{failed:boolean}>{state={failed:false};static getDerivedStateFromError(){return{failed:true};}render(){return this.state.failed?<div className="core-fallback"><div className="fallback-nucleus"/><p>Friday is here.</p><small>3D rendering is unavailable in this browser.</small></div>:this.props.children;}}
export default function NeuralPresence({state,visible=true}:{state:CognitiveState;visible?:boolean}){
 const [pageVisible,setPageVisible]=useState(!document.hidden);
 useEffect(()=>{const onVisibility=()=>setPageVisible(!document.hidden);document.addEventListener('visibilitychange',onVisibility);return()=>document.removeEventListener('visibilitychange',onVisibility);},[]);
 const [reduced,setReduced]=useState(()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches||document.documentElement.classList.contains('vision-reduced-motion'));
 useEffect(()=>{const query=window.matchMedia('(prefers-reduced-motion: reduce)');const change=()=>setReduced(query.matches||document.documentElement.classList.contains('vision-reduced-motion'));query.addEventListener('change',change);const observer=new MutationObserver(change);observer.observe(document.documentElement,{attributes:true,attributeFilter:['class']});return()=>{query.removeEventListener('change',change);observer.disconnect();};},[]);
 return <SceneBoundary><Canvas frameloop={visible&&pageVisible?'always':'never'} camera={{position:[0,.15,4.8],fov:36}} dpr={[1,1.5]} gl={{alpha:true,antialias:true,powerPreference:'high-performance'}} aria-label={`Friday neural presence. ${state}. Interactive 3D brain.`}><Brain state={state} reduced={reduced}/><EffectComposer multisampling={0}><Bloom intensity={.46} luminanceThreshold={.65} luminanceSmoothing={.4} mipmapBlur/></EffectComposer></Canvas></SceneBoundary>;
}
