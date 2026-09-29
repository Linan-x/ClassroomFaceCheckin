/* 会议签到系统 — 前端交互逻辑 */

// ===== 工具函数 =====

function showToast(msg, type) {
    const t = document.getElementById('toast') || createToast();
    t.textContent = msg;
    t.className = 'toast ' + (type || '');
    t.style.display = 'block';
    setTimeout(() => { t.style.display = 'none'; }, 3000);
}
function createToast() {
    const t = document.createElement('div');
    t.id = 'toast'; t.className = 'toast'; t.style.display = 'none';
    document.body.appendChild(t); return t;
}
function api(path, opts) {
    const defaults = { headers: {} };
    if (opts && opts.body && !(opts.body instanceof FormData)) {
        defaults.headers['Content-Type'] = 'application/json';
    }
    return fetch(path, Object.assign(defaults, opts))
        .then(r => r.json().then(d => ({ ok: r.ok, data: d })).catch(() => ({ ok: r.ok, data: null })));
}
function escHtml(s) {
    const d = document.createElement('div');
    d.textContent = s; return d.innerHTML;
}

// ===== 首页：会议列表 =====

function loadMeetings() {
    const container = document.getElementById('meeting-list');
    const empty = document.getElementById('empty-state');
    api('/api/meetings').then(({ ok, data }) => {
        if (!ok || !data || !data.length) {
            container.style.display = 'none';
            if (empty) empty.style.display = 'block';
            return;
        }
        container.style.display = 'grid';
        if (empty) empty.style.display = 'none';
        container.innerHTML = data.map(m => {
            const total = m.participant_count || 0;
            const checked = m.checked_in || 0;
            const rate = total > 0 ? Math.round(checked / total * 100) : 0;
            const desc = m.description || '';
            const name = m.name || '?';
            return `<div class="meeting-card">
                <h3>${escHtml(name)}</h3>
                ${desc ? `<div class="desc">${escHtml(desc)}</div>` : ''}
                <div class="progress-bar"><div class="progress-fill" style="width:${rate}%"></div></div>
                <div class="meta"><span>👤 ${total} 人</span><span>✅ ${checked} 人已签到</span><span><strong>${rate}%</strong></span></div>
                <div class="actions">
                    <a href="/meeting/${encodeURIComponent(name)}" class="btn btn-primary btn-sm">管理</a>
                    <a href="/report/${encodeURIComponent(name)}" class="btn btn-info btn-sm">报告</a>
                </div></div>`;
        }).join('');
    });
}
function showCreateMeeting() { document.getElementById('create-modal').style.display = 'flex'; document.getElementById('meeting-name').focus(); }
function hideCreateMeeting() { document.getElementById('create-modal').style.display = 'none'; }
function createMeeting() {
    const name = document.getElementById('meeting-name').value.trim();
    const desc = document.getElementById('meeting-desc').value.trim();
    if (!name) { showToast('请输入会议名称', 'error'); return; }
    api('/api/meetings', { method: 'POST', body: JSON.stringify({ name, description: desc }) })
    .then(({ ok, data }) => {
        if (!ok) { showToast(data.error || '创建失败', 'error'); return; }
        hideCreateMeeting();
        document.getElementById('meeting-name').value = '';
        document.getElementById('meeting-desc').value = '';
        showToast('会议创建成功', 'success');
        loadMeetings();
    });
}

// ===== 会议详情 =====

function loadMeetingDetail() { loadMeetingStats(); loadParticipants(); }

