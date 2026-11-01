const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const paths = {
  scan: '<path d="M8 3H5a2 2 0 0 0-2 2v3m13-5h3a2 2 0 0 1 2 2v3M3 16v3a2 2 0 0 0 2 2h3m8 0h3a2 2 0 0 0 2-2v-3M7 12h10"/>',
  users: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6m2 3a5 5 0 0 1 3 5v2"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18m-13 4h2m4 0h2m-8 3h2"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  chart: '<path d="M4 4v16h17M8 15v-4m5 4V7m5 8v-6"/>',
  camera: '<path d="M4 6h3l2-3h6l2 3h3a1 1 0 0 1 1 1v12H3V7a1 1 0 0 1 1-1Z"/><circle cx="12" cy="12" r="4"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/>',
  download: '<path d="M12 3v13m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
  search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
  face: '<path d="M5 7c0-6 14-6 14 0v7c0 8-14 8-14 0Z"/><path d="M8 10h1m6 0h1m-7 6c2 2 4 2 6 0m-3-6v3"/>'
};
function icon(name) { return `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.grid}</svg>`; }
$$('[data-icon]').forEach(el => el.innerHTML = icon(el.dataset.icon));
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const initials = name => name.trim().split(/\s+/).slice(-2).map(s => s[0]).join('').toUpperCase();
const state = { user: null, teachers: [], classes: [], students: [], classId: null, view: 'attendance', filter: 'all', today: '', stream: null, loading: false, rosterRequest: 0, recognizing: false, sessions: [], sessionId: null, sessionKey: '' };
let toastTimer;
function toast(message) { $('#toast').textContent = message; $('#toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').hidden = true, 4500); }
function errorBanner(message = '') { $('#global-error').textContent = message; $('#global-error').hidden = !message; }
async function api(path, options = {}) {
  let response;
  try { response = await fetch('/api' + path, {...options, headers: {...options.headers, 'X-Requested-With':'attendance-web'}}); }
  catch { throw new Error('Không kết nối được máy chủ. Hãy kiểm tra backend đang chạy và tải lại trang.'); }
  const data = await response.json().catch(() => ({}));
  if (response.status === 401 && !path.startsWith('/auth/')) showLogin();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Dữ liệu chưa hợp lệ hoặc máy chủ gặp lỗi. Vui lòng thử lại.');
  return data;
}
function currentClass() { return state.classes.find(c => c.id === state.classId); }
function selectedDay() { return state.view === 'history' ? $('#history-date').value || state.today : state.today; }
function formatDate(value, options = {}) { return new Date(value + 'T12:00:00+07:00').toLocaleDateString('vi-VN', { day:'2-digit', month:'2-digit', year:'numeric', ...options }); }
async function loadClasses(preferredId = state.classId) {
  const data = await api('/classes');
  state.classes = data.classes; state.today = data.today;
  state.classId = data.classes.some(c => c.id === preferredId) ? preferredId : data.classes[0]?.id ?? null;
  $('#class-select').innerHTML = data.classes.length ? data.classes.map(c => `<option value="${c.id}">${escapeHTML(c.name)}</option>`).join('') : '<option value="">Chưa có lớp môn học</option>';
  $('#class-select').value = state.classId ?? '';
  $('#class-select').disabled = !data.classes.length;
  $('#history-date').removeAttribute('max');
  if (!$('#history-date').value) $('#history-date').value = data.today;
  $('#current-date').textContent = formatDate(data.today, { weekday:'long' });
  $('#session-date').textContent = formatDate(data.today, { weekday:'long' });
  $('#connection').textContent = 'Máy chủ đã kết nối'; $('#connection').classList.remove('offline');
  renderClass(); renderClasses();
  if (state.view === 'calendar') await loadTeachingCalendar();
  else if (state.view === 'dashboard') await loadDashboard();
  else await loadRoster();
}
function renderClass() {
  const cls = currentClass();
  $('#new-student').disabled = !cls;
  $('#class-info').innerHTML = cls ? `<span class="teacher-label">GIẢNG VIÊN PHỤ TRÁCH</span><strong class="teacher-name">${escapeHTML(cls.teacher || 'Chưa thêm giảng viên')}</strong><span class="class-subject">${escapeHTML(cls.subject)}</span>` : 'Chưa có lớp môn học';
  $('#session-class').textContent = cls?.name || 'Chưa chọn lớp';
  $('#session-subject').textContent = cls?.subject || (cls ? 'Điểm danh hằng ngày' : 'Tạo lớp để bắt đầu điểm danh');
  $('#camera-toggle').disabled = !cls || !currentSession()?.can_attend || state.recognizing;
  $('#new-session').disabled = !cls || state.recognizing;
  $('#manage-schedules').disabled = !cls || state.recognizing;
  $('#export').disabled = !cls;
}
async function loadRoster() {
  const request = ++state.rosterRequest;
  state.students = []; state.loading = true; renderRoster(); renderStats();
  $('#camera-toggle').disabled = true; $('#capture').disabled = true; $('#session-select').disabled = true;
  try {
    await loadSessions(request);
    if (request !== state.rosterRequest) return;
    const data = state.classId ? await api(`/classes/${state.classId}/roster?${rosterQuery()}`) : {students:[]};
    if (request !== state.rosterRequest) return;
    state.students = data.students; state.loading = false; errorBanner();
    renderStats(); renderRoster(); renderRecent();
  } catch (error) { if (request === state.rosterRequest) { state.loading = false; errorBanner(error.message); $('#roster-body').innerHTML = '<tr><td colspan="6" class="empty-cell">Không tải được danh sách. Hãy tải lại trang để thử lại.</td></tr>'; } }
}
function renderStats() {
  const total = state.students.length, present = state.students.filter(s => s.time).length, rate = total ? Math.round(present / total * 100) : 0;
  $('#stat-total').innerHTML = `${total}<small>sinh viên</small>`;
  $('#stat-present').innerHTML = `${present}<small>sinh viên</small>`;
  $('#stat-pending').innerHTML = `${total - present}<small>sinh viên</small>`;
  $('#stat-rate').innerHTML = `${rate}<small>%</small>`;
  $('#progress-bar').style.width = rate + '%';
  $('#roster-count').textContent = total;
}
function renderRecent() {
  const recent = state.students.filter(s => s.time).sort((a,b) => b.time.localeCompare(a.time));
  $('#recent-count').textContent = recent.length;
  $('#recent-list').innerHTML = recent.length ? recent.slice(0,5).map(s => `<div class="recent-item"><div class="avatar">${escapeHTML(initials(s.name))}</div><div><strong>${escapeHTML(s.name)}</strong><small>${escapeHTML(s.code)} · ${s.method === 'face' ? 'Khuôn mặt' : 'Thủ công'}</small></div><time>${s.time.slice(0,5)}</time></div>`).join('') : '<div class="recent-empty">Chưa có lượt điểm danh.</div>';
}
function renderRoster() {
  if (state.loading) { $('#roster-body').innerHTML = '<tr><td colspan="6" class="empty-cell">Đang tải danh sách…</td></tr>'; return; }
  const search = $('#search').value.trim().toLocaleLowerCase('vi');
  const students = state.students.filter(s => (s.name + ' ' + s.code).toLocaleLowerCase('vi').includes(search) && (state.filter === 'all' || (state.filter === 'present' ? s.time : !s.time)));
  if (!students.length) {
    const empty = !state.students.length, noClass = !state.classId;
    const hint = noClass ? 'Vào mục Lớp môn học để tạo lớp trước khi sử dụng.' : !empty ? 'Thử thay đổi từ khóa hoặc bộ lọc trạng thái.' : state.view === 'history' ? 'Không có sinh viên được đăng ký vào ngày đã chọn.' : state.view === 'students' ? 'Thêm sinh viên cùng ảnh khuôn mặt để sẵn sàng cho buổi học.' : 'Lớp chưa có sinh viên. Bạn có thể đăng ký sinh viên trong mục Sinh viên.';
    $('#roster-body').innerHTML = `<tr><td colspan="6" class="empty-cell"><div class="empty-icon">${icon(empty ? 'users' : 'search')}</div><h3>${noClass ? 'Chưa có lớp môn học' : empty ? 'Chưa có sinh viên trong danh sách' : 'Không tìm thấy sinh viên phù hợp'}</h3><p>${hint}</p>${empty && !noClass && state.view === 'students' && isAdmin() ? `<button class="button primary" data-empty-action="student">${icon('plus')}Thêm sinh viên</button>` : ''}</td></tr>`;
  } else {
    $('#roster-body').innerHTML = students.map(s => `<tr><td><div class="student-cell"><div class="avatar">${escapeHTML(initials(s.name))}</div><div><strong>${escapeHTML(s.name)}</strong><small>${s.photo_count} ảnh đã đăng ký</small></div></div></td><td>${escapeHTML(s.code)}</td><td><span class="status-pill ${s.time ? 'present' : ''}">${s.time ? 'Có mặt' : 'Chưa điểm danh'}</span></td><td>${s.time || '—'}</td><td>${s.method === 'face' ? 'Khuôn mặt AI' : s.method === 'manual' ? 'Thủ công' : '—'}</td><td></td></tr>`).join('');
  }
  $('#table-summary').textContent = `Hiển thị ${students.length} / ${state.students.length} sinh viên`;
}
function renderClasses() {
  $('#class-cards').innerHTML = state.classes.length ? state.classes.map(c => `<article class="class-card"><span class="class-symbol">${icon('grid')}</span><h3>${escapeHTML(c.name)}</h3><p>${escapeHTML(c.subject || 'Lớp môn học của bạn')}</p><div class="class-teacher"><span class="teacher-label">GIẢNG VIÊN PHỤ TRÁCH</span><strong class="teacher-name">${escapeHTML(c.teacher || 'Chưa thêm giảng viên')}</strong></div><div class="card-bottom"><span>${c.student_count} sinh viên</span>${isAdmin() ? `<button class="button subtle" data-edit-course="${c.id}">Sửa lớp</button>` : ''}<button class="button subtle" data-select-class="${c.id}">Mở lớp →</button></div></article>`).join('') : '<article class="class-card"><span class="class-symbol">'+icon('plus')+'</span><h3>Chưa có lớp môn học</h3><p>Tạo lớp để thêm sinh viên.</p>'+(isAdmin() ? '<button class="button primary" data-empty-action="class">Tạo lớp</button>' : '<p>Admin sẽ phân công lớp môn học cho bạn.</p>')+'</article>';
}
const viewLabels = {
  calendar: ['Lịch dạy', 'Lịch dạy', 'Theo dõi buổi học theo ngày và tuần.'],
  dashboard: ['Tổng quan', 'Tổng quan', 'Thống kê điểm danh hôm nay.'],
  attendance: ['Điểm danh', 'Điểm danh', 'Chọn buổi học và bật camera.'],
  students: ['Sinh viên', 'Sinh viên', 'Quản lý hồ sơ và khuôn mặt.'],
  classes: ['Lớp môn học', 'Lớp môn học', 'Tạo và chọn lớp cần quản lý.'],
  history: ['Lịch sử', 'Lịch sử điểm danh', 'Tra cứu theo ngày hoặc buổi học.']
};
function switchView(view) {
  if (view === 'students' && !isAdmin()) return;
  if (state.recognizing) return toast('Chờ nhận diện hoàn tất trước khi chuyển trang.');
  state.view = view; state.filter = 'all'; $('#search').value = '';
  if (view !== 'attendance') stopCamera();
  $$('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.view === view));
  $$('.tabs button').forEach(el => el.classList.toggle('selected', el.dataset.filter === 'all'));
  const [label,title,description] = viewLabels[view];
  $('#breadcrumb').textContent = label; $('#page-title').textContent = title; $('#page-description').textContent = description;
  $('#attendance-view').hidden = view !== 'attendance'; $('#classes-view').hidden = view !== 'classes';
  $('#dashboard-view').hidden = view !== 'dashboard';
  $('#session-toolbar').hidden = !['attendance','history'].includes(view);
  $('#calendar-view').hidden = view !== 'calendar';
  const overview = ['classes','dashboard','calendar'].includes(view);
  $('#roster-panel').hidden = overview; $('#stats').hidden = overview;
  $('#class-toolbar').hidden = overview;
  if (view === 'dashboard') { state.rosterRequest++; loadDashboard(); return; }
  if (view === 'calendar') { state.rosterRequest++; loadTeachingCalendar(); return; }
  $('#new-student').hidden = view !== 'students' || !isAdmin();
  $('#enroll-existing').hidden = view !== 'students' || !isAdmin();
  $('#bulk-open').hidden = view !== 'students' || !isAdmin();
  $('#history-date').hidden = view !== 'history';
  $('#roster-title').innerHTML = `${view === 'students' ? 'Sinh viên trong lớp' : view === 'history' ? 'Lịch sử theo ngày' : 'Danh sách điểm danh'} <span id="roster-count" class="count-badge">0</span>`;
  $('#roster-subtitle').textContent = view === 'history' ? 'Chọn ngày để xem kết quả đã lưu của lớp.' : 'Kết quả của lớp đang chọn.';
  return loadRoster();
}
function openDialog(kind) {
  if (['student','class','enrollment','session','schedules'].includes(kind) && !isAdmin()) return toast('Chỉ admin được thực hiện thao tác này.');
  if (kind === 'student' && !state.classId) return toast('Hãy tạo lớp môn học trước.');
  const dialog = $(`#${kind}-dialog`);
  if (kind === 'class') {
    $('#class-form').dataset.editId = '';
    $('#class-dialog-title').textContent = 'Tạo lớp môn học';
    $('#class-owner').innerHTML = state.teachers.map(t => `<option value="${t.id}">${escapeHTML(t.name)}</option>`).join('');
  } dialog.querySelector('form').reset(); dialog.querySelector('.form-error').textContent = '';
  if (kind === 'student') {
    stopCamera(); resetEnrollment();
    $('#student-class-label').textContent = `Đăng ký vào lớp ${currentClass().name}`;
  }
  dialog.showModal();
}
function lockForm(form, busy) {
  form.dataset.busy = String(busy);
  [...form.querySelectorAll('button,input')].forEach(el => el.disabled = busy);
}
$('#class-form').addEventListener('submit', async event => {
  event.preventDefault(); const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form)); lockForm(form, true);
  form.querySelector('.form-error').textContent = '';
  try { const created = await api(form.dataset.editId ? `/classes/${form.dataset.editId}` : '/classes', {method:form.dataset.editId ? 'PATCH' : 'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}); await loadClasses(created.id); $('#class-dialog').close(); toast('Đã lưu lớp môn học.'); }
  catch(error) { form.querySelector('.form-error').textContent = error.message; }
  finally { lockForm(form, false); }
});
$('#student-form').addEventListener('submit', async event => {
  event.preventDefault(); const form = event.currentTarget, data = new FormData(form);
  const files = enrollment.mode === 'camera' ? (enrollment.photo ? [enrollment.photo] : []) : data.getAll('images').filter(file => file.size > 0);
  if (!files.length || files.length > 5 || files.some(file => file.size > 10*1024*1024)) { form.querySelector('.form-error').textContent = enrollment.mode === 'camera' ? 'Hãy bật camera và chụp ảnh trước khi đăng ký.' : 'Chọn 1–5 ảnh hợp lệ, mỗi ảnh tối đa 10 MB.'; return; }
  data.delete('images');
  data.set('use_guide', String(enrollment.mode === 'camera'));
  files.forEach(file => data.append('images', file, file.name || 'webcam.jpg'));
  stopEnrollmentCamera();
  data.append('class_id', state.classId); lockForm(form, true);
  const button = form.querySelector('[type=submit]'); button.textContent = 'Đang xử lý khuôn mặt…'; form.querySelector('.form-error').textContent = '';
  try { const student = await api('/students', {method:'POST', body:data}); await loadClasses(); $('#student-dialog').close(); toast(`Đã thêm ${student.name} và đăng ký khuôn mặt.`); }
  catch(error) { form.querySelector('.form-error').textContent = error.message; }
  finally { lockForm(form, false); button.textContent = 'Lưu sinh viên'; }
});
$$('dialog').forEach(dialog => { dialog.addEventListener('cancel', e => { if (dialog.querySelector('form').dataset.busy === 'true') e.preventDefault(); }); });
$$('.close-dialog').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
$('#new-class').onclick = () => openDialog('class'); $('#new-student').onclick = () => openDialog('student');
$$('.nav-item').forEach(button => button.onclick = () => switchView(button.dataset.view));
$('#class-select').onchange = async event => { state.classId = Number(event.target.value); stopCamera(); renderClass(); resultMessage('Bật camera để điểm danh.'); await loadRoster(); };
$('#history-date').onchange = () => { state.sessionKey = ''; loadRoster(); };
$('#search').oninput = renderRoster;
$$('.tabs button').forEach(button => button.onclick = () => { state.filter = button.dataset.filter; $$('.tabs button').forEach(el => el.classList.toggle('selected', el === button)); renderRoster(); });
document.addEventListener('click', async event => {
  const empty = event.target.closest('[data-empty-action]'); if (empty) openDialog(empty.dataset.emptyAction);
  const selection = event.target.closest('[data-select-class]');
  if (selection) { state.classId = Number(selection.dataset.selectClass); $('#class-select').value = state.classId; renderClass(); switchView('students'); }

});
$('#export').onclick = () => { if (state.classId) window.location.href = `/api/classes/${state.classId}/export?${rosterQuery()}`; };
function resultMessage(message, type = '') { const el = $('#recognition-result'); el.className = 'recognition-result ' + type; el.textContent = message; }
function stopCamera() {
  state.stream?.getTracks().forEach(track => track.stop()); state.stream = null;
  const video = $('#camera'); video.srcObject = null; video.hidden = true;
  $('#camera-empty').hidden = false; $('#camera-corners').hidden = true; $('#capture').hidden = true;
  $('#camera-toggle').innerHTML = icon('camera') + 'Bật camera'; $('#camera-status').textContent = 'CAMERA CHƯA BẬT';
}
$('#camera-toggle').onclick = async () => {
  if (state.stream) { stopCamera(); return; }
  $('#camera-toggle').disabled = true;
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('Trình duyệt này chưa hỗ trợ camera. Hãy dùng Chrome/Edge tại localhost để mở camera.');
    const stream = await navigator.mediaDevices.getUserMedia({video:{facingMode:'user', width:{ideal:1280}, height:{ideal:720}}, audio:false});
    if (state.view !== 'attendance') { stream.getTracks().forEach(track => track.stop()); return; }
    state.stream = stream; $('#camera').srcObject = stream; await $('#camera').play(); $('#camera').hidden = false;
    $('#camera-empty').hidden = true; $('#camera-corners').hidden = false; $('#capture').hidden = false;
    $('#camera-toggle').innerHTML = icon('camera') + 'Tắt camera'; $('#camera-status').textContent = 'CAMERA ĐANG BẬT';
    resultMessage('Đặt toàn bộ khuôn mặt trong vòng, sau đó bấm Chụp & điểm danh.');
  } catch(error) { stopCamera(); resultMessage(error.name === 'NotAllowedError' ? 'Bạn chưa cho phép camera. Hãy cấp quyền camera trên trình duyệt để điểm danh.' : error.name === 'NotFoundError' ? 'Không tìm thấy webcam. Hãy kết nối camera để điểm danh.' : error.name === 'NotReadableError' ? 'Camera đang được ứng dụng khác sử dụng. Hãy đóng ứng dụng đó và thử lại.' : error.message, 'error'); }
  finally { $('#camera-toggle').disabled = !state.classId; }
};
async function recognize(file) {
  if (!file || state.recognizing) return;
  if (!currentSession()?.can_attend) return resultMessage('Hãy chọn buổi đang mở và trong khung giờ để điểm danh.', 'error');
  if (file.size > 10*1024*1024) return resultMessage('Ảnh vượt quá 10 MB. Hãy chọn ảnh nhỏ hơn.', 'error');
  state.recognizing = true;
  const classId = state.classId, sessionId = state.sessionId;
  ['#capture','#camera-toggle','#class-select','#session-select','#toggle-session','#new-session','#refresh-sessions'].forEach(s => $(s).disabled = true);
  resultMessage('Đang nhận diện khuôn mặt, vui lòng chờ…');
  const data = new FormData(); data.append('image', file, file.name || 'camera.jpg');
  try {
    const result = await api(`/classes/${classId}/recognize?session_id=${sessionId}`, {method:'POST', body:data});
    if (result.status === 'unknown') resultMessage(result.message, 'error');
    else { resultMessage(`${result.student.name} · ${result.student.code} — ${result.status === 'duplicate' ? 'Đã điểm danh buổi này lúc' : 'Có mặt lúc'} ${result.time}`, 'success'); await loadRoster(); }
  } catch(error) { resultMessage(error.message, 'error'); }
  finally { state.recognizing = false; ['#capture','#camera-toggle','#class-select','#session-select','#toggle-session','#new-session','#refresh-sessions'].forEach(s => $(s).disabled = false); renderClass(); renderSession(); }
}
// Match the centered object-fit: cover preview, including its cropped edges.
function attendanceCrop(videoWidth, videoHeight, viewWidth, viewHeight) {
  const scale = Math.max(viewWidth / videoWidth, viewHeight / videoHeight);
  const width = viewWidth / scale, height = viewHeight / scale;
  return { x: (videoWidth - width) / 2, y: (videoHeight - height) / 2, width, height };
}
$('#capture').onclick = () => {
  const video = $('#camera');
  if (!video.videoWidth || video.readyState < 2) return resultMessage('Camera chưa sẵn sàng. Vui lòng thử lại.', 'error');
  const bounds = video.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  const crop = attendanceCrop(video.videoWidth, video.videoHeight, bounds.width, bounds.height);
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(crop.width); canvas.height = Math.round(crop.height);
  canvas.getContext('2d').drawImage(video, crop.x, crop.y, crop.width, crop.height, 0, 0, canvas.width, canvas.height);
  // Preview is mirrored; the centered ellipse is symmetric so its region is unchanged.
  canvas.toBlob(blob => recognize(blob), 'image/jpeg', .9);
};
const enrollment = { mode: 'camera', stream: null, photo: null, url: null, request: 0 };
function stopEnrollmentCamera() {
  enrollment.request++;
  enrollment.stream?.getTracks().forEach(track => track.stop());
  enrollment.stream = null;
  $('#enroll-video').srcObject = null;
  $('#enroll-video').hidden = true;
  $('#enroll-guide').hidden = true;
  $('#enroll-capture').hidden = true;
}
function resetEnrollment() {
  stopEnrollmentCamera();
  if (enrollment.url) URL.revokeObjectURL(enrollment.url);
  enrollment.photo = null; enrollment.url = null;
  $('#enroll-preview').removeAttribute('src'); $('#enroll-preview').hidden = true;
  $('#enroll-placeholder').hidden = false; $('#enroll-retake').hidden = true;
  $('#enroll-camera-start').hidden = false; $('#enroll-camera-start').disabled = false;
  $('#enroll-capture').disabled = false;
  $('#enroll-status').textContent = 'Đặt một khuôn mặt trong oval. Người ngoài oval được bỏ qua.';
  setEnrollmentMode('camera');
}
function setEnrollmentMode(mode) {
  stopEnrollmentCamera(); enrollment.mode = mode;
  $('#enroll-camera-section').hidden = mode !== 'camera';
  $('#enroll-upload-section').hidden = mode !== 'upload';
  $('#enroll-camera-start').hidden = !!enrollment.photo;
  $('#enroll-placeholder').hidden = !!enrollment.photo;
  $('#student-form .form-error').textContent = '';
  ['camera','upload'].forEach(value => {
    const button = $(`#enroll-mode-${value}`);
    button.className = 'button ' + (mode === value ? 'primary' : 'subtle');
    button.setAttribute('aria-pressed', String(mode === value));
  });
}
async function startEnrollmentCamera() {
  stopEnrollmentCamera(); const request = enrollment.request;
  $('#enroll-camera-start').disabled = true; $('#enroll-retake').disabled = true;
  $('#enroll-status').textContent = 'Đang mở camera…';
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('Hãy mở trang bằng Chrome/Edge tại localhost để dùng camera, hoặc chọn tải ảnh.');
    const stream = await navigator.mediaDevices.getUserMedia({video:{facingMode:'user', width:{ideal:1280},height:{ideal:720}},audio:false});
    if (request !== enrollment.request || !$('#student-dialog').open || enrollment.mode !== 'camera') { stream.getTracks().forEach(track => track.stop()); return; }
    enrollment.stream = stream;
    const video = $('#enroll-video'); video.srcObject = stream;
    await video.play();
    if (request !== enrollment.request) return;
    video.hidden = false; $('#enroll-preview').hidden = true;
    $('#enroll-guide').hidden = false;
    $('#enroll-placeholder').hidden = true; $('#enroll-camera-start').hidden = true;
    $('#enroll-retake').hidden = true; $('#enroll-capture').hidden = false;
    // A retake replaces the previous selection only after the camera opens.
    enrollment.photo = null;
    if (enrollment.url) URL.revokeObjectURL(enrollment.url);
    enrollment.url = null; $('#enroll-preview').removeAttribute('src');
    $('#enroll-status').textContent = 'Đặt một khuôn mặt trong oval rồi bấm Chụp ảnh. Người ngoài oval được bỏ qua.';
  } catch(error) {
    if (request !== enrollment.request) return;
    stopEnrollmentCamera();
    $('#enroll-status').textContent = error.name === 'NotAllowedError' ? 'Chưa có quyền camera. Hãy cho phép camera trên trình duyệt hoặc chọn tải ảnh.' : error.name === 'NotFoundError' ? 'Không tìm thấy webcam. Bạn có thể chọn tải ảnh có sẵn.' : error.name === 'NotReadableError' ? 'Camera đang bận. Hãy đóng ứng dụng khác dùng camera và thử lại.' : error.message;
  } finally {
    if ($('#student-form').dataset.busy !== 'true') { $('#enroll-camera-start').disabled = false; $('#enroll-retake').disabled = false; }
  }
}
$('#enroll-mode-camera').onclick = () => setEnrollmentMode('camera');
$('#enroll-mode-upload').onclick = () => setEnrollmentMode('upload');
$('#enroll-camera-start').onclick = startEnrollmentCamera;
$('#enroll-retake').onclick = startEnrollmentCamera;
$('#enroll-capture').onclick = () => {
  const video = $('#enroll-video');
  if (!video.videoWidth || video.readyState < 2) { $('#enroll-status').textContent = 'Camera chưa sẵn sàng. Vui lòng thử lại.'; return; }
  const request = enrollment.request;
  const bounds = video.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  const crop = attendanceCrop(video.videoWidth, video.videoHeight, bounds.width, bounds.height);
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(crop.width); canvas.height = Math.round(crop.height);
  canvas.getContext('2d').drawImage(video, crop.x, crop.y, crop.width, crop.height, 0, 0, canvas.width, canvas.height);
  $('#enroll-capture').disabled = true;
  canvas.toBlob(blob => {
    $('#enroll-capture').disabled = false;
    if (request !== enrollment.request || !$('#student-dialog').open) return;
    if (!blob) { $('#enroll-status').textContent = 'Chưa chụp được ảnh. Vui lòng thử lại.'; return; }
    enrollment.photo = blob; enrollment.url = URL.createObjectURL(blob);
    $('#enroll-preview').src = enrollment.url; $('#enroll-preview').hidden = false;
    $('#enroll-retake').hidden = false;
    $('#enroll-status').textContent = 'Đã chụp ảnh. Kiểm tra ảnh rồi bấm Lưu sinh viên, hoặc Chụp lại.';
    stopEnrollmentCamera();
    $('#student-form .form-error').textContent = '';
  }, 'image/jpeg', .92);
};
$('#student-dialog').addEventListener('close', resetEnrollment);
window.addEventListener('pagehide', () => { stopCamera(); resetEnrollment(); });
initializeLogin();

