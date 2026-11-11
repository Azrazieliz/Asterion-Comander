'use strict';
const $ = (q) => document.querySelector(q);
const state = {token:'', page:'desktop', device:'', job:'', selectedFile:'', imageUrl:null, phoneUrl:null, desktopRight:false, busy:false, phoneInfo:null};
const embedded = new URLSearchParams(location.search).get('embedded')==='1';
if(embedded)document.body.classList.add('embedded');
const api = '/api/v1';
let frameTimer;let lastFrame=0;let live=null;let liveRetry=null;
let liveTarget=null,liveRequestId=0;
const livePending=new Map();
function clearPendingInputs(error){
  for(const [id,entry] of livePending){clearTimeout(entry.timeout);entry.reject(error);}
  livePending.clear();
}
async function controlInput(source,payload){
  // A single live authenticated LAN socket carries frames and input acknowledgements.
  // Fall back to the existing authorized local REST route if WebSocket is unavailable.
  if(!live||live.readyState!==WebSocket.OPEN||liveTarget!==source){
    return request(source==='desktop'?'/input':'/phone/input',{method:'POST',body:payload});
  }
  const id=String(++liveRequestId);
  return new Promise((resolve,reject)=>{
    const started=performance.now();
    const timeout=setTimeout(()=>{
      livePending.delete(id);reject(new Error('Live input acknowledgement timed out'));
    },3500);
    livePending.set(id,{resolve,reject,timeout,started});
    try{live.send(JSON.stringify({type:'input',id,payload}));}
    catch(e){clearTimeout(timeout);livePending.delete(id);reject(e);}
  });
}