function loadMeetingStats() {
    if (!window.MEETING_NAME) return;
    api('/api/meeting/' + encodeURIComponent(MEETING_NAME)).then(({ ok, data }) => {
        if (!ok) return;
        const total = data.total_participants || 0;
        const expected = data.expected_count || total;
        const checked = data.checked_in || 0;
        const unchecked = Math.max(0, expected - checked);
        const rate = expected > 0 ? (checked / expected * 100).toFixed(1) + '%' : '0%';
        document.getElementById('stat-total').textContent = total;
        document.getElementById('stat-expected').textContent = expected;
        document.getElementById('stat-checked').textContent = checked;
        document.getElementById('stat-unchecked').textContent = unchecked;
        var rateEl = document.getElementById('stat-rate');
        if (rateEl) rateEl.textContent = rate;
        const badge = document.getElementById('meeting-status');
        if (badge) {
            badge.textContent = '签到: ' + checked + '/' + expected;
            badge.style.background = checked > 0 ? '#d1fae5' : '#f1f5f9';
            badge.style.color = checked > 0 ? '#065f46' : '#64748b';
        }
    });
}

// ─── 会议设置 ──────────────────────────────────

function loadMeetingSettings() {
    var dateInput = document.getElementById('meeting-date');
    if (!dateInput) return;
    fetch('/api/meeting/' + encodeURIComponent(MEETING_NAME)).then(function(r) { return r.json(); }).then(function(data) {
        if (!data) return;
        if (data.meeting_date) dateInput.value = data.meeting_date;
        var dlInput = document.getElementById('deadline-input');
        var dlStatus = document.getElementById('deadline-status');
        if (data.checkin_deadline && dlInput) {
            dlInput.value = data.checkin_deadline;
            if (dlStatus) dlStatus.textContent = '超过此时间签到记为迟到';
        }
    });
}
function saveMeetingSettings() {
    var data = {};
    var di = document.getElementById('meeting-date');
    var dl = document.getElementById('deadline-input');
    if (di) data.meeting_date = di.value;
    if (dl) data.checkin_deadline = dl.value || null;
    api('/api/meeting/' + encodeURIComponent(MEETING_NAME), { method: 'PUT', body: JSON.stringify(data) })
    .then(function(r) { if (!r.ok) { showToast('保存失败','error'); return; } showToast('会议设置已保存','success'); loadMeetingStats(); });
}
function clearDeadline() {
    document.getElementById('deadline-input').value = '';
    var st = document.getElementById('deadline-status');
    if (st) st.textContent = '未设置';
    saveMeetingSettings();
}

// ─── 班级管理与关联 ────────────────────────────

function loadDepartments() {
    // 加载关联班级卡片（course-classes-list）
    var clist = document.getElementById('course-classes-list');
    if (clist) {
        fetch('/api/course/' + encodeURIComponent(MEETING_NAME) + '/classes')
        .then(function(r) { return r.json(); }).then(function(d) {
            var selected = d.classes || [];
            fetch('/api/global-classes').then(function(r) { return r.json(); }).then(function(gd) {
                var allClasses = gd.classes || [];
                if (!allClasses.length) {
                    clist.innerHTML = '<span style="color:#94a3b8;font-size:0.9rem;">暂无全局班级，请先在"班级管理"中创建</span>';
                    return;
                }
                var html = '<div style="display:flex;flex-wrap:wrap;gap:8px;padding:8px 0;">';
                allClasses.forEach(function(c) {
                    var checked = selected.indexOf(c) !== -1 ? 'checked' : '';
                    html += '<label style="display:flex;align-items:center;gap:6px;cursor:pointer;padding:6px 14px;background:#f1f5f9;border-radius:8px;font-size:0.9rem;">'
                        + '<input type="checkbox" class="class-cb" value="' + escHtml(c) + '" ' + checked + '> ' + escHtml(c) + '</label>';
                });
                html += '</div>';
                clist.innerHTML = html;
            });
        });
    }

    // 从全局班级加载下拉框和筛选
    fetch('/api/global-classes')
    .then(function(r) { return r.json(); }).then(function(data) {
        var depts = data.classes || [];
        // 更新所有班级下拉框
        var selects = document.querySelectorAll('#add-dept-select, #batch-dept-select');
        selects.forEach(function(sel) {
            var cur = sel.value;
            sel.innerHTML = '<option value="">— 无班级 —</option>' + depts.map(function(d) {
                return '<option value="' + escHtml(d) + '"' + (d === cur ? ' selected' : '') + '>' + escHtml(d) + '</option>';
            }).join('');
        });
        // 更新部门筛选按钮
        var filterDiv = document.getElementById('dept-filter');
        if (filterDiv) {
            filterDiv.style.display = depts.length ? 'flex' : 'none';
            filterDiv.innerHTML = '<button class="dept-filter-btn' + (currentDeptFilter === '' ? ' active' : '') + '" onclick="filterByDept(\'\')">全部</button>'
                + depts.map(function(d) {
                    return '<button class="dept-filter-btn' + (currentDeptFilter === d ? ' active' : '') + '" onclick="filterByDept(\'' + escHtml(d) + '\')">' + escHtml(d) + '</button>';
                }).join('')
                + (depts.length ? '<span class="dept-filter-hint" onclick="selectAllByDept()" style="margin-left:auto;cursor:pointer;font-size:0.85rem;color:var(--primary);">☑ 一键全选</span>' : '');
        }
    });
}