let dashboardRequest = 0;
async function loadDashboard() {
  const request = ++dashboardRequest;
  $('#dashboard-refresh').disabled = true;
  $('#dashboard-content').hidden = true;
  $('#dashboard-error').hidden = true;
  $('#dashboard-updated').textContent = 'Đang tải thống kê…';
  try {
    const data = await api('/dashboard');
    if (request !== dashboardRequest) return;
    $('#dash-classes').textContent = data.class_count;
    $('#dash-students').textContent = data.total;
    $('#dash-present').textContent = data.present;
    $('#dash-pending').textContent = data.pending;
    const presentRate = data.total > 0 ? Math.min(100, Math.max(0, data.present / data.total * 100)) : 0;
    const pendingRate = data.total > 0 ? Math.min(100, Math.max(0, data.pending / data.total * 100)) : 0;
    $('#dash-rate').textContent = `${Math.round(presentRate)}% có mặt`;
    $('#dash-pending-rate').textContent = `${Math.round(pendingRate)}% chưa điểm danh`;
    $('#dash-present-progress').value = presentRate;
    $('#dash-pending-progress').value = pendingRate;
    $('#dashboard-updated').textContent = `Tất cả lớp môn học · ${formatDate(data.day)} · Cập nhật ${new Date().toLocaleTimeString('vi-VN', {timeZone:'Asia/Ho_Chi_Minh'})}`;
    const peak = Math.max(1, ...data.trend.map(d => d.present));
    $('#dashboard-chart').innerHTML = data.trend.map(d => `<div class="chart-column"><strong>${d.present}</strong><div class="chart-track"><div class="chart-bar" style="height:${d.present / peak * 100}%"></div></div><span>${escapeHTML(d.day.slice(8) + '/' + d.day.slice(5,7))}</span><small>${d.total} lượt ghi danh</small></div>`).join('');
    $('#dashboard-recent').innerHTML = data.recent.length ? data.recent.map(s => `<div class="recent-item"><div class="avatar">${escapeHTML(initials(s.name))}</div><div><strong>${escapeHTML(s.name)}</strong><small>${escapeHTML(s.code)} · ${escapeHTML(s.class_name)}</small></div><time>${escapeHTML(s.time)}</time></div>`).join('') : '<p class="recent-empty">Chưa có lượt điểm danh hôm nay.</p>';
    $('#dashboard-classes').innerHTML = data.classes.length ? data.classes.map(c => `<tr><td><strong>${escapeHTML(c.name)}</strong></td><td>${escapeHTML(c.teacher || 'Chưa thêm giảng viên')}</td><td>${c.total}</td><td>${c.present}</td><td>${c.total-c.present}</td><td><div class="dashboard-meter class-meter"><span>${c.total ? Math.round(c.present/c.total*100) : 0}%</span><progress max="100" value="${c.total ? Math.min(100, Math.max(0, c.present/c.total*100)) : 0}" aria-label="Tỷ lệ có mặt của ${escapeHTML(c.name)}"></progress></div></td><td><button class="button subtle" data-dashboard-class="${c.id}">Điểm danh →</button></td></tr>`).join('') : '<tr><td colspan="7" class="empty-cell">Chưa có lớp môn học. <button class="button primary" data-empty-action="class">Tạo lớp</button></td></tr>';
    $('#dashboard-content').hidden = false;
  } catch (error) {
    if (request !== dashboardRequest) return;
    $('#dashboard-error').textContent = error.message;
    $('#dashboard-error').hidden = false;
    $('#dashboard-updated').textContent = 'Chưa tải được thống kê. Bấm Làm mới để thử lại.';
  } finally { if (request === dashboardRequest) $('#dashboard-refresh').disabled = false; }
}
$('#dashboard-refresh').onclick = loadDashboard;
document.addEventListener('click', event => {
  const button = event.target.closest('[data-dashboard-class]');
  if (!button) return;
  state.classId = Number(button.dataset.dashboardClass);
  $('#class-select').value = state.classId;
  renderClass(); switchView('attendance');
});

