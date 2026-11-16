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
function showPage(name){ state.page=name;document.querySelectorAll('.page').forEach(e=>e.classList.toggle('active',e.id===name));document.querySelectorAll('.tabs button').forEach(e=>e.classList.toggle('active',e.dataset.page===name)); if(name==='android')discover().catch(e=>toast(e.message));if(name==='files')files().catch(e=>toast(e.message));if(name==='processes')processes().catch(e=>toast(e.message));if(name==='system')system().catch(e=>toast(e.message));if(name==='diagnostics')loadDiagnostics().catch(e=>toast(e.message)); startLive();}
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
   if(state.page==='diagnostics')await loadDiagnostics();
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
// Read-only diagnosis is deliberately not an inferred live phone status.
function diagnosticRecord(parent,title,detail,severity='neutral'){
 const item=document.createElement('article');
 item.className='diagnostic-record '+(severity==='warning'?'diagnostic-warning':'');
 const heading=document.createElement('strong');heading.textContent=title;
 const body=document.createElement('p');body.textContent=detail;
 item.append(heading,body);parent.append(item);
}
function readableDiagnosticIssue(finding){
 const code=String(finding.code||'');
 switch(code){
  case 'http_403':
   return ['A website or server refused a request (HTTP 403)',
    'Open that app and check which provider, URL stage, and authorization failed. HTTP 403 alone does not show a geographical block.'];
  case 'stale_operations':
   return ['Some work stopped reporting progress',
    'Open the affected app and check the current queue and worker state. A historical queued entry does not prove the job is still waiting.'];
  case 'crash_or_anr_reported':
   return ['An application crash or freeze was reported',
    'Check the matching crash stack or Android exit record and the build version; the recorded event alone does not identify the cause.'];
  default:
   return ['A failure was reported',
    'Inspect the originating app and its related request trace. Cause has not been verified.'];
 }
}
function readableDiagnosticEvent(event){
 const code=String(event.symptom||event.kind||'');
 if(code==='http_403_observed_not_root_cause'||event.status_code===403)
  return ['Server refused a request (403)','Open this app to check provider and authentication. This is not proof of a regional block.'];
 if(code.includes('crash')||code.includes('anr'))
  return ['App crash or freeze reported','A matching stack trace is needed to confirm the cause.'];
 if(code.includes('stalled')||code.includes('worker_dead'))
  return ['Worker progress stopped being reported','Check the worker in the originating application.'];
 return ['A failure event was recorded','The app-specific engine trace is needed to investigate.'];
}
function diagnosticAppAction(parent,app){
 if(!app||typeof app!=='string')return;
 const button=document.createElement('button');
 button.type='button';button.className='diagnostic-app-action';
 button.textContent='Investigate '+app;
 button.addEventListener('click',()=>{
  $('#diagnostic-app').value=app;
  loadDiagnostics().catch(e=>toast(e.message));
 });
 parent.append(button);
}
function readableExitState(code){
 const meanings={
  0:'Exit reason not reported by Android',
  1:'App closed itself',
  2:'App received a process signal',
  3:'Android stopped the app under memory pressure',
  4:'Java application crash',
  5:'Native-code application crash',
  6:'App stopped responding (ANR)',
  7:'App failed while starting',
  8:'Permissions changed',
  9:'Android reported excessive resource use',
  10:'User requested app exit',
  11:'User stopped the application',
  12:'An app dependency stopped',
  13:'Other operating-system exit'
 };
 return meanings[code]||'Android did not provide a recognized exit classification';
}
async function loadPhoneDiagnosticEvidence(){
 const panel=$('#diagnostic-phone');
 if(!panel)return;
 panel.replaceChildren();
 if(!state.token){
  diagnosticRecord(panel,'Connection required','Connect to Windows to read Control’s own Android event history.');
  return;
 }
 diagnosticRecord(panel,'Reading Control connection history','Checking the existing paired phone listener…');
 try{
  const head=await request('/phone/diagnostics/events'+qp({since:0,limit:1}));
  if(head.scope!=='asterion_control_process_only')throw new Error('Unexpected journal scope');
  const latest=Number(head.latest_sequence||0);
  const start=Math.max(0,latest-25);
  const page=await request('/phone/diagnostics/events'+qp({since:start,limit:25}));
  if(page.scope!=='asterion_control_process_only')throw new Error('Unexpected journal scope');
  panel.replaceChildren();
  const data=page.events||[];
  if(!data.length){
   diagnosticRecord(panel,'No Control connection events found',
    'Only Control’s own events can appear here. This does not tell us whether other apps are healthy.');
   return;
  }
  // Group repeated WSS/lifecycle messages. Rendering 15 identical cards hid
  // real app failures behind connection noise on the owner's phone.
  const grouped=new Map();
  for(const event of data.slice().reverse().slice(0,25)){
   const kind=String(event.kind||''),state=String(event.state||'');
   const stage=String(event.stage||'');
   const key=[kind,state,stage].join('|');
   if(!grouped.has(key))grouped.set(key,{kind,state,stage,count:0});
   grouped.get(key).count++;
  }
  const ordered=[...grouped.values()].sort((a,b)=>
   (a.state==='failed'?0:1)-(b.state==='failed'?0:1));
  for(const event of ordered.slice(0,6)){
   const {kind,state,stage,count}=event;
   let title=kind.replaceAll('_',' ');
   let detail='Historical Control event';
   if(kind.includes('transport')||kind.includes('wss')){
    title=state==='failed'?'Control connection problem':'Control connection activity';
    detail=state==='failed'?
     'A connection problem was recorded. Check the current live status.':
     'The phone and Windows exchanged a connection event.';
   }else if(kind.includes('service')){
    title='Control background service';
    detail='Android recorded a service lifecycle change.';
   }else if(state==='failed'||state==='error'){
    title='Control recorded an error';
    detail='Check current permissions and connection status.';
   }
   detail+=' '+count+' similar event'+(count===1?'':'s')+' recorded.';
   if(stage)detail+=' Area: '+stage.replaceAll('_',' ')+'.';
   diagnosticRecord(panel,title,detail,state==='failed'?'warning':'neutral');
  }
  diagnosticRecord(panel,'Scope of these records',
   'Only Control’s own process is visible. Other applications must send their own diagnostic evidence.');
 }catch(err){
  panel.replaceChildren();
  diagnosticRecord(panel,'Connection history unavailable',
   friendlyError(err)+' · No conclusion about app health can be drawn.','warning');
 }
}