function saveCourseClasses() {
    var checked = [];
    document.querySelectorAll('.class-cb:checked').forEach(function(cb) {
        checked.push(cb.value);
    });
    fetch('/api/course/' + encodeURIComponent(MEETING_NAME) + '/classes', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({classes: checked})
    }).then(function(r) { return r.json(); }).then(function(d) {
        if (d.success) { showToast('班级关联已保存，学生已自动同步', 'success'); loadParticipants(); }
        else { showToast(d.error || '保存失败', 'error'); }
    });
}

function filterByDept(dept) {
    currentDeptFilter = dept;
    loadParticipants();
}
function selectAllByDept() {
    var items = document.querySelectorAll('.participant-item');
    items.forEach(function(item) {
        var cb = item.querySelector('.participant-cb');
        if (cb) {
            // 只选中当前筛选部门下的
            var dept = item.getAttribute('data-dept') || '';
            if (!currentDeptFilter || dept === currentDeptFilter) {
                cb.checked = true;
                participantCheckState[cb.getAttribute('data-name')] = true;
            }
        }
    });
    updateBatchDeleteBtn();
}

// ─── 参与者搜索与渲染 ─────────────────────────

function searchParticipants(query) {
    var list = document.getElementById('participant-list');
    if (!list) return;
    var url = '/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/participants/search?q=' + encodeURIComponent(query);
    fetch(url).then(function(r) { return r.json(); }).then(function(data) {
        if (!data || !data.length) {
            list.innerHTML = '<div class="empty-hint">' + (query ? '未找到 "' + escHtml(query) + '"' : '暂无参与者') + '</div>';
            return;
        }
        renderParticipantList(data, list);
    });
}