function currentSession() { return state.sessions.find(s => s.id === state.sessionId); }
function rosterQuery() {
  return `day=${selectedDay()}` + (['attendance','history'].includes(state.view) && state.sessionId ? `&session_id=${state.sessionId}` : '');
}
function renderSession() {
  const session = currentSession();
  $('#toggle-session').disabled = !session || state.recognizing;
  $('#toggle-session').textContent = session?.status === 'open' ? 'Đóng điểm danh' : 'Mở điểm danh';
  $('#session-select').disabled = !state.sessions.length || state.recognizing;
  $('#session-state').textContent = session ? `${session.status === 'open' ? 'Đang mở' : 'Đang đóng'} · ${session.starts_at.slice(0,5)}–${session.ends_at.slice(0,5)} · ${formatDate(session.day)}${session.status === 'open' && !session.can_attend ? ' · Ngoài khung giờ điểm danh' : ''}` : state.view === 'history' ? 'Tổng hợp ngày: tính mỗi sinh viên một lần, gồm dữ liệu cũ.' : (isAdmin() ? 'Tạo buổi học để bắt đầu điểm danh.' : 'Chưa có buổi học. Liên hệ admin để được xếp lịch.');
  $('#camera-toggle').disabled = !session?.can_attend || state.recognizing;
  $('#capture').disabled = !session?.can_attend || state.recognizing;
  $('#session-subject').textContent = session?.name || 'Chưa chọn buổi học';
  $('#session-date').textContent = formatDate(session?.day || state.today || selectedDay());
}
async function loadSessions(request) {
  if (!['attendance','history'].includes(state.view)) return;
  const key = `${state.classId}:${selectedDay()}:${state.view}`;
  const data = state.classId ? await api(`/classes/${state.classId}/sessions?day=${selectedDay()}`) : {sessions:[]};
  if (request !== state.rosterRequest) return;
  state.sessions = data.sessions;
  if (state.sessionKey !== key || (state.sessionId && !currentSession())) {
    state.sessionId = state.view === 'history' ? null : (data.sessions.find(s => s.can_attend)?.id ?? data.sessions[0]?.id ?? null);
  }
  state.sessionKey = key;
  $('#session-select').innerHTML = (state.view === 'history' ? '<option value="">Tổng hợp ngày / dữ liệu cũ</option>' : !data.sessions.length ? '<option value="">Chưa có buổi học</option>' : '') + data.sessions.map(s => `<option value="${s.id}">${escapeHTML(s.name)} · ${s.starts_at.slice(0,5)}–${s.ends_at.slice(0,5)} · ${s.status==='open'?'Mở':'Đóng'}</option>`).join('');
  $('#session-select').value = state.sessionId ?? '';
  renderSession();
}
$('#session-select').onchange = async event => { stopCamera(); state.sessionId = Number(event.target.value) || null; renderSession(); await loadRoster(); };
$('#new-session').onclick = () => {
  if (!state.classId || state.recognizing) return;
  openDialog('session');
  $('#new-session-day').value = selectedDay();
  const cls = currentClass();
  $('#session-form-class').textContent = [
    `Lớp môn học: ${cls.name}${cls.course_code ? ' · ' + cls.course_code : ''}`,
    `Giảng viên: ${cls.teacher || 'Chưa phân công'}`,
    `Phòng: ${cls.room || 'Chưa cập nhật'}`
  ].join('\n');
};
$('#session-form').addEventListener('submit', async event => {
  event.preventDefault(); const form = event.currentTarget;
  const values = new FormData(form);
  const data = Object.fromEntries(values);
  data.weekdays = values.getAll('weekdays').map(Number);
  data.ends_on = data.ends_on || null;
  if (data.ends_at <= data.starts_at) { form.querySelector('.form-error').textContent = 'Giờ kết thúc phải sau giờ bắt đầu.'; return; }
  lockForm(form, true);
  try {
    const result = await api(`/classes/${state.classId}/sessions`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    if (state.view === 'calendar') { $('#session-dialog').close(); await loadTeachingCalendar(); toast('Đã lưu lịch dạy.'); return; }
    if (result.schedule_id) { state.sessionKey = ''; await loadRoster(); $('#session-dialog').close(); toast('Đã lưu lịch cố định. Buổi được tạo vào ngày học.'); return; }
    if (data.day !== state.today || state.view === 'history') { $('#history-date').value = data.day; switchView('history'); }
    state.sessionId = result.id;
    state.sessionKey = `${state.classId}:${selectedDay()}:${state.view}`;
    await loadRoster(); $('#session-dialog').close(); toast('Đã tạo buổi học. Bấm Mở điểm danh khi sẵn sàng.');
  } catch(error) { form.querySelector('.form-error').textContent = error.message; }
  finally { lockForm(form, false); }
});
$('#toggle-session').onclick = async () => {
  const session = currentSession(); if (!session || state.recognizing) return;
  $('#toggle-session').disabled = true;
  try {
    await api(`/classes/${state.classId}/sessions/${session.id}`, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:session.status==='open'?'closed':'open'})});
    stopCamera(); await loadRoster();
  } catch(error) { toast(error.message); }
  finally { renderSession(); }
};

