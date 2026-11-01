const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function setup() {
  const elements = new Map();
  const element = selector => {
    if (!elements.has(selector)) elements.set(selector, {
      hidden:false, disabled:false, open:true, value:'', dataset:{}, files:[],
      classList:{add(){},remove(){},toggle(){}},
      listeners:{}, addEventListener(type, fn){this.listeners[type]=fn},
      setAttribute(key,value){this[key]=value}, removeAttribute(key){delete this[key]},
      querySelector(s){return element(selector+' '+s)}, querySelectorAll(){return []},
      play:async()=>{}, reset(){}, close(){this.open=false;this.listeners.close?.()},
      videoWidth:640,videoHeight:480,readyState:4,
      getBoundingClientRect(){return {width:400,height:300}}
    });
    return elements.get(selector);
  };
  const streams=[]; const calls=[];
  const navigator={mediaDevices:{getUserMedia:async()=>{
    const track={stopped:false,stop(){this.stopped=true}};
    const stream={getTracks:()=>[track],track};streams.push(stream);return stream;
  }}};
  const context = vm.createContext({console, Blob, URL, setTimeout,clearTimeout,
    FormData:class extends FormData{constructor(){super()}}, navigator,
    document:{querySelector:element,querySelectorAll:()=>[],addEventListener(){},createElement:()=>({getContext:()=>({drawImage(){}}),toBlob:fn=>fn(new Blob(['camera JPEG'],{type:'image/jpeg'}))})},
    window:{addEventListener(){},location:{}},
    fetch:async(url, options={})=>{calls.push({url,options});return {ok:true,json:async()=>url==='/api/classes'?{classes:[],today:'2026-10-24'}:url==='/api/students'?{name:'Test'}:{students:[]}}}
  });
  vm.runInContext(fs.readFileSync('frontend/app.js','utf8'),context);
  return {context,element,streams,calls,navigator,run:code=>vm.runInContext(code,context)};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('capture previews JPEG, stops camera, and submits captured image without file upload',async()=>{
  const t=setup(); await tick();
  await t.run('startEnrollmentCamera()');
  assert.equal(t.element('#enroll-video').hidden,false);
  t.element('#enroll-capture').onclick();
  assert.equal(t.streams[0].track.stopped,true);
  assert.equal(t.element('#enroll-preview').hidden,false);
  assert.equal(t.element('#enroll-retake').hidden,false);
  const form=t.element('#student-form');
  await form.listeners.submit({preventDefault(){},currentTarget:form});
  const request=t.calls.find(c=>c.url==='/api/students');
  assert.ok(request);
  const photo=request.options.body.get('images');
  assert.equal(photo.type,'image/jpeg');
  assert.equal(photo.name,'webcam.jpg');
  assert.equal(await photo.text(),'camera JPEG');
  assert.equal(request.options.body.get('use_guide'),'true');
});
test('closing a dialog cancels pending camera permission and stops late stream',async()=>{
  const t=setup();await tick();let resolve;
  const track={stopped:false,stop(){this.stopped=true}};
  t.navigator.mediaDevices.getUserMedia=()=>new Promise(r=>resolve=r);
  const opening=t.run('startEnrollmentCamera()');
  t.element('#student-dialog').close();
  resolve({getTracks:()=>[track]});await opening;
  assert.equal(track.stopped,true);
  assert.equal(t.run('enrollment.stream'),null);
});
test('retake clears old photo; switching to upload stops webcam',async()=>{
  const t=setup();await tick();await t.run('startEnrollmentCamera()');
  t.element('#enroll-capture').onclick();
  await t.run('startEnrollmentCamera()');
  assert.equal(t.run('enrollment.photo'),null);
  t.run("setEnrollmentMode('upload')");
  assert.equal(t.streams[1].track.stopped,true);
  assert.equal(t.element('#enroll-upload-section').hidden,false);
});
test('camera permission error is shown and empty capture cannot submit',async()=>{
  const t=setup();await tick();
  t.navigator.mediaDevices.getUserMedia=async()=>{const e=new Error();e.name='NotAllowedError';throw e};
  await t.run('startEnrollmentCamera()');
  assert.match(t.element('#enroll-status').textContent,/Chưa có quyền/);
  const form=t.element('#student-form');
  await form.listeners.submit({preventDefault(){},currentTarget:form});
  assert.equal(t.calls.some(c=>c.url==='/api/students'),false);
  assert.match(form.querySelector('.form-error').textContent,/chụp ảnh/);
});

test('session selection scopes roster and recognition to the chosen lesson', async()=>{
  const t=setup(); await tick();
  t.run("state.classId=2; state.today='2026-10-28'; state.view='attendance'; state.sessionId=8; state.sessions=[{id:8,can_attend:true,status:'open',name:'Morning',day:'2026-10-28',starts_at:'00:00:00',ends_at:'23:59:59'}]");
  assert.equal(t.run('rosterQuery()'),'day=2026-10-28&session_id=8');
  t.run("state.view='history'; state.sessionId=null");
  t.element('#history-date').value='2026-10-27';
  assert.equal(t.run('rosterQuery()'),'day=2026-10-27');
});

test('closed session prevents camera image from being submitted',async()=>{
  const t=setup(); await tick();
  t.run("state.classId=2; state.sessionId=8; state.sessions=[{id:8,can_attend:false}]");
  await t.run("recognize(new Blob(['image']))");
  assert.equal(t.calls.filter(c=>c.url.includes('/recognize')).length,0);
  assert.match(t.element('#recognition-result').textContent,/buổi đang mở/);
});