function renderParticipantList(participants, list) {
    var filtered = currentDeptFilter ? participants.filter(function(p) { return (p.department || '') === currentDeptFilter; }) : participants;
    if (!filtered.length) {
        list.innerHTML = '<div class="empty-hint">' + (currentDeptFilter ? '该班级暂无学生' : '暂无参与者') + '</div>';
        document.getElementById('btn-batch-delete').style.display = 'none';
        return;
    }
    list.innerHTML = filtered.map(function(p) {
        var checked = participantCheckState[p.name] || false;
        var photoHtml = (p.photos && p.photos.length > 0)
            ? '<div class="participant-photo" style="background-image:url(/' + p.photos[0].replace(/\\\\/g,'/').replace(/\\/g,'/') + ');"></div>'
            : '<div class="no-photo">👤</div>';
        var deptBadge = p.department ? '<span class="dept-badge">' + escHtml(p.department) + '</span>' : '';
        var phoneText = p.phone ? '<span class="phone-text">📞 ' + escHtml(p.phone) + '</span>' : '';
        return '<div class="participant-item" data-dept="' + (p.department || '') + '">'
            + '<label class="checkbox-label"><input type="checkbox" class="participant-cb" data-name="' + escHtml(p.name) + '" ' + (checked ? 'checked' : '') + ' onchange="toggleParticipantCheck(\'' + escHtml(p.name) + '\', this.checked)"></label>'
            + photoHtml
            + '<div class="participant-info"><div class="name">' + escHtml(p.name) + ' ' + deptBadge + '</div><div class="meta">' + phoneText + ' ' + p.photo_count + ' 张照片</div></div>'
            + '<div class="participant-actions">'
            + '<button class="btn btn-outline btn-sm" onclick="showRenameModal(\'' + escHtml(p.name) + '\')" style="margin-right:4px;">✏️</button>'
            + '<button class="btn btn-danger btn-sm" onclick="removeParticipant(\'' + escHtml(p.name) + '\')">删除</button>'
            + '</div></div>';
    }).join('');
    updateBatchDeleteBtn();
    document.getElementById('btn-batch-delete').style.display = Object.values(participantCheckState).filter(Boolean).length > 0 ? 'inline-flex' : 'none';
}

function exportParticipantList() { window.open('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/participants/export', '_blank'); }

function showRenameModal(oldName) { renameTarget = oldName; document.getElementById('rename-input').value = oldName; document.getElementById('rename-modal').style.display = 'flex'; }
function hideRenameModal() { document.getElementById('rename-modal').style.display = 'none'; renameTarget = ''; }
function confirmRename() {
    var newName = document.getElementById('rename-input').value.trim();
    if (!newName) { showToast('姓名不能为空', 'error'); return; }
    if (newName === renameTarget) { hideRenameModal(); return; }
    fetch('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/participants/' + encodeURIComponent(renameTarget) + '/rename', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ new_name: newName })
    }).then(function(r) { return r.json(); }).then(function(d) {
        if (d.error) { showToast(d.error, 'error'); return; }
        hideRenameModal(); showToast('已重命名为 ' + newName, 'success'); loadParticipants(); loadExpectedAttendees();
    });
}

let participantCheckState = {};

function loadParticipants() {
    const list = document.getElementById('participant-list');
    const countEl = document.getElementById('participant-count');
    if (!list) return;
    api('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/participants').then(({ ok, data }) => {
        if (!ok || !data || !data.length) {
            list.innerHTML = '<div class="empty-hint">暂无参与者</div>';
            document.getElementById('btn-batch-delete').style.display = 'none';
            if (countEl) countEl.textContent = '0';
            return;
        }
        renderParticipantList(data, list);
        if (countEl) countEl.textContent = data.length;
    });
}
function toggleParticipantCheck(name, checked) {
    participantCheckState[name] = checked;
    updateBatchDeleteBtn();
}
function updateBatchDeleteBtn() {
    var checked = Object.values(participantCheckState).filter(Boolean).length;
    var btn = document.getElementById('btn-batch-delete');
    if (btn) { btn.style.display = checked > 0 ? 'inline-flex' : 'none'; btn.textContent = checked > 0 ? '🗑 删除选中 (' + checked + ')' : '🗑 删除选中'; }
}
function batchDelete() {
    var names = Object.keys(participantCheckState).filter(function(k) { return participantCheckState[k]; });
    if (!names.length) return;
    if (!confirm('确定删除选中的 ' + names.length + ' 位参与者吗？')) return;
    api('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/participants/batch-delete', { method: 'POST', body: JSON.stringify({ names: names }) })
    .then(function(r) {
        if (!r.ok) { showToast('批量删除失败','error'); return; }
        names.forEach(function(n) { delete participantCheckState[n]; });
        showToast('已删除 ' + names.length + ' 人','success');
        loadParticipants(); loadMeetingStats(); loadExpectedAttendees();
    });
}