$('#refresh-sessions').onclick = () => { if (!state.recognizing) { stopCamera(); loadClasses().catch(error => toast(error.message)); } };

async function showSchedules() {
  const data = await api(`/classes/${state.classId}/schedules`);
  $('#schedules-list').innerHTML = data.schedules.length ? data.schedules.map(s => `<div class="schedule-item"><strong>${escapeHTML(s.name)}</strong><p>${s.weekdays.map(d=>['T2','T3','T4','T5','T6','T7','CN'][d]).join(', ')} · ${s.starts_at.slice(0,5)}–${s.ends_at.slice(0,5)}</p><p>Từ ${formatDate(s.starts_on)}${s.ends_on ? ' đến '+formatDate(s.ends_on) : ''}</p><button type="button" class="button subtle" data-stop-schedule="${s.id}">Dừng lịch</button></div>`).join('') : '<p>Chưa có lịch cố định. Chọn Tạo buổi học để thêm lịch.</p>';
}
$('#manage-schedules').onclick = async () => {
  if (!state.classId || state.recognizing) return;
  openDialog('schedules');
  $('#schedules-list').textContent = 'Đang tải…';
  try { await showSchedules(); } catch(error) { $('#schedules-dialog .form-error').textContent = error.message; }
};
$('#schedules-list').onclick = async event => {
  const button = event.target.closest('[data-stop-schedule]'); if (!button) return;
  button.disabled = true;
  try { await api(`/classes/${state.classId}/schedules/${button.dataset.stopSchedule}`, {method:'DELETE'}); await showSchedules(); toast('Đã dừng lịch. Các buổi đã tạo vẫn được giữ.'); }
  catch(error) { $('#schedules-dialog .form-error').textContent = error.message; button.disabled = false; }
};

