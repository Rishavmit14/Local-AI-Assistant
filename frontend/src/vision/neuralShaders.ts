export const cognitionGLSL = `
uniform float uTime;
uniform float uActivity;
uniform float uMode;
uniform float uPrevious;
uniform float uTransition;
float pulse(float x, float center, float width) {float d=abs(x-center);return exp(-d*d/width);}
float cognition(float mode,float p,float phase,float bundle) {
 float t=uTime;
 float signal=0.;
 if(mode<.5){
  float beat=fract(p-t*.07+phase);signal=pulse(beat,.5,.0017)*(.38+.28*sin(phase*36.));
 } else if(mode<1.5){
  signal=pulse(fract(p+t*.21+phase*.3),.5,.004) * (.65+.35*sin(t*1.7));
 } else if(mode<2.5){
  float routing=sin(t*1.2+phase*28.);signal=pulse(fract(p-t*.28+phase),.5,.0018)*smoothstep(-.4,.45,routing)*1.3;
  signal+=pulse(p,.25+.5*sin(t*.4+phase*9.)*.5,.008)*pow(max(0.,sin(t*1.5+phase*18.)),8.)*.5;
 } else if(mode<3.5){
  float voice=.4+.35*sin(t*3.7)+.25*sin(t*7.1);signal=pulse(fract(p-t*.25+phase*.12),.5,.0045)*(.4+abs(voice))*(bundle>1.5?1.4:.7);
 } else if(mode<4.5){
  signal=pulse(fract(p-t*.20+floor(phase*7.)*.14),.5,.0025)*(.3+step(.45,fract(phase*4.+floor(t*.4)*.19)));
 } else if(mode<5.5){
  signal=pulse(p,.52,.015)*(.42+.3*sin(t*1.1))*smoothstep(.35,.8,phase);
 } else if(mode<6.5){
  float alert=pow(max(0.,sin(t*2.1)),12.);signal=pulse(p,.64,.006)*alert*.9;
  signal+=pulse(fract(p-t*.09+phase),.5,.0008)*.18;
 } else {
  signal=pulse(fract(p-t*.16+phase*.05),.5,.004)*smoothstep(.48,.8,phase)*1.5;
 }
 return max(0.,signal);
}
float activity(float p,float phase,float bundle){return mix(cognition(uPrevious,p,phase,bundle),cognition(uMode,p,phase,bundle),smoothstep(0.,1.,uTransition));}
vec3 signalColor(float bundle,float phase){
 vec3 cold=mix(vec3(.29,.60,.80),vec3(.68,.80,1.),phase);
 vec3 warm=vec3(1.,.70,.36);
 vec3 c=mix(cold,warm,step(.83,phase)*.8);
 return c;
}
`;
export const cortexVertex=`
attribute float aCorticalDisplacement; attribute float aCorticalU; attribute float aCorticalQ; attribute float aCorticalLateral;
varying vec3 vNormal; varying vec3 vPosition; varying vec3 vView; varying float vFold; varying float vU; varying float vLateral;
void main(){vNormal=normalize(normalMatrix*normal);vPosition=position;vFold=aCorticalDisplacement;vU=aCorticalU;vLateral=aCorticalLateral;vec4 mv=modelViewMatrix*vec4(position,1.);vView=normalize(-mv.xyz);gl_Position=projectionMatrix*mv;}`;
export const cortexFragment=cognitionGLSL+`
varying vec3 vNormal; varying vec3 vPosition; varying vec3 vView; varying float vFold; varying float vU; varying float vLateral;
void main(){
 if(vLateral<.10)discard;
 vec3 n=normalize(vNormal)*(gl_FrontFacing?1.:-1.);vec3 eye=normalize(vView);
 float facing=abs(dot(n,eye));float rim=pow(1.-facing,3.4);
 float key=max(dot(n,normalize(vec3(-.7,.8,1.))),0.);
 float spec=pow(max(dot(n,normalize(normalize(vec3(-.6,.8,1.))+eye)),0.),34.);
 float ridge=smoothstep(-.014,.007,vFold);
 float lattice=pow(.5+.5*sin(vPosition.y*180.+vPosition.z*20.),18.);
 float signal=activity(vU,.45+vPosition.x*.48,0.);
 vec3 color=vec3(.055,.10,.18)*(.35+key*.65);
 color+=vec3(.19,.34,.47)*rim + vec3(.30,.46,.56)*spec*.2;
 color+=vec3(.17,.38,.49)*signal*ridge*.24;
 float alpha=(.028+rim*.19+ridge*.035+spec*.03)*(.25+.75*smoothstep(.05,.35,abs(vLateral)));
 alpha+=lattice*ridge*.025;
 if(!gl_FrontFacing)alpha*=.50;
 gl_FragColor=vec4(color,alpha);
}`;
export const fiberVertex=`attribute float aProgress;attribute float aPhase;attribute float aBundle;varying float vProgress;varying float vPhase;varying float vBundle;varying float vDepth;void main(){vProgress=aProgress;vPhase=aPhase;vBundle=aBundle;vec4 mv=modelViewMatrix*vec4(position,1.);vDepth=-mv.z;gl_Position=projectionMatrix*mv;}`;
export const fiberFragment=cognitionGLSL+`
uniform float uLayer; varying float vProgress;varying float vPhase;varying float vBundle;varying float vDepth;
void main(){
 float firing=activity(vProgress,vPhase,vBundle);
 if(uLayer>1.5){float now=(step(.5,uMode)-step(1.5,uMode))+(step(2.5,uMode)-step(3.5,uMode));float prior=(step(.5,uPrevious)-step(1.5,uPrevious))+(step(2.5,uPrevious)-step(3.5,uPrevious));firing*=mix(prior,now,smoothstep(0.,1.,uTransition));}
 float edge=pow(sin(clamp(vProgress,.001,.999)*3.14159),.25);
 float depth=clamp(1.5-(vDepth-3.)*.23,.36,1.);
 vec3 color=signalColor(vBundle,vPhase);
 float rest=uLayer<.5?.075:uLayer<1.5?.16:.012;
 vec3 lit=color;
 if(uMode>4.5&&uMode<5.5)lit=vec3(1.,.72,.38);
 if(uMode>5.5&&uMode<6.5)lit=vec3(1.,.42,.31);
 vec3 result=(color*rest+lit*firing*(uLayer<.5?.48:uLayer<1.5?.51:.40))*depth;
 gl_FragColor=vec4(result,clamp((rest*2.+firing*.78)*edge*depth,0.,.9));
}`;
export const pointVertex=cognitionGLSL+`
attribute float aPhase;attribute float aBundle;attribute float aProgress;attribute float aSize;varying float vPhase;varying float vBundle;varying float vSignal;varying float vDepth;uniform float uLayer;
void main(){vPhase=aPhase;vBundle=aBundle;vSignal=activity(aProgress,aPhase,aBundle);vec4 mv=modelViewMatrix*vec4(position,1.);vDepth=-mv.z;gl_Position=projectionMatrix*mv;float s=uLayer<.5?1.1:2.;gl_PointSize=clamp((s+vSignal*(uLayer<.5?2.3:5.))*aSize*3.6/-mv.z,.65,9.);}`;
export const pointFragment=cognitionGLSL+`
varying float vPhase;varying float vBundle;varying float vSignal;varying float vDepth;uniform float uLayer;
void main(){float d=length(gl_PointCoord-.5)*2.;if(d>1.)discard;float sharp=exp(-d*d*5.);float aura=exp(-d*d*1.5)*.18;float near=clamp(1.4-(vDepth-3.)*.23,.3,1.);vec3 color=signalColor(vBundle,vPhase);if(uMode>4.5&&uMode<5.5)color=mix(color,vec3(1.,.72,.38),min(1.,vSignal));if(uMode>5.5&&uMode<6.5)color=mix(color,vec3(1.,.42,.31),min(1.,vSignal));float base=uLayer<.5?.15:.18;gl_FragColor=vec4(color*(.6+vSignal*1.25), (sharp+aura)*(base+vSignal*.85)*near);}`;