function friendlyError(error){
 const message=String(error?.message||error||'Connection unavailable');
 if(/503|screen.*unavailable|screen sharing|media.?projection|capture/i.test(message))
   return 'Phone screen sharing is paused. Open Control, tap Start screen sharing, and approve Android’s prompt.';
 if(/401|403|unauthorized|forbidden/i.test(message))return 'Authorization was rejected. Reconnect this device in Control.';
 if(/unreachable|timed out|network|failed to fetch/i.test(message))return 'The device is not reachable. Check its connection and retry.';
 return message.length>140?message.slice(0,137)+'…':message;
}
function phoneStatus(message,kind='warn'){
 const el=$('#android-status');
 if(el){el.textContent=message;el.className='device-status '+kind;}
}
function toast(message){const el=$('#toast');el.textContent=friendlyError(message);el.style.display='block';clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.style.display='none',4200);}
async function request(path,options={}){
 const headers={Authorization:`Bearer ${state.token}`,...(options.headers||{})};
 if(options.body && !(options.body instanceof Blob) && !(options.body instanceof ArrayBuffer) && typeof options.body==='object'){
  options.body=JSON.stringify(options.body);headers['Content-Type']='application/json';
 }
 const r=await fetch(api+path,{...options,headers,cache:'no-store'});
 if(!r.ok){let detail='HTTP '+r.status;try{const j=await r.json();detail=j.detail||detail}catch{}throw new Error(detail);}
 if(options.blob)return await r.blob();
 const type=r.headers.get('content-type')||'';
 return type.includes('json')?r.json():r.text();
}
function qp(obj){return '?'+new URLSearchParams(obj).toString()}
function showPage(name){ state.page=name;document.querySelectorAll('.page').forEach(e=>e.classList.toggle('active',e.id===name));document.querySelectorAll('.tabs button').forEach(e=>e.classList.toggle('active',e.dataset.page===name)); if(name==='android')discover().catch(e=>toast(e.message));if(name==='files')files().catch(e=>toast(e.message));if(name==='processes')processes().catch(e=>toast(e.message));if(name==='system')system().catch(e=>toast(e.message)); startLive();}
async function connect(){
 state.token=$('#token').value.trim()||state.token;
 if(!state.token){toast('Enter the Windows access key');return;}
 try{
   const h=await request('/health');
   $('#connection').textContent=h.host+' · Connected';
   $('#connection').classList.remove('off');
   document.body.classList.add('paired');
   $('#token').value='';
   if($('#health-body'))$('#health-body').textContent=JSON.stringify(h,null,2);
   if(state.page==='android')await discover();
   await discoverMonitors();
   startLive();
 }catch(e){
   document.body.classList.remove('paired');
   $('#connection').textContent='Disconnected';
   $('#connection').classList.add('off');
   toast(e);
 }
}
async function shot(url,img,placeholder,key){if(!state.token)return;const blob=await request(url,{blob:true});const object=URL.createObjectURL(blob);if(state[key])URL.revokeObjectURL(state[key]);state[key]=object;img.src=object;img.classList.add('shown');$(placeholder).style.display='none';}
async function screen(){
 if(!state.token||state.busy)return;
 if(state.page==='android'&&state.device==='native'&&state.phoneInfo?.capture===false){
   phoneStatus('Phone connected · Screen sharing is paused. Start it in Control.');return;
 }
 state.busy=true;
 try{
   if(state.page==='desktop')await shot('/screen'+qp({monitor:$('#desktop-monitor').value}),$('#desktop-image'),'#desktop-empty','imageUrl');
   else if(state.page==='android'&&state.device)await shot(state.device==='native'?'/phone/screen':'/android/'+encodeURIComponent(state.device)+'/screen',$('#android-image'),'#android-empty','phoneUrl');
 }catch(e){
   if(state.page==='android')phoneStatus(friendlyError(e));
   else toast(e);
 }finally{state.busy=false;}
}
async function discoverMonitors(){try{const data=await request('/monitors');const select=$('#desktop-monitor');select.replaceChildren();for(const m of data.items){const o=document.createElement('option');o.value=m.index;o.textContent=m.index===0?'All monitors':'Monitor '+m.index;select.append(o);}select.value=String(data.items.length>1?1:0);}catch(e){toast(e.message)}}
function startScreenRefresh(){clearInterval(frameTimer);frameTimer=setInterval(()=>{if(live&&live.readyState===WebSocket.OPEN)return;if(!state.token)return;if(state.page==='desktop'||state.page==='android'&&state.device)screen();},1600);}
function startLive(){
 clearTimeout(liveRetry);clearPendingInputs(new Error('Live stream replaced'));if(live){live.onclose=null;live.close();live=null;} liveTarget=null;
 if(!state.token)return;
 if(state.page==='android'&&state.device==='native'&&state.phoneInfo?.capture===false)return;
 const target=state.page==='desktop'?'desktop':state.page==='android'&&state.device==='native'?'phone':null;
 if(!target)return;
 const protocol=location.protocol==='https:'?'wss:':'ws:';
 const ws=new WebSocket(protocol+'//'+location.host+'/api/v1/stream/'+target);
 live=ws;liveTarget=target;ws.binaryType='blob';
 ws.onopen=()=>ws.send(JSON.stringify({token:state.token,monitor:Number($('#desktop-monitor').value),fps:Number($('#desktop-fps').value)}));
 ws.onmessage=e=>{
   if(typeof e.data==='string'){
     try{
       const data=JSON.parse(e.data);
       if(data.type==='input_ack'){
         const entry=livePending.get(data.id);
         if(entry){
           livePending.delete(data.id);clearTimeout(entry.timeout);
           if(data.ok){
             const rtt=Math.round(performance.now()-entry.started);
             const signal=document.querySelector('.signal');
             if(signal)signal.textContent='● DIRECT LIVE · input '+rtt+' ms';
             entry.resolve({ok:true,rtt_ms:rtt,device_ms:data.device_ms});
           }else entry.reject(new Error(data.error||'Input refused'));
         }
       }else if(data.type==='error'){
         if(target==='phone')phoneStatus(friendlyError(data.error||'Live phone stream unavailable'));
         else toast(data.error||'Live stream error');
       }else if(data.error){if(target==='phone')phoneStatus(friendlyError(data.error));else toast(data.error);}
     }catch(ex){toast('Invalid stream response');}
     return;
   }
   if(state.page!==(target==='desktop'?'desktop':'android'))return;
   const img=target==='desktop'?$('#desktop-image'):$('#android-image');
   const obj=URL.createObjectURL(e.data);const old=img.dataset.objectUrl;
   img.src=obj;img.dataset.objectUrl=obj;img.classList.add('shown');
   (target==='desktop'?$('#desktop-empty'):$('#android-empty')).style.display='none';
    if(target==='phone')phoneStatus('Phone connected · Live screen sharing', 'good');
   if(old)URL.revokeObjectURL(old);
 };
 ws.onclose=()=>{if(live===ws){live=null;liveTarget=null;clearPendingInputs(new Error('Live connection lost'));liveRetry=setTimeout(startLive,2500);}};
 ws.onerror=()=>{};
}
function screenCoords(img, ev){const r=img.getBoundingClientRect();const width=img.naturalWidth,height=img.naturalHeight;const scale=Math.min(r.width/width,r.height/height);const renderW=width*scale,renderH=height*scale;const offsetX=(r.width-renderW)/2, offsetY=(r.height-renderH)/2;const x=Math.round((ev.clientX-r.left-offsetX)/scale),y=Math.round((ev.clientY-r.top-offsetY)/scale);if(x<0||y<0||x>=width||y>=height)return null;return {x,y};}
function bindPointer(img,mode){let pressed=null;img.addEventListener('pointerdown',ev=>{pressed={...screenCoords(img,ev),time:Date.now()};if(!Number.isFinite(pressed.x))pressed=null;img.setPointerCapture(ev.pointerId)});img.addEventListener('pointerup',async ev=>{if(!pressed)return;const end=screenCoords(img,ev);if(!end){pressed=null;return;}const begin=pressed;pressed=null;const elapsed=Date.now()-begin.time;const distance=Math.hypot(end.x-begin.x,end.y-begin.y);try{if(mode==='desktop'){if(distance>18){await controlInput('desktop',{action:'drag',monitor:Number($('#desktop-monitor').value),x:begin.x,y:begin.y,to_x:end.x,to_y:end.y,seconds:Math.max(.2,Math.min(3,elapsed/1000))})}else{await controlInput('desktop',{action:state.desktopRight?'right_click':'click',monitor:Number($('#desktop-monitor').value),...end});}}else if(state.device){const action=distance>30?'swipe':elapsed>600?'long_press':'tap';if(state.device==='native'){const inf=state.phoneInfo||{};const sx=(inf.screen_width||img.naturalWidth)/img.naturalWidth,sy=(inf.screen_height||img.naturalHeight)/img.naturalHeight;await androidAction({action,x:Math.round(begin.x*sx),y:Math.round(begin.y*sy),x2:Math.round(end.x*sx),y2:Math.round(end.y*sy),duration_ms:Math.max(200,Math.min(5000,elapsed))});}else await androidAction({action,x:begin.x,y:begin.y,to_x:end.x,to_y:end.y,duration_ms:Math.max(200,Math.min(10000,elapsed))});}if(!live)setTimeout(screen,250);}catch(e){toast(e.message)}});img.addEventListener('contextmenu',e=>e.preventDefault());}
async function discover(){
 const select=$('#device-select');select.replaceChildren();
 let native=null;
 try{native=await request('/phone');}
 catch(e){phoneStatus(friendlyError(e));}
 const detail=$('#android-detail');
 if(detail)detail.hidden=true;
 if(native?.paired&&native?.reachable){
   const opt=document.createElement('option');opt.value='native';
   opt.textContent=(native.device||'Android')+' · Native';select.append(opt);
   state.device='native';state.phoneInfo=native.info||{};
   const info=state.phoneInfo,access=info.accessible===true,capture=info.capture===true;
   if(!capture){
     phoneStatus('Phone connected · Start screen sharing in Control to see the display.');
   }else if(!access){
     phoneStatus('Live screen available · Accessibility input not authorized.');
   }else{
     phoneStatus('Phone connected · Screen and touch ready','good');
   }
 }else{
   state.device='';state.phoneInfo=null;
   if(!native?.paired)phoneStatus('Phone not registered with Windows. Use Force activate connection in Control.');
   else phoneStatus(friendlyError(native?.reason||'Windows cannot reach the phone agent.'));
   $('#android-image').classList.remove('shown');$('#android-empty').style.display='flex';
 }
 select.value=state.device;
 startLive();
}
function formatPhoneInfo(info){
 const transport=info.remote_transport||{};
 const wss=transport.direct_mcp||{};
 const net=transport.network||'Unavailable';
 const screen=info.capture?'Active':'Off — start screen sharing in Control';
 const input=info.accessible?'Authorized':'Not authorized — enable Accessibility';
 const live=wss.connected===true?'Connected':wss.phase||'Unavailable';
 return ['Device: '+(info.device||'Android'),
   'Android: '+(info.android||'Unknown'),
   'Screen sharing: '+screen,
   'Touch input: '+input,
   'Network: '+net,
   'Direct WebSocket: '+live
 ].join('\n');
}