function showLogin() {
  stopCamera(); stopEnrollmentCamera();
  state.rosterRequest++; dashboardRequest++;
  state.user = null; state.teachers = []; state.classes = []; state.students = []; state.classId = null;
  state.sessions = []; state.sessionId = null; state.sessionKey = '';
  $$('.sidebar, .app-shell').forEach(el => el.hidden = true);
  $$('dialog[open]').forEach(dialog => dialog.close());
  $('#login-screen').hidden = false;
}
function isAdmin() { return state.user?.role === 'admin'; }
async function enterAccount(user) {
  state.user = user;
  $('#workspace-role').textContent = isAdmin() ? 'Quản trị lớp môn học' : 'Quản lý điểm danh';
  $$('[data-admin-only]').forEach(el => el.hidden = !isAdmin());
  if (isAdmin()) state.teachers = (await api('/teachers')).teachers;
  $('#teacher-account-name').textContent = user.name;
  $('#teacher-account-username').textContent = `${user.role === 'admin' ? 'Admin' : 'Giảng viên'} · ${user.username}`;
  $('#login-screen').hidden = true;
  $$('.sidebar, .app-shell').forEach(el => el.hidden = false);
  await loadClasses();
}
async function initializeLogin() {
  try { await enterAccount(await api('/auth/me')); }
  catch { showLogin(); }
}
$('#login-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget, button = form.querySelector('button[type="submit"]');
  button.disabled = true; $('#login-error').textContent = '';
  try {
    const user = await api('/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(Object.fromEntries(new FormData(form)))});
    form.reset(); await enterAccount(user);
  } catch(error) { $('#login-error').textContent = error.message; }
  finally { button.disabled = false; }
});
$('#logout').onclick = async () => {
  try { await api('/auth/logout', {method:'POST'}); window.location.reload(); }
  catch(error) { toast(error.message); }
};