// ─── 添加参与者（含部门/电话） ──────────────────

function showAddParticipant() {
    document.getElementById('add-modal').style.display = 'flex';
    document.getElementById('participant-name').focus();
}
function hideAddParticipant() { document.getElementById('add-modal').style.display = 'none'; }
function addParticipant() {
    var name = document.getElementById('participant-name').value.trim();
    var phone = document.getElementById('participant-phone').value.trim();
    var dept = document.getElementById('add-dept-select').value;
    var fileInput = document.getElementById('participant-photo');
    if (!name) { showToast('请输入姓名','error'); return; }
    if (!fileInput.files.length) { showToast('请选择照片','error'); return; }
    var formData = new FormData();
    formData.append('name', name);
    formData.append('photo', fileInput.files[0]);
    api('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/participants', { method: 'POST', body: formData })
    .then(function(r) {
        if (!r.ok) { showToast(r.data && r.data.error || '添加失败','error'); return; }
        // 保存部门/电话元数据
        if (phone || dept) {
            fetch('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/participants/meta', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({ name: name, phone: phone, department: dept })
            });
        }
        hideAddParticipant();
        document.getElementById('participant-name').value = '';
        document.getElementById('participant-phone').value = '';
        document.getElementById('participant-photo').value = '';
        showToast('参与者添加成功','success');
        loadParticipants(); loadMeetingStats();
    });
}
function removeParticipant(name) {
    if (!confirm('确定删除参与者 "' + name + '" 吗？')) return;
    fetch('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/participants/' + encodeURIComponent(name), { method: 'DELETE' })
    .then(function(r) { return r.json(); }).then(function(d) {
        if (d.error) { showToast(d.error,'error'); return; }
        showToast('已删除','success'); loadParticipants(); loadMeetingStats();
    });
}

// ─── 批量上传照片 ──────────────────────────────

function showBatchUpload() {
    document.getElementById('batch-modal').style.display = 'flex';
    document.getElementById('batch-photos').value = '';
    document.getElementById('batch-preview').innerHTML = '';
    // 同步部门列表
    loadDepartments();
}
function hideBatchUpload() { document.getElementById('batch-modal').style.display = 'none'; }

document.addEventListener('change', function(e) {
    if (e.target && e.target.id === 'batch-photos') {
        var preview = document.getElementById('batch-preview');
        var names = [];
        for (var f of e.target.files) {
            names.push(f.name.replace(/\.[^.]+$/, ''));
        }
        preview.innerHTML = '<div class="batch-preview-list">' + names.map(function(n) { return '<span class="name-tag preview">' + escHtml(n) + '</span>'; }).join('') + '</div><p style="font-size:0.85rem;color:var(--text-secondary);margin-top:8px;">共 ' + names.length + ' 人</p>';
    }
});

function batchUpload() {
    var fileInput = document.getElementById('batch-photos');
    if (!fileInput.files.length) { showToast('请选择照片文件','error'); return; }
    var dept = document.getElementById('batch-dept-select').value;
    var formData = new FormData();
    for (var f of fileInput.files) { formData.append('photos', f); }
    var btn = document.querySelector('#batch-modal .btn-primary');
    btn.disabled = true; btn.textContent = '⏳ 上传中...';
    fetch('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/participants/batch', { method: 'POST', body: formData })
    .then(function(r) { return r.json(); }).then(function(d) {
        btn.disabled = false; btn.textContent = '上传并添加';
        if (d.error) { showToast(d.error,'error'); return; }
        // 如果选了部门，批量设置元数据
        if (dept && d.added && d.added.length) {
            fetch('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/participants/phones', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({ items: d.added.map(function(n) { return {name: n, department: dept, phone: ''}; }) })
            });
        }
        hideBatchUpload();
        showToast('成功添加 ' + (d.count || 0) + ' 人','success');
        loadParticipants(); loadExpectedAttendees();
    }).catch(function() { btn.disabled = false; btn.textContent = '上传并添加'; showToast('网络错误','error'); });
}