async function androidAction(action){
 if(state.device!=='native')throw Error('Android agent not paired');
 const a={...action};
 if(a.action==='key'){const map={KEYCODE_BACK:'back',KEYCODE_HOME:'home',KEYCODE_APP_SWITCH:'recents'};if(!map[a.key])throw Error('Unsupported key');a.action=map[a.key];delete a.key;}
 if(a.action==='text')a.action='type';
 await controlInput('phone',a);
}
function human(n){if(n==null)return '—';const a=['B','KB','MB','GB','TB'];let i=0;while(n>1024&&i<4){n/=1024;i++}return n.toFixed(i?1:0)+' '+a[i]}
async function files(){const path=$('#path').value.trim()||'.';const data=await request('/files'+qp({path}));const list=$('#file-list');list.replaceChildren();for(const f of data.items){const b=document.createElement('button');b.className='fileitem';const lhs=document.createElement('span');lhs.textContent=(f.directory?'▣ ':'▤ ')+f.name;const rhs=document.createElement('span');rhs.className='muted';rhs.textContent=f.directory?'Folder':human(f.size);b.append(lhs,rhs);b.addEventListener('click',async()=>{if(f.directory){$('#path').value=f.path;await files();}else{state.selectedFile=f.path;$('#file-title').textContent=f.path;try{const data=await request('/files/read'+qp({path:f.path}));$('#file-content').value=data.content;}catch(e){$('#file-content').value='';toast(e.message)}}});list.append(b);}if(!data.items.length)list.textContent='Directory is empty.';}
async function runCommand(){const text=$('#command').value.trim();if(!text)return;try{const r=await request('/commands',{method:'POST',body:{command:text,cwd:$('#cwd').value||'.'}});state.job=r.id;$('#job-meta').textContent='Job '+r.id.slice(0,8)+' · PID '+r.pid;await readJob();toast('Started '+r.id.slice(0,8));}catch(e){toast(e.message)}}
async function readJob(){if(!state.job)return;const d=await request('/commands/'+state.job);$('#terminal-output').textContent=d.output||'(No output yet)';$('#job-meta').textContent=d.status+' · PID '+d.pid+(d.exit_code==null?'':' · exit '+d.exit_code);if(d.status==='running')setTimeout(()=>{if(state.page==='terminal')readJob().catch(e=>toast(e.message))},1300)}
async function processes(){const r=await request('/processes?limit=160');const body=$('#process-body');body.replaceChildren();for(const p of r.items){const tr=document.createElement('tr');for(const v of [p.pid,p.name,human(p.memory),p.status]){const td=document.createElement('td');td.textContent=String(v);tr.append(td);}const td=document.createElement('td'),b=document.createElement('button');b.textContent='Terminate';b.addEventListener('click',async()=>{if(!confirm('Terminate process '+p.pid+' ('+p.name+')?'))return;try{await request('/processes/'+p.pid+'/terminate',{method:'POST'});await processes();}catch(e){toast(e.message)}});td.append(b);tr.append(td);body.append(tr)}}
async function system(){
 const d=await request('/device-health');const box=$('#system-body');box.replaceChildren();
 const metrics=[['Host',d.host],['CPU load',d.cpu_percent.toFixed(1)+'%'],
 ['RAM pressure',d.memory.percent+'% · '+human(d.memory.available)+' available'],
 ['Battery',d.battery ? d.battery.percent+'% · '+(d.battery.plugged?'charging':'on battery') : 'Not exposed by OS'],
 ['Thermal sensors',d.thermals.available ? d.thermals.sensors.map(x=>x.label+': '+x.celsius+'°C').join(' · ') : 'Not exposed by OS'],
 ['Thermal pressure',d.thermals.thermal_pressure],['GPU sensors',d.gpu.available?'Available':'Not exposed by OS']];
 for(const disk of d.disks)metrics.push(['Storage '+disk.mount,human(disk.free)+' free · '+disk.percent_used+'% used']);
 for(const [name,value] of metrics){const node=document.createElement('article');node.className='stat';const l=document.createElement('label');l.textContent=name;const v=document.createElement('div');v.className='metric';v.textContent=value;node.append(l,v);box.append(node)}
}
function bind(id,fn){$(id).addEventListener('click',async()=>{try{await fn()}catch(e){toast(e.message)}})}
document.querySelectorAll('.tabs button').forEach(b=>b.addEventListener('click',()=>showPage(b.dataset.page)));
bind('#connect',connect);bind('#reconnect',connect);$('#token').addEventListener('keydown',e=>{if(e.key==='Enter')connect()});
bind('#desktop-shot',screen);$('#desktop-monitor').addEventListener('change',startLive);bind('#android-shot',screen);bind('#refresh-devices',discover);
$('#device-select').addEventListener('change',e=>{state.device=e.target.value;startLive();if(!live)screen()});
$('#desktop-fps').addEventListener('change',startLive);
bind('#desktop-backspace',()=>request('/input',{method:'POST',body:{action:'press',keys:['backspace']}}));
bind('#desktop-enter',()=>request('/input',{method:'POST',body:{action:'press',keys:['enter']}}));
bind('#desktop-escape',()=>request('/input',{method:'POST',body:{action:'press',keys:['esc']}}));
bind('#desktop-right',()=>{state.desktopRight=!state.desktopRight;$('#desktop-right').textContent='Right-click mode: '+(state.desktopRight?'ON':'OFF')});
bind('#desktop-type',()=>request('/input',{method:'POST',body:{action:'type',text:$('#desktop-text').value}}));
document.querySelectorAll('[data-android-key]').forEach(b=>b.addEventListener('click',()=>androidAction({action:'key',key:b.dataset.androidKey}).catch(e=>toast(e.message))));
bind('#android-type',()=>androidAction({action:'text',text:$('#android-text').value}));
bind('#android-pair',async()=>{const address=prompt('Wireless debugging pairing address (IP:pairing-port):');if(!address)return;const code=prompt('Six-digit pairing code shown on your phone:');if(!code)return;const result=await request('/android/pair',{method:'POST',body:{address,code}});toast(result.output);await discover();});
bind('#android-connect',async()=>{const address=prompt('Wireless debugging connection address (IP:connection-port):');if(!address)return;const result=await request('/android/connect',{method:'POST',body:{address}});toast(result.output);await discover();});
bind('#android-info',async()=>{
 if(!state.device){phoneStatus('Phone not connected. Use Force activate connection in Control.');return;}
 const detail=$('#android-detail');
 if(!detail.hidden){detail.hidden=true;return;}
 const info=await request(state.device==='native'?'/phone/health':'/android/'+encodeURIComponent(state.device)+'/info');
 detail.textContent=formatPhoneInfo(info);
 detail.hidden=false;
});
bind('#android-ui',async()=>{const v=await request(state.device==='native'?'/phone/ui':'/android/'+encodeURIComponent(state.device)+'/ui');$('#android-detail').textContent=(typeof v==='string'?v:JSON.stringify(v,null,2)).slice(0,30000)});
bind('#terminal-run',runCommand);bind('#terminal-refresh',readJob);bind('#terminal-stop',async()=>{if(state.job)await request('/commands/'+state.job+'/stop',{method:'POST'})});
bind('#terminal-list',async()=>{$('#terminal-output').textContent=JSON.stringify(await request('/commands'),null,2)});
bind('#android-run-command',async()=>{if(!state.device)throw Error('Select a phone');const d=await request('/android/'+encodeURIComponent(state.device)+'/shell',{method:'POST',body:{command:$('#android-command').value}});$('#android-shell-output').textContent=d.output});
bind('#open-dir',files);bind('#file-refresh',files);bind('#file-up',()=>{const p=$('#path').value.split(/[\\/]/).filter(Boolean);p.pop();$('#path').value=p.join('/')||'.';return files()});
bind('#file-mkdir',async()=>{const name=prompt('Folder path relative to root:',$('#path').value==='.'?'':$('#path').value+'/');if(name){await request('/files/mkdir',{method:'POST',body:{path:name}});await files()}});
bind('#file-new',async()=>{const name=prompt('New file path:',$('#path').value==='.'?'':$('#path').value+'/');if(name){await request('/files/write',{method:'PUT',body:{path:name,content:'',overwrite:false}});await files()}});
bind('#file-save',async()=>{if(!state.selectedFile)throw Error('Select a file');await request('/files/write',{method:'PUT',body:{path:state.selectedFile,content:$('#file-content').value,overwrite:true}});toast('Saved '+state.selectedFile)});
bind('#file-delete',async()=>{if(!state.selectedFile)return;if(!confirm('Delete '+state.selectedFile+'?'))return;await request('/files'+qp({path:state.selectedFile}),{method:'DELETE'});state.selectedFile='';$('#file-content').value='';await files()});
bind('#file-rename',async()=>{if(!state.selectedFile)return;const dest=prompt('New path:',state.selectedFile);if(dest&&dest!==state.selectedFile){await request('/files/move',{method:'POST',body:{source:state.selectedFile,destination:dest}});state.selectedFile=dest;await files()}});
bind('#file-search',async()=>{const q=prompt('Find filename containing:');if(q){const r=await request('/files/search'+qp({path:$('#path').value,q}));const list=$('#file-list');list.replaceChildren();for(const item of r.items){const b=document.createElement('button');b.className='fileitem';b.textContent=item.path;b.addEventListener('click',()=>{state.selectedFile=item.path;$('#file-title').textContent=item.path;request('/files/read'+qp({path:item.path})).then(v=>$('#file-content').value=v.content).catch(e=>toast(e.message))});list.append(b)}}});
bind('#file-download',async()=>{if(!state.selectedFile)return;const blob=await request('/files/download'+qp({path:state.selectedFile}),{blob:true});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=state.selectedFile.split('/').pop();a.click();setTimeout(()=>URL.revokeObjectURL(url),2000)});
$('#file-upload').addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;let path=($('#path').value==='.'?'':$('#path').value.replace(/\/$/,'')+'/')+file.name;try{await request('/files/upload'+qp({path}),{method:'PUT',body:file,headers:{'Content-Type':'application/octet-stream'}});toast('Uploaded '+file.name);await files()}catch(err){toast(err.message)}e.target.value=''});
bind('#process-refresh',processes);bind('#system-refresh',system);
bindPointer($('#desktop-image'),'desktop');bindPointer($('#android-image'),'android');
startScreenRefresh();