let directoryStudents = [];
function renderDirectoryOptions() {
  const query = $('#directory-search').value.trim().toLocaleLowerCase('vi');
  const candidates = directoryStudents.filter(s => !state.students.some(member=>member.id===s.id) && `${s.name} ${s.code}`.toLocaleLowerCase('vi').includes(query));
  $('#directory-student').innerHTML = candidates.length ? candidates.map(s=>`<option value="${s.id}">${escapeHTML(s.code)} · ${escapeHTML(s.name)}</option>`).join('') : '<option value="">Không có sinh viên phù hợp</option>';
}
$('#enroll-existing').onclick = async () => {
  if (!state.classId || !isAdmin()) return;
  openDialog('enrollment');
  $('#enrollment-course').textContent = currentClass().name;
  $('#directory-student').innerHTML = '<option value="">Đang tải…</option>';
  try { directoryStudents = (await api('/students')).students; renderDirectoryOptions(); }
  catch(error) { $('#enrollment-form .form-error').textContent = error.message; }
};
$('#directory-search').oninput = renderDirectoryOptions;
$('#enrollment-form').addEventListener('submit', async event => {
  event.preventDefault(); const form=event.currentTarget; lockForm(form,true);
  try {
    await api(`/classes/${state.classId}/enrollments`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({student_id:Number($('#directory-student').value)})});
    $('#enrollment-dialog').close(); await loadClasses(); toast('Đã ghi danh sinh viên vào lớp môn học.');
  } catch(error) { form.querySelector('.form-error').textContent=error.message; }
  finally { lockForm(form,false); }
});
document.addEventListener('click', event => {
  const button=event.target.closest('[data-edit-course]');
  if (!button || !isAdmin()) return;
  const course=state.classes.find(c=>c.id===Number(button.dataset.editCourse));
  openDialog('class'); const form=$('#class-form'); form.dataset.editId=course.id;
  $('#class-dialog-title').textContent='Sửa lớp môn học';
  form.elements.name.value=course.name; form.elements.subject.value=course.subject;
  form.elements.course_code.value=course.course_code || ''; form.elements.room.value=course.room || '';
  form.elements.owner_id.value=course.owner_id;
});