// ─── 批量上传电话 ──────────────────────────────

function showPhoneUpload() { document.getElementById('phone-modal').style.display = 'flex'; }
function hidePhoneUpload() { document.getElementById('phone-modal').style.display = 'none'; }
function uploadPhones() {
    var text = document.getElementById('phone-data').value.trim();
    if (!text) { showToast('请输入数据','error'); return; }
    var lines = text.split('\n').filter(function(l) { return l.trim(); });
    var items = lines.map(function(line) {
        var parts = line.split(',').map(function(s) { return s.trim(); });
        return { name: parts[0] || '', phone: parts[1] || '', department: parts[2] || '' };
    }).filter(function(item) { return item.name; });
    if (!items.length) { showToast('没有有效数据（至少需要姓名）','error'); return; }
    var btn = document.querySelector('#phone-modal .btn-primary');
    btn.disabled = true; btn.textContent = '⏳ 上传中...';
    fetch('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/participants/phones', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ items: items })
    }).then(function(r) { return r.json(); }).then(function(d) {
        btn.disabled = false; btn.textContent = '上传';
        if (d.error) { showToast(d.error,'error'); return; }
        hidePhoneUpload(); showToast('成功上传 ' + d.count + ' 人信息','success');
        loadParticipants();
    }).catch(function() { btn.disabled = false; btn.textContent = '上传'; showToast('网络错误','error'); });
}

// ─── 预期参会人员 ──────────────────────────────

function loadExpectedAttendees() {
    var list = document.getElementById('expected-list');
    if (!list) return;
    api('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/participants').then(function(r) {
        if (!r.ok || !r.data || !r.data.length) { list.innerHTML = '<div class="empty-hint">暂无参与者</div>'; return; }
        var participants = r.data;
        api('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/expected').then(function(r2) {
            var expected = (r2.data && r2.data.expected) || [];
            list.innerHTML = participants.map(function(p) {
                var checked = expected.indexOf(p.name) !== -1;
                var deptTag = p.department ? ' <span style="font-size:0.8rem;color:var(--text-secondary);">[' + escHtml(p.department) + ']</span>' : '';
                return '<label class="expected-item"><input type="checkbox" class="expected-cb" data-name="' + escHtml(p.name) + '" ' + (checked ? 'checked' : '') + '><span>' + escHtml(p.name) + deptTag + '</span></label>';
            }).join('');
        });
    });
}
function saveExpected() {
    var cbs = document.querySelectorAll('.expected-cb');
    var names = [];
    cbs.forEach(function(cb) { if (cb.checked) names.push(cb.getAttribute('data-name')); });
    api('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/expected', { method: 'POST', body: JSON.stringify({ names: names }) })
    .then(function(r) { if (!r.ok) { showToast('保存失败','error'); return; } showToast('已保存预期参会人员 (' + names.length + ' 人)','success'); loadMeetingStats(); });
}

// ─── 构建特征库 ──────────────────────────────

function buildFacebank() {
    const btn = event && event.target ? event.target : document.querySelector('.btn-warning');
    if (!btn) return;
    btn.disabled = true; btn.textContent = '⏳ 加载模型中...';
    showToast('正在加载模型并构建特征库，请稍候...', '');
    api('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/build', { method: 'POST' })
    .then(function(r) {
        if (!r.ok) { showToast('❌ ' + (r.data && r.data.error ? r.data.error : '构建失败'), 'error'); return; }
        showToast('✅ 特征库构建完成！共 ' + (r.data.count || 0) + ' 人', 'success');
        loadMeetingStats();
    }).catch(function(err) { showToast('❌ 网络错误: ' + err.message, 'error'); })
    .then(function() { btn.disabled = false; btn.textContent = '🔧 构建特征库'; });
}