async function loadIntegrationCoverage(){
 const panel=$('#diagnostic-coverage');
 if(!panel)return;
 panel.replaceChildren();
 if(!state.token){
  diagnosticRecord(panel,'Connection required',
   'Connect to Windows to see which apps have opted into Control.');
  return;
 }
 diagnosticRecord(panel,'Checking your Asterion applications',
  'Reading actual installed apps and native bridge support…');
 try{
  const data=await request('/diagnostics/coverage'+qp({
   lookback_minutes:Number($('#diagnostic-window').value),limit:1200}));
  if(!data.ok)throw new Error('Coverage response unverified');
  panel.replaceChildren();
  const count=data.native_partner_count;
  diagnosticRecord(panel,'Connected app evidence',
   'Apps that sent recent events: '+String(data.recent_event_source_count||0)+
   '. Apps exposing a native bridge: '+(count===null||count===undefined?
    'not checked':String(count))+'. These are separate capabilities.');
  if(!data.phone_app_catalog_available)
   diagnosticRecord(panel,'App list could not be read',
    'The phone list is unavailable at this moment. It does not mean your apps were removed.','warning');
  if(!data.partner_bridge_catalog_available)
   diagnosticRecord(panel,'Native integrations could not be checked',
    'An app’s bridge status must be checked on the phone.','warning');
  const apps=data.apps||[];
  if(!apps.length&&data.phone_app_catalog_available)
   diagnosticRecord(panel,'No matching Asterion apps in this sample',
    'Select a recorded source in the app filter above, or use Tools > Add an app on Android.');
  for(const app of apps.slice(0,50)){
   const title=String(app.name||app.package||'Asterion app');
   const bridge=app.partner_bridge_discovered?
    (app.partner_bridge_approved?'Connected with owner approval':
      'Native bridge exists; approve it in Control > Tools > Add an app'):
    'Native bridge not available in this installed version';
   const evidence=app.recent_instrumented_event_observed?
    'Events were recorded in this window':
    'No events from this app were recorded in this window';
   const item=document.createElement('div');
   item.className='diagnostic-coverage-item';
   diagnosticRecord(item,title,bridge+' · '+evidence);
   if(app.recent_instrumented_event_observed)
    diagnosticAppAction(item,app.package);
   panel.append(item);
  }
  if(data.events_window_may_be_truncated)
   diagnosticRecord(panel,'Only the newest events were inspected',
    'Use a narrower app filter to investigate a specific application.','warning');
 }catch(err){
  panel.replaceChildren();
  diagnosticRecord(panel,'App coverage could not be checked',
   friendlyError(err)+' · App installations and approvals have not been changed.','warning');
 }
}