let calendarRequest = 0;
function shiftCalendarDate(delta) {
  const date = new Date(($('#calendar-date').value || state.today) + 'T12:00:00+07:00');
  date.setUTCDate(date.getUTCDate() + delta);
  $('#calendar-date').value = date.toISOString().slice(0,10);
  loadTeachingCalendar();
}
async function loadTeachingCalendar() {
  const request = ++calendarRequest;
  if (!$('#calendar-date').value) $('#calendar-date').value = state.today;
  const day = $('#calendar-date').value;
  if (!day) return;
  const selectedTeacher = $('#calendar-teacher').value;
  $('#calendar-teacher').innerHTML = '<option value="">Tất cả giảng viên</option>' + state.teachers.map(t=>`<option value="${t.id}">${escapeHTML(t.name)}</option>`).join('');
  $('#calendar-teacher').value = selectedTeacher;
  const selectedCourse = $('#calendar-course').value;
  $('#calendar-course').innerHTML = state.classes.map(c=>`<option value="${c.id}">${escapeHTML(c.name)}</option>`).join('');
  if (state.classes.some(c=>String(c.id)===selectedCourse)) $('#calendar-course').value = selectedCourse;
  $('#calendar-create').disabled = !state.classes.length;
  $('#calendar-error').hidden = true;
  $('#calendar-caption').textContent = 'Đang tải lịch dạy…';
  $('#calendar-grid').innerHTML = '';
  try {
    const filter = isAdmin() && selectedTeacher ? `&teacher_id=${encodeURIComponent(selectedTeacher)}` : '';
    const data = await api(`/teaching-calendar?day=${day}&view=${$('#calendar-mode').value}${filter}`);
    if (request !== calendarRequest || state.view !== 'calendar') return;
    const periods = [['Sáng',0,12],['Chiều',12,18],['Tối',18,24]];
    const eventCard = event => `<article class="lesson-card ${event.planned?'planned':''} ${event.status==='open'?'is-open':''} ${event.conflict?'has-conflict':''}"><strong>${escapeHTML(event.subject || event.class_name)}</strong><span>Phòng: ${escapeHTML(event.room || 'Chưa xếp phòng')}</span><span>${event.starts_at.slice(0,5)}–${event.ends_at.slice(0,5)}</span><span>${escapeHTML(event.teacher_name || 'Chưa phân công')}</span><small>${escapeHTML(event.name)}</small><small>${event.planned?'Lịch cố định':event.status==='open'?'Đang mở điểm danh':'Buổi đã tạo'}</small>${event.conflict?'<b class="conflict-label">Trùng giờ giảng viên</b>':''}${event.day===data.today?`<button class="button subtle" data-calendar-attend="${event.class_id}" data-lesson-name="${escapeHTML(event.name)}">Điểm danh</button>`:''}</article>`;
    $('#calendar-grid').innerHTML = `<table class="teaching-calendar ${data.days.length===1?'day-calendar':''}"><thead><tr><th scope="col">Ca học</th>${data.days.map(d=>`<th scope="col" class="${d===data.today?'calendar-current':''}">${escapeHTML(formatDate(d,{weekday:'short'}))}</th>`).join('')}</tr></thead><tbody>${periods.map(([label,start,end])=>`<tr><th scope="row">${label}</th>${data.days.map(d=>{const lessons=data.events.filter(e=>e.day===d && Number(e.starts_at.slice(0,2))<end && Number(e.ends_at.slice(0,2))+Number(e.ends_at.slice(3,5))/60>start);return `<td class="${d===data.today?'calendar-current':''}">${lessons.length?lessons.map(eventCard).join(''):'<span class="calendar-empty">—</span>'}</td>`;}).join('')}</tr>`).join('')}</tbody></table>`;
    $('#calendar-caption').textContent = `${data.events.length} buổi · ${formatDate(data.days[0])}${data.days.length>1?' – '+formatDate(data.days.at(-1)):''}${data.events.length?'':' · Chưa có lịch dạy trong khoảng này.'}`;
  } catch(error) {
    if (request !== calendarRequest) return;
    $('#calendar-caption').textContent = 'Chưa tải được lịch dạy.';
    $('#calendar-error').textContent = error.message; $('#calendar-error').hidden = false;
  }
}
$('#calendar-prev').onclick=()=>shiftCalendarDate($('#calendar-mode').value==='week'?-7:-1);
$('#calendar-next').onclick=()=>shiftCalendarDate($('#calendar-mode').value==='week'?7:1);
$('#calendar-today').onclick=()=>{ $('#calendar-date').value=state.today; loadTeachingCalendar(); };
['#calendar-date','#calendar-mode','#calendar-teacher'].forEach(selector=>$(selector).onchange=loadTeachingCalendar);
$('#calendar-refresh').onclick=loadTeachingCalendar;
$('#calendar-create').onclick=()=>{
  if (!isAdmin()) return;
  state.classId=Number($('#calendar-course').value); renderClass();
  $('#new-session').onclick();
  $('#new-session-day').value=$('#calendar-date').value;
};
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-calendar-attend]');
  if (!button) return;
  state.classId=Number(button.dataset.calendarAttend); state.sessionKey='';
  $('#class-select').value=state.classId; renderClass(); await switchView('attendance');
  const lesson=state.sessions.find(s=>s.name===button.dataset.lessonName);
  if (lesson) { state.sessionId=lesson.id; $('#session-select').value=lesson.id; await loadRoster(); }
});