// ===== 签到报告（独立页面 /report/<name> 使用） =====

function loadReport() {
    if (typeof MEETING_NAME === 'undefined') {
        console.warn('loadReport: MEETING_NAME not defined');
        return;
    }
    console.log('loadReport: loading for', MEETING_NAME);
    api('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/report').then(function(r) {
        if (!r.ok) { console.warn('loadReport: API error', r.data); return; }
        console.log('loadReport: data received', r.data);
        var d = r.data;
        var total = d.total_participants || 0;
        var checked = d.checked_in || 0;
        var late = d.late_count || 0;
        var ontime = d.ontime_count || 0;
        var rate = d.checkin_rate || '0%';
        var unchecked = d.not_checked_in || 0;
        var deadline = d.checkin_deadline || null;
        var deadlineHtml = '';
        if (deadline) deadlineHtml = '<div class="stat-card"><div class="stat-num" style="color:#f59e0b;">' + deadline + '</div><div class="stat-label">签到截止</div></div>';

        document.getElementById('report-stats').innerHTML = ''
            + '<div class="stat-card"><div class="stat-num">' + total + '</div><div class="stat-label">已注册</div></div>'
            + '<div class="stat-card"><div class="stat-num green">' + checked + '</div><div class="stat-label">已签到</div></div>'
            + '<div class="stat-card"><div class="stat-num" style="color:#10b981;">' + ontime + '</div><div class="stat-label">准时</div></div>'
            + '<div class="stat-card"><div class="stat-num" style="color:#f59e0b;">' + late + '</div><div class="stat-label">迟到</div></div>'
            + '<div class="stat-card"><div class="stat-num red">' + unchecked + '</div><div class="stat-label">未签到</div></div>'
            + '<div class="stat-card"><div class="stat-num blue">' + rate + '</div><div class="stat-label">签到率</div></div>'
            + deadlineHtml;

        // 签到明细
        var detailBody = document.getElementById('detail-body');
        var records = d.records || [];
        if (records.length) {
            detailBody.innerHTML = records.map(function(r) {
                var statusText = '✅ 准时', statusColor = '#10b981';
                if (r.late) { statusText = '⏰ 迟到 ' + (r.late_minutes || '') + ' 分钟'; statusColor = '#f59e0b'; }
                return '<tr><td>' + escHtml(r.name) + '</td><td>' + (r.time || '').substring(0, 19) + '</td><td style="color:' + statusColor + ';">' + statusText + '</td><td>' + (r.confidence ? r.confidence.toFixed(3) : '-') + '</td></tr>';
            }).join('');
        } else {
            detailBody.innerHTML = '<tr><td colspan="4" class="empty-cell">暂无签到记录</td></tr>';
        }

        // 签到状态
        var statusBody = document.getElementById('status-body');
        var allNames = d.all_names || [];
        var checkedNames = d.checked_names || [];
        if (allNames.length) {
            statusBody.innerHTML = allNames.map(function(n) {
                var c = checkedNames.indexOf(n) !== -1;
                return '<tr><td style="font-size:1.2rem;color:' + (c ? '#10b981' : '#ef4444') + '">' + (c ? '✅' : '⭕') + '</td><td>' + escHtml(n) + '</td></tr>';
            }).join('');
        } else {
            statusBody.innerHTML = '<tr><td colspan="2" class="empty-cell">暂无参与者</td></tr>';
        }
    });
}

function exportCSV() {
    window.open('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/export/csv', '_blank');
}
function exportHTML() {
    window.open('/api/meeting/' + encodeURIComponent(MEETING_NAME) + '/export/html', '_blank');
}

// ===== 签到台（管理后台不再使用，保留兼容） =====

function startCheckin() { showToast('请在签到台 (http://localhost:5001) 进行签到', 'error'); }
function stopCheckin() {}
function loadCheckinStatus() {}