async function loadDiagnostics(){
 if(!state.token){
  $('#diagnostic-state').textContent='Connect to Windows to check your Asterion apps.';
  return;
 }
 const status=$('#diagnostic-state');
 const guidance=$('#diagnostic-guidance');
 status.textContent='Checking recorded events…';
 guidance.textContent='Only diagnostic events that an app has actually reported can be inspected.';
 loadPhoneDiagnosticEvidence().catch(e=>toast(e.message));
 loadIntegrationCoverage().catch(e=>toast(e.message));
 const filter=$('#diagnostic-app').value.trim();
 const minutes=Number($('#diagnostic-window').value);
 try{
  const query={lookback_minutes:minutes,limit:1200,stale_after_seconds:300};
  if(filter)query.app=filter;
  const data=await request('/diagnostics/triage'+qp(query));
  const count=data.events_examined||0;
  const operations=data.operations||[];
  const needs=data.needs_fresh_state||[];
  const records=data.findings||[];
  const affected=data.observed_apps||[];
  status.className='device-status';
  if(count===0){
   status.textContent='No diagnostic events recorded in the selected period.';
   guidance.textContent='This does not prove any app is working. Use Tools > Add an app on Android to inspect native integration support, and instrument app engines for detailed failures.';
  }else if(records.length){
   status.textContent=records.length+' type(s) of recorded problem across '+affected.length+
    ' event source(s).';
   guidance.textContent='Select a problem to see what is known and the next useful check. These records do not identify root causes on their own.';
  }else{
   status.textContent=count+' events recorded from '+affected.length+
    ' source(s), with no classified failures in this sample.';
   guidance.textContent='This is not a clean bill of health. Many Asterion apps do not yet send detailed engine traces.';
  }
  const metrics=$('#diagnostic-metrics');metrics.replaceChildren();
  for(const [title,value] of [
    ['Recorded events',String(count)],
    ['Apps reporting events',String(affected.length)],
    ['Jobs with recorded IDs',String(operations.length)],
    ['Jobs needing a fresh check',String(needs.length)],
  ]){
   const card=document.createElement('article');card.className='diagnostic-metric';
   const number=document.createElement('strong');number.textContent=value;
   const label=document.createElement('span');label.textContent=title;
   card.append(number,label);metrics.append(card);
  }
  const findings=$('#diagnostic-findings');findings.replaceChildren();
  // Empty datasets are not actionable. Collapse their panels rather than
  // filling the small Android screen with success-looking placeholders.
  findings.closest('.diagnostic-panel').hidden=records.length===0;
  for(const f of records.slice(0,20)){
   const [title,next]=readableDiagnosticIssue(f);
   const item=document.createElement('div');
   diagnosticRecord(item,title,(f.meaning||'')+'\nNext useful check: '+next,'warning');
   findings.append(item);
  }
  const ops=$('#diagnostic-operations');ops.replaceChildren();
  const review=operations.filter(o=>o.review_reason);
  ops.closest('.diagnostic-panel').hidden=review.length===0;
  for(const op of review.slice(0,35)){
   const age=Math.max(0,Math.round(op.seconds_since_last_observation||0));
   const last=String(op.last_state||'not reported').replaceAll('_',' ');
   const cause=op.review_reason==='stale_nonterminal_observation'?
     'No recent update in this journal. Check the app’s current queue; the job may have finished since.':
     'A failure was reported. Check this job’s engine logs for the actual cause.';
   const item=document.createElement('div');
   diagnosticRecord(item,(op.app||'App')+' · Job '+(op.operation_id||'not identified'),
    'Last recorded: '+last+', '+age+' seconds before this snapshot. '+cause,'warning');
   diagnosticAppAction(item,op.app);
   ops.append(item);
  }
  const timeline=$('#diagnostic-timeline');timeline.replaceChildren();
  const notable=data.notable_events||[];
  timeline.closest('.diagnostic-panel').hidden=notable.length===0;
  for(const e of notable.slice().reverse().slice(0,25)){
   const [title,detail]=readableDiagnosticEvent(e);
   const item=document.createElement('div');
   const when=e.recorded_utc_ms?
    new Date(e.recorded_utc_ms).toLocaleString():'Recorded time unavailable';
   diagnosticRecord(item,title,'App: '+String(e.app||'Not identified')+
    ' · '+when+'. '+detail,'warning');
   diagnosticAppAction(item,e.app);
   timeline.append(item);
  }
  const limits=$('#diagnostic-limits');
  limits.textContent='What this view cannot check: other apps’ private logs, current engine queue status, the cause of an HTTP 403, or a model’s correctness. These need the respective app’s diagnostic bridge and real traces.'+
    (data.window_may_be_truncated||data.operations_truncated?
     ' The event limit was reached, so older records may be missing.':'');
 }catch(err){
  status.textContent='Could not read diagnostic events: '+friendlyError(err);
  status.className='device-status warn';
  guidance.textContent='The connection or diagnostic API needs checking. This is not proof of an app failure or successful operation.';
  for(const sel of ['#diagnostic-metrics','#diagnostic-findings',
                    '#diagnostic-operations','#diagnostic-timeline'])
   $(sel).replaceChildren();
 }
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
bind('#diagnostic-refresh',loadDiagnostics);$('#diagnostic-app').addEventListener('keydown',e=>{if(e.key==='Enter')loadDiagnostics()});
bindPointer($('#desktop-image'),'desktop');bindPointer($('#android-image'),'android');
startScreenRefresh();