let bulkJob=null, bulkBusy=false;
function renderBulk(job) {
  bulkJob=job; $('#bulk-progress').max=job.total; $('#bulk-progress').value=job.cursor;
  $('#bulk-rows').innerHTML=job.rows.map(r=>{const d=r.data; return `<tr><td>${r.line}</td><td>${escapeHTML(d.ma_sinh_vien)}<br>${escapeHTML(d.ho_ten)}</td><td>${escapeHTML(d.ma_lop_mon_hoc)}<br>${escapeHTML(d.tai_khoan_giang_vien)}</td><td>Thứ ${escapeHTML(d.thu)} · ${escapeHTML(d.gio_bat_dau)}–${escapeHTML(d.gio_ket_thuc)}<br>Phòng ${escapeHTML(d.phong)}</td><td>${escapeHTML(r.message)}</td></tr>`;}).join('');
  $('#bulk-status').textContent=`Đã xử lý ${job.cursor}/${job.total} · Thành công: ${job.rows.filter(r=>r.status==='success').length} · Bỏ qua: ${job.rows.filter(r=>r.status==='skipped').length} · Lỗi: ${job.rows.filter(r=>r.status==='error').length}`;
  $('#bulk-confirm').disabled=job.done || bulkBusy || !job.rows.some(r=>r.status==='ready');
}
$('#bulk-open').onclick=()=>{if(isAdmin()) $('#bulk-dialog').showModal();};
$('#bulk-dialog').addEventListener('cancel',e=>{if(bulkBusy)e.preventDefault();});
$('#bulk-preview').onclick=async()=>{
  if(bulkBusy || !isAdmin())return;
  const file=$('#bulk-file').files[0]; if(!file)return toast('Chọn file ZIP.');
  bulkBusy=true; $('#bulk-preview').disabled=true; $('#bulk-confirm').disabled=true;
  try { const data=new FormData();data.append('file',file); renderBulk(await api('/imports/preview',{method:'POST',body:data})); }
  catch(e){bulkJob=null;$('#bulk-status').textContent=e.message;}
  finally{bulkBusy=false;$('#bulk-preview').disabled=false;if(bulkJob)renderBulk(bulkJob);}
};
$('#bulk-confirm').onclick=async()=>{
  if(!bulkJob || bulkBusy || !isAdmin())return;
  bulkBusy=true;$('#bulk-preview').disabled=true;$('#bulk-file').disabled=true;$('#bulk-confirm').disabled=true;
  try { while(!bulkJob.done){renderBulk(await api(`/imports/${bulkJob.id}/next`,{method:'POST'}));} await loadClasses(); }
  catch(e){toast(e.message+' Có thể bấm xác nhận để tiếp tục.');}
  finally{bulkBusy=false;$('#bulk-preview').disabled=false;$('#bulk-file').disabled=false;if(bulkJob)renderBulk(bulkJob);}
};
