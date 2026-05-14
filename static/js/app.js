// ─── GLOBAL STATE ───
let currentPipelineId = null;
let currentSection = 'dashboard';
let pipelines = [];
let prospects = [];
let sequences = [];
let currentUser = null;
let editingProspectId = null;
let editingSequenceId = null;
let tempTags = [];
let tempSequenceSteps = [];
let csvFile = null;
let selectedProspects = new Set();

// ─── API HELPER ───
async function api(url, options = {}) {
    const defaults = {
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'same-origin'
    };

    try {
        const response = await fetch(url, { ...defaults, ...options });

        if (response.status === 401) {
            window.location.href = '/login';
            return null;
        }

        if (response.status === 403) {
            alert('Admin access required');
            return null;
        }

        if (!response.ok) {
            const error = await response.json().catch(() => ({ error: 'Request failed' }));
            throw new Error(error.error || `HTTP ${response.status}`);
        }

        return await response.json();
    } catch (err) {
        console.error('API Error:', err);
        throw err;
    }
}

// ─── MODAL FUNCTIONS ───
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Close modal on overlay click
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal-overlay') && e.target.classList.contains('active')) {
        e.target.classList.remove('active');
        document.body.style.overflow = '';
    }
});

// Close modal on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(m => {
            m.classList.remove('active');
        });
        document.body.style.overflow = '';
    }
});

// ─── SECTION NAVIGATION ───
function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    const section = document.getElementById(sectionId);
    if (section) section.classList.add('active');

    const navMap = {
        'dashboard': 'navDashboard',
        'pipeline-view': 'navPipelineView',
        'table-view': 'navTableView',
        'settings': 'navSettings'
    };

    const navId = navMap[sectionId];
    if (navId) {
        const nav = document.getElementById(navId);
        if (nav) nav.classList.add('active');
    }

    currentSection = sectionId;

    // Update page title
    const titles = {
        'dashboard': 'Dashboard',
        'pipeline-view': 'Pipeline View',
        'table-view': 'Table View',
        'settings': 'Settings'
    };
    document.getElementById('pageTitle').textContent = titles[sectionId] || 'Dashboard';

    // Load data for section
    if (sectionId === 'pipeline-view') {
        renderPipeline();
    } else if (sectionId === 'table-view') {
        loadTableView();
    } else if (sectionId === 'settings') {
        loadSettings();
    } else if (sectionId === 'dashboard') {
        loadDashboard();
    }
}

// ─── SIDEBAR TOGGLE ───
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('open');
}

// ─── PIPELINE LIST ───
async function renderPipelineList() {
    try {
        pipelines = await api('/api/pipelines') || [];
        const container = document.getElementById('pipelineList');

        container.innerHTML = pipelines.map(p => `
            <div class="pipeline-item ${p.id == currentPipelineId ? 'active' : ''}" 
                 onclick="selectPipeline(${p.id})">
                <span>${escapeHtml(p.name)}</span>
                <span class="count">${p.prospect_count || 0}</span>
            </div>
        `).join('');
    } catch (err) {
        console.error('Error loading pipelines:', err);
    }
}

function selectPipeline(id) {
    currentPipelineId = id;
    renderPipelineList();
    loadProspects();
    loadStats();

    if (currentSection === 'pipeline-view') {
        renderPipeline();
    } else if (currentSection === 'table-view') {
        loadTableView();
    }
}

function populatePipelineSelects() {
    const selects = ['prospectPipeline', 'importPipeline', 'sequencePipeline'];
    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (!select) return;

        const currentVal = select.value;
        select.innerHTML = '<option value="">Select Pipeline</option>' + 
            pipelines.map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('');

        if (currentPipelineId && selectId !== 'sequencePipeline') {
            select.value = currentPipelineId;
        } else if (currentVal) {
            select.value = currentVal;
        }
    });
}

// ─── PROSPECTS ───
async function loadProspects() {
    try {
        const params = new URLSearchParams();
        if (currentPipelineId) params.append('pipeline_id', currentPipelineId);

        const search = document.getElementById('searchInput')?.value;
        if (search) params.append('search', search);

        const status = document.getElementById('statusFilter')?.value;
        if (status) params.append('status', status);

        const tag = document.getElementById('tagFilter')?.value;
        if (tag) params.append('tag', tag);

        const month = document.getElementById('monthFilter')?.value;
        if (month) params.append('month', month);

        const year = document.getElementById('yearFilter')?.value;
        if (year) params.append('year', year);

        prospects = await api(`/api/prospects?${params}`) || [];

        if (currentSection === 'pipeline-view') {
            renderPipeline();
        } else if (currentSection === 'table-view') {
            renderTable();
        }

        loadStats();
    } catch (err) {
        console.error('Error loading prospects:', err);
    }
}

function loadTableView() {
    renderTable();
}

// ─── STATS ───
async function loadStats() {
    try {
        const params = new URLSearchParams();
        if (currentPipelineId) params.append('pipeline_id', currentPipelineId);

        const stats = await api(`/api/stats?${params}`);
        if (stats) {
            document.getElementById('statTotal').textContent = stats.total;
            document.getElementById('statOverdue').textContent = stats.overdue;
            document.getElementById('statDueSoon').textContent = stats.due_soon;
            document.getElementById('statOnTrack').textContent = stats.on_track;
        }
    } catch (err) {
        console.error('Error loading stats:', err);
    }
}

// ─── RENDER PIPELINE (KANBAN) ───
function renderPipeline() {
    const container = document.getElementById('kanbanContainer');
    if (!container) return;

    const columns = [
        { id: 'new-leads', title: 'New Leads', statuses: ['New Lead'] },
        { id: 'outreach', title: 'Outreach', statuses: ['Sent', 'Sent 1', 'Sent 2', 'Sent 3', 'Sent 4+'] },
        { id: 'engaged', title: 'Engaged', statuses: ['Responded', 'Meeting', 'Proposal'] },
        { id: 'closed', title: 'Closed', statuses: ['Closed-Won', 'Closed-Lost'] },
        { id: 'nurture', title: 'Nurture', statuses: ['Nurture'] }
    ];

    container.innerHTML = columns.map(col => {
        const colProspects = prospects.filter(p => col.statuses.includes(p.status));
        return `
            <div class="kanban-column">
                <div class="kanban-header">
                    <h4>${col.title}</h4>
                    <span class="kanban-count">${colProspects.length}</span>
                </div>
                <div class="kanban-cards">
                    ${colProspects.map(p => renderProspectCard(p)).join('')}
                    ${colProspects.length === 0 ? '<div class="empty-state" style="padding:20px"><p>No prospects</p></div>' : ''}
                </div>
            </div>
        `;
    }).join('');
}

function renderProspectCard(prospect) {
    const tagsHtml = (prospect.tags || []).map(t => 
        `<span class="tag tag-${t.toLowerCase()}">${escapeHtml(t)}</span>`
    ).join('');

    const followupClass = prospect.followup_status || 'on-track';
    const followupLabel = followupClass === 'overdue' ? 'Overdue' : 
                          followupClass === 'due-soon' ? 'Due Soon' : 'On Track';

    // Show sequence progress if applicable
    let sequenceBadge = '';
    if (prospect.sequence_id && sequences.length > 0) {
        const seq = sequences.find(s => s.id === prospect.sequence_id);
        if (seq && seq.steps) {
            const stepNum = (prospect.sequence_step_index || 0) + 1;
            const totalSteps = seq.steps.length;
            sequenceBadge = `<span class="sequence-badge">Step ${stepNum}/${totalSteps}</span>`;
        }
    }

    // Show last contact date
    let lastContactInfo = '';
    if (prospect.last_contact_date) {
        const date = new Date(prospect.last_contact_date);
        const daysAgo = Math.floor((new Date() - date) / (1000 * 60 * 60 * 24));
        lastContactInfo = `<div class="last-contact">Last contact: ${daysAgo === 0 ? 'Today' : daysAgo + ' days ago'}</div>`;
    }

    return `
        <div class="prospect-card ${followupClass}" onclick="showProspectDetails(${prospect.id})">
            <div class="name">${escapeHtml(prospect.first_name)} ${escapeHtml(prospect.last_name || '')}</div>
            <div class="company">${escapeHtml(prospect.company || 'No company')}</div>
            ${lastContactInfo}
            <div class="meta">
                <div class="tags">${tagsHtml}</div>
                ${sequenceBadge}
            </div>
            <div class="card-actions">
                <span class="followup-badge ${followupClass}">${followupLabel}</span>
                ${prospect.sequence_id ? `<button class="btn-advance" onclick="event.stopPropagation(); advanceSequence(${prospect.id})" title="Advance to next step">⏭️</button>` : ''}
            </div>
        </div>
    `;
}

// ─── RENDER TABLE ───
function renderTable() {
    const tbody = document.getElementById('tableBody');
    if (!tbody) return;

    if (prospects.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="empty-state">
                    <div class="icon">📭</div>
                    <h3>No prospects found</h3>
                    <p>Add prospects or adjust your filters</p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = prospects.map(p => {
        const tagsHtml = (p.tags || []).map(t => 
            `<span class="tag tag-${t.toLowerCase()}">${escapeHtml(t)}</span>`
        ).join('');

        const followupClass = p.followup_status || 'on-track';
        const followupLabel = followupClass === 'overdue' ? '⚠️ Overdue' : 
                              followupClass === 'due-soon' ? '⏰ Due Soon' : '✅ On Track';

        const lastContact = p.last_contact_date ? 
            new Date(p.last_contact_date).toLocaleDateString() : 'Never';

        // Sequence info
        let seqInfo = '-';
        if (p.sequence_id && sequences.length > 0) {
            const seq = sequences.find(s => s.id === p.sequence_id);
            if (seq) {
                seqInfo = `${escapeHtml(seq.name)} (${(p.sequence_step_index || 0) + 1}/${seq.steps?.length || '?'})`;
            }
        }

        const isSelected = selectedProspects.has(p.id);

        return `
            <tr class="${isSelected ? 'selected' : ''}">
                <td><input type="checkbox" ${isSelected ? 'checked' : ''} onchange="toggleSelectProspect(${p.id})" onclick="event.stopPropagation()"></td>
                <td class="name-cell">${escapeHtml(p.first_name)} ${escapeHtml(p.last_name || '')}</td>
                <td class="email-cell">${escapeHtml(p.email || '-')}</td>
                <td>${escapeHtml(p.company || '-')}</td>
                <td>
                    <select class="status-select" onchange="quickUpdateStatus(${p.id}, this.value)" onclick="event.stopPropagation()">
                        ${getStatusOptions(p.status)}
                    </select>
                </td>
                <td>${tagsHtml}</td>
                <td>${lastContact}</td>
                <td><span class="followup-badge ${followupClass}">${followupLabel}</span></td>
                <td class="actions">
                    <button class="btn-edit" onclick="event.stopPropagation(); editProspect(${p.id})">Edit</button>
                    <button class="btn-log" onclick="event.stopPropagation(); openContactModal(${p.id})">Log</button>
                    ${p.sequence_id ? `<button class="btn-advance" onclick="event.stopPropagation(); advanceSequence(${p.id})" title="Next Step">⏭️</button>` : ''}
                    <button class="btn-delete" onclick="event.stopPropagation(); deleteProspect(${p.id})">Del</button>
                </td>
            </tr>
        `;
    }).join('');
}

function getStatusOptions(currentStatus) {
    const statuses = ['New Lead', 'Sent', 'Sent 1', 'Sent 2', 'Sent 3', 'Sent 4+', 
                      'Responded', 'Meeting', 'Proposal', 'Closed-Won', 'Closed-Lost', 'Nurture'];
    return statuses.map(s => 
        `<option value="${s}" ${s === currentStatus ? 'selected' : ''}>${s}</option>`
    ).join('');
}

// ─── SELECTION & BULK ACTIONS ───
function toggleSelectProspect(id) {
    if (selectedProspects.has(id)) {
        selectedProspects.delete(id);
    } else {
        selectedProspects.add(id);
    }
    renderTable();
    updateBulkActionsBar();
}

function toggleSelectAll() {
    const allSelected = selectedProspects.size === prospects.length;
    if (allSelected) {
        selectedProspects.clear();
    } else {
        prospects.forEach(p => selectedProspects.add(p.id));
    }
    renderTable();
    updateBulkActionsBar();
}

function updateBulkActionsBar() {
    let bar = document.getElementById('bulkActionsBar');
    if (!bar) {
        bar = document.createElement('div');
        bar.id = 'bulkActionsBar';
        bar.className = 'bulk-actions-bar';
        document.querySelector('.table-container').insertBefore(bar, document.querySelector('.table-container').firstChild);
    }

    if (selectedProspects.size === 0) {
        bar.style.display = 'none';
        return;
    }

    bar.style.display = 'flex';
    bar.innerHTML = `
        <span class="bulk-count">${selectedProspects.size} selected</span>
        <div class="bulk-buttons">
            <button class="btn btn-sm btn-secondary" onclick="bulkAdvanceSequence()">⏭️ Advance Sequence</button>
            <button class="btn btn-sm btn-secondary" onclick="bulkUpdateStatus()">📝 Update Status</button>
            <button class="btn btn-sm btn-danger" onclick="bulkDelete()">🗑️ Delete</button>
            <button class="btn btn-sm btn-secondary" onclick="selectedProspects.clear(); renderTable(); updateBulkActionsBar();">Clear</button>
        </div>
    `;
}

async function bulkAdvanceSequence() {
    if (selectedProspects.size === 0) return;
    if (!confirm(`Advance ${selectedProspects.size} prospects to next sequence step?`)) return;

    try {
        const result = await api('/api/bulk/advance-sequence', {
            method: 'POST',
            body: JSON.stringify({ prospect_ids: Array.from(selectedProspects) })
        });

        alert(`Advanced ${result.advanced} prospects.${result.errors.length > 0 ? '\nErrors: ' + result.errors.join('\n') : ''}`);
        selectedProspects.clear();
        loadProspects();
        updateBulkActionsBar();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function bulkUpdateStatus() {
    if (selectedProspects.size === 0) return;

    const newStatus = prompt('Enter new status for selected prospects:');
    if (!newStatus) return;

    try {
        const result = await api('/api/bulk/update-status', {
            method: 'POST',
            body: JSON.stringify({ 
                prospect_ids: Array.from(selectedProspects),
                status: newStatus
            })
        });

        alert(`Updated ${result.updated} prospects`);
        selectedProspects.clear();
        loadProspects();
        updateBulkActionsBar();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function bulkDelete() {
    if (selectedProspects.size === 0) return;
    if (!confirm(`Delete ${selectedProspects.size} prospects? This cannot be undone.`)) return;

    let deleted = 0;
    for (const id of selectedProspects) {
        try {
            await api(`/api/prospects/${id}`, { method: 'DELETE' });
            deleted++;
        } catch (e) {
            console.error('Error deleting prospect:', e);
        }
    }

    alert(`Deleted ${deleted} prospects`);
    selectedProspects.clear();
    loadProspects();
    updateBulkActionsBar();
}

// ─── ADVANCE SEQUENCE ───
async function advanceSequence(prospectId) {
    try {
        const result = await api(`/api/prospects/${prospectId}/advance-sequence`, {
            method: 'POST'
        });

        if (result.success) {
            // Show success notification
            showNotification(`Advanced to: ${result.step_label}`, 'success');
            loadProspects();
            renderPipelineList();
        }
    } catch (err) {
        alert('Error advancing sequence: ' + err.message);
    }
}

function showNotification(message, type = 'info') {
    const notif = document.createElement('div');
    notif.className = `notification notification-${type}`;
    notif.textContent = message;
    document.body.appendChild(notif);

    setTimeout(() => {
        notif.classList.add('show');
    }, 10);

    setTimeout(() => {
        notif.classList.remove('show');
        setTimeout(() => notif.remove(), 300);
    }, 3000);
}

// ─── PROSPECT MODAL ───
function openProspectModal() {
    editingProspectId = null;
    document.getElementById('prospectModalTitle').textContent = 'Add Prospect';
    document.getElementById('prospectForm').reset();
    document.getElementById('prospectId').value = '';
    tempTags = [];
    renderTags();
    populatePipelineSelects();
    loadSequencesForSelect();

    if (currentPipelineId) {
        document.getElementById('prospectPipeline').value = currentPipelineId;
    }

    openModal('prospectModal');
}

function openPipelineModal() {
    document.getElementById('pipelineForm').reset();
    openModal('pipelineModal');
}

function openImportModal() {
    document.getElementById('importPreview').innerHTML = '';
    document.getElementById('importBtn').disabled = true;
    csvFile = null;
    populatePipelineSelects();
    loadSequencesForSelect('importSequence');
    openModal('importModal');
}

function openContactModal(prospectId) {
    document.getElementById('contactProspectId').value = prospectId;
    document.getElementById('contactNotes').value = '';
    openModal('contactModal');
}

// ─── TAG INPUT ───
function setupTagInput() {
    const input = document.getElementById('tagInput');
    if (!input) return;

    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const tag = this.value.trim().toLowerCase();
            if (tag && !tempTags.includes(tag)) {
                tempTags.push(tag);
                renderTags();
                this.value = '';
            }
        }
    });
}

function renderTags() {
    const display = document.getElementById('tagsDisplay');
    if (!display) return;

    display.innerHTML = tempTags.map(tag => `
        <span class="tag-chip">
            ${escapeHtml(tag)}
            <span class="remove" onclick="removeTag('${tag}')">&times;</span>
        </span>
    `).join('');
}

function removeTag(tag) {
    tempTags = tempTags.filter(t => t !== tag);
    renderTags();
}

// ─── SAVE PROSPECT ───
async function saveProspect() {
    const data = {
        pipeline_id: parseInt(document.getElementById('prospectPipeline').value),
        first_name: document.getElementById('prospectFirstName').value.trim(),
        last_name: document.getElementById('prospectLastName').value.trim(),
        email: document.getElementById('prospectEmail').value.trim(),
        linkedin_url: document.getElementById('prospectLinkedIn').value.trim(),
        phone: document.getElementById('prospectPhone').value.trim(),
        company: document.getElementById('prospectCompany').value.trim(),
        tags: tempTags,
        status: document.getElementById('prospectStatus').value,
        notes: document.getElementById('prospectNotes').value.trim(),
        sequence_id: document.getElementById('prospectSequence').value || null
    };

    if (!data.first_name || !data.pipeline_id) {
        alert('First name and pipeline are required');
        return;
    }

    // NEW: Handle last contact date
    const lastContactDate = document.getElementById('prospectLastContactDate')?.value;
    if (lastContactDate) {
        data.last_contact_date = new Date(lastContactDate).toISOString();
    }

    try {
        if (editingProspectId) {
            await api(`/api/prospects/${editingProspectId}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
        } else {
            await api('/api/prospects', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        }

        closeModal('prospectModal');
        loadProspects();
        renderPipelineList();
    } catch (err) {
        alert('Error saving prospect: ' + err.message);
    }
}

async function editProspect(id) {
    const prospect = prospects.find(p => p.id === id);
    if (!prospect) return;

    editingProspectId = id;
    document.getElementById('prospectModalTitle').textContent = 'Edit Prospect';
    document.getElementById('prospectId').value = id;
    document.getElementById('prospectFirstName').value = prospect.first_name || '';
    document.getElementById('prospectLastName').value = prospect.last_name || '';
    document.getElementById('prospectEmail').value = prospect.email || '';
    document.getElementById('prospectLinkedIn').value = prospect.linkedin_url || '';
    document.getElementById('prospectPhone').value = prospect.phone || '';
    document.getElementById('prospectCompany').value = prospect.company || '';
    document.getElementById('prospectStatus').value = prospect.status || 'New Lead';
    document.getElementById('prospectNotes').value = prospect.notes || '';

    // NEW: Set last contact date
    const lastContactInput = document.getElementById('prospectLastContactDate');
    if (lastContactInput && prospect.last_contact_date) {
        const date = new Date(prospect.last_contact_date);
        lastContactInput.value = date.toISOString().split('T')[0];
    } else if (lastContactInput) {
        lastContactInput.value = '';
    }

    populatePipelineSelects();
    document.getElementById('prospectPipeline').value = prospect.pipeline_id;

    await loadSequencesForSelect();
    if (prospect.sequence_id) {
        document.getElementById('prospectSequence').value = prospect.sequence_id;
    }

    tempTags = [...(prospect.tags || [])];
    renderTags();

    openModal('prospectModal');
}

async function deleteProspect(id) {
    if (!confirm('Are you sure you want to delete this prospect?')) return;

    try {
        await api(`/api/prospects/${id}`, { method: 'DELETE' });
        loadProspects();
        renderPipelineList();
    } catch (err) {
        alert('Error deleting prospect: ' + err.message);
    }
}

async function quickUpdateStatus(id, status) {
    try {
        await api(`/api/prospects/${id}`, {
            method: 'PUT',
            body: JSON.stringify({ status })
        });
        loadProspects();
    } catch (err) {
        alert('Error updating status: ' + err.message);
    }
}

async function logContact() {
    const prospectId = document.getElementById('contactProspectId').value;
    const notes = document.getElementById('contactNotes').value.trim();

    try {
        await api(`/api/prospects/${prospectId}/log-contact`, {
            method: 'POST',
            body: JSON.stringify({ notes })
        });
        closeModal('contactModal');
        loadProspects();
        showNotification('Contact logged successfully', 'success');
    } catch (err) {
        alert('Error logging contact: ' + err.message);
    }
}

// ─── SHOW PROSPECT DETAILS ───
function showProspectDetails(id) {
    const prospect = prospects.find(p => p.id === id);
    if (!prospect) return;

    const pipeline = pipelines.find(p => p.id === prospect.pipeline_id);
    const tagsHtml = (prospect.tags || []).map(t => 
        `<span class="tag tag-${t.toLowerCase()}">${escapeHtml(t)}</span>`
    ).join('');

    const lastContact = prospect.last_contact_date ? 
        new Date(prospect.last_contact_date).toLocaleString() : 'Never';
    const created = prospect.created_at ? 
        new Date(prospect.created_at).toLocaleString() : 'Unknown';

    // Sequence info
    let sequenceInfo = 'None';
    if (prospect.sequence_id && sequences.length > 0) {
        const seq = sequences.find(s => s.id === prospect.sequence_id);
        if (seq && seq.steps) {
            const currentStep = seq.steps[prospect.sequence_step_index || 0];
            const nextStep = seq.steps[prospect.sequence_step_index + 1];
            sequenceInfo = `
                <strong>${escapeHtml(seq.name)}</strong><br>
                Current: Step ${(prospect.sequence_step_index || 0) + 1} - ${escapeHtml(currentStep?.label || 'Unknown')}<br>
                ${nextStep ? `Next: Step ${(prospect.sequence_step_index || 0) + 2} - ${escapeHtml(nextStep.label)} (Day ${nextStep.days})` : '<em>Final step</em>'}
            `;
        }
    }

    // Next follow-up info
    let nextFollowupInfo = 'Not scheduled';
    if (prospect.next_followup) {
        const date = new Date(prospect.next_followup);
        const daysUntil = Math.floor((date - new Date()) / (1000 * 60 * 60 * 24));
        nextFollowupInfo = `${date.toLocaleString()} (${daysUntil < 0 ? 'Overdue ' + Math.abs(daysUntil) + ' days' : daysUntil + ' days'})`;
    }

    document.getElementById('detailsName').textContent = 
        `${escapeHtml(prospect.first_name)} ${escapeHtml(prospect.last_name || '')}`;

    document.getElementById('detailsBody').innerHTML = `
        <div class="details-grid">
            <div class="detail-item">
                <span class="detail-label">Email</span>
                <span class="detail-value">${prospect.email ? `<a href="mailto:${escapeHtml(prospect.email)}">${escapeHtml(prospect.email)}</a>` : '-'}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Phone</span>
                <span class="detail-value">${escapeHtml(prospect.phone || '-')}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">LinkedIn</span>
                <span class="detail-value">${prospect.linkedin_url ? `<a href="${escapeHtml(prospect.linkedin_url)}" target="_blank">${escapeHtml(prospect.linkedin_url)}</a>` : '-'}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Company</span>
                <span class="detail-value">${escapeHtml(prospect.company || '-')}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Pipeline</span>
                <span class="detail-value">${escapeHtml(pipeline?.name || '-')}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Status</span>
                <span class="detail-value">${escapeHtml(prospect.status)}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Tags</span>
                <span class="detail-value">${tagsHtml || '-'}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Created</span>
                <span class="detail-value">${created}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Last Contact</span>
                <span class="detail-value">${lastContact}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Next Follow-Up</span>
                <span class="detail-value">${nextFollowupInfo}</span>
            </div>
            <div class="detail-item" style="grid-column: 1 / -1;">
                <span class="detail-label">Sequence Progress</span>
                <span class="detail-value">${sequenceInfo}</span>
            </div>
        </div>
        ${prospect.notes ? `
            <div class="details-notes">
                <strong>Notes:</strong><br>
                ${escapeHtml(prospect.notes)}
            </div>
        ` : ''}
        <div class="details-activity">
            <h4>Activity</h4>
            <div id="detailsActivityList">Loading...</div>
        </div>
    `;

    openModal('detailsModal');
    loadActivityForProspect(id);
}

async function loadActivityForProspect(prospectId) {
    try {
        const logs = await api(`/api/activity-log?prospect_id=${prospectId}`) || [];
        const container = document.getElementById('detailsActivityList');

        if (logs.length === 0) {
            container.innerHTML = '<p style="color:#888;font-size:13px;">No activity yet</p>';
            return;
        }

        container.innerHTML = logs.map(log => `
            <div class="activity-item">
                <span class="time">${new Date(log.created_at).toLocaleString()}</span>
                <div>
                    <span class="action-badge ${log.action}">${log.action.replace('_', ' ')}</span>
                    ${log.username ? `<span class="user">by ${escapeHtml(log.username)}</span>` : ''}
                    ${log.details ? `<div style="color:#666;font-size:12px;margin-top:2px;">${escapeHtml(log.details)}</div>` : ''}
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Error loading activity:', err);
    }
}

// ─── CREATE PIPELINE ───
async function createPipeline() {
    const name = document.getElementById('pipelineName').value.trim();
    const description = document.getElementById('pipelineDescription').value.trim();

    if (!name) {
        alert('Pipeline name is required');
        return;
    }

    try {
        await api('/api/pipelines', {
            method: 'POST',
            body: JSON.stringify({ name, description })
        });
        closeModal('pipelineModal');
        renderPipelineList();
    } catch (err) {
        alert('Error creating pipeline: ' + err.message);
    }
}

// ─── SEQUENCES ───
async function loadSequences() {
    try {
        sequences = await api('/api/sequences') || [];
    } catch (err) {
        console.error('Error loading sequences:', err);
    }
}

async function loadSequencesForSelect(selectId = 'prospectSequence') {
    const select = document.getElementById(selectId);
    if (!select) return;

    const pipelineId = selectId === 'prospectSequence' 
        ? document.getElementById('prospectPipeline')?.value 
        : document.getElementById('importPipeline')?.value;

    if (!pipelineId) {
        select.innerHTML = '<option value="">Select Pipeline First</option>';
        return;
    }

    try {
        const seqs = await api(`/api/sequences?pipeline_id=${pipelineId}`) || [];
        select.innerHTML = '<option value="">No Sequence</option>' + 
            seqs.map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('');
    } catch (err) {
        console.error('Error loading sequences:', err);
    }
}

function renderSequencesSettings() {
    const container = document.getElementById('sequencesList');
    if (!container) return;

    if (sequences.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>No sequences yet</p></div>';
        return;
    }

    container.innerHTML = sequences.map(s => {
        const pipeline = pipelines.find(p => p.id === s.pipeline_id);
        const stepsPreview = (s.steps || []).map((step, i) => 
            `<span class="step-chip">Day ${step.days}: ${escapeHtml(step.label)}</span>`
        ).join('');

        return `
            <div class="sequence-item">
                <div class="header">
                    <div>
                        <div class="name">${escapeHtml(s.name)} ${s.is_default ? '<span style="color:#888;font-size:12px;">(Default)</span>' : ''}</div>
                        <div class="pipeline">${escapeHtml(pipeline?.name || 'Unknown Pipeline')}</div>
                    </div>
                    <div class="actions">
                        <button class="btn btn-sm btn-secondary" onclick="editSequence(${s.id})">Edit</button>
                    </div>
                </div>
                <div class="steps-preview">${stepsPreview}</div>
            </div>
        `;
    }).join('');
}

function createNewSequence() {
    editingSequenceId = null;
    document.getElementById('sequenceModalTitle').textContent = 'New Sequence';
    document.getElementById('sequenceForm').reset();
    document.getElementById('sequenceId').value = '';
    tempSequenceSteps = [
        { days: 0, status: 'New Lead', label: 'Initial Contact' },
        { days: 1, status: 'Sent', label: 'Day 1: First Message' },
        { days: 3, status: 'Sent 1', label: 'Day 3: Follow Up 1' },
        { days: 7, status: 'Sent 2', label: 'Day 7: Follow Up 2' },
        { days: 14, status: 'Sent 3', label: 'Day 14: Follow Up 3' },
        { days: 30, status: 'Sent 4+', label: 'Day 30: Final Follow Up' },
        { days: 45, status: 'Nurture', label: 'Day 45: Nurture/Re-engage' }
    ];
    populatePipelineSelects();
    renderSequenceSteps();
    openModal('sequenceModal');
}

function editSequence(id) {
    const sequence = sequences.find(s => s.id === id);
    if (!sequence) return;

    editingSequenceId = id;
    document.getElementById('sequenceModalTitle').textContent = 'Edit Sequence';
    document.getElementById('sequenceId').value = id;
    document.getElementById('sequenceName').value = sequence.name;
    populatePipelineSelects();
    document.getElementById('sequencePipeline').value = sequence.pipeline_id;
    tempSequenceSteps = JSON.parse(JSON.stringify(sequence.steps || []));
    renderSequenceSteps();
    openModal('sequenceModal');
}

function renderSequenceSteps() {
    const container = document.getElementById('stepsList');
    if (!container) return;

    container.innerHTML = tempSequenceSteps.map((step, i) => `
        <div class="step-row">
            <span class="step-num">${i + 1}</span>
            <input type="number" value="${step.days}" min="0" onchange="tempSequenceSteps[${i}].days = parseInt(this.value) || 0">
            <select onchange="tempSequenceSteps[${i}].status = this.value">
                ${getStatusOptions(step.status)}
            </select>
            <input type="text" value="${escapeHtml(step.label)}" onchange="tempSequenceSteps[${i}].label = this.value">
            <button type="button" class="remove-step" onclick="tempSequenceSteps.splice(${i}, 1); renderSequenceSteps();">&times;</button>
        </div>
    `).join('');
}

function addSequenceStep() {
    tempSequenceSteps.push({ days: 7, status: 'Sent', label: 'New Step' });
    renderSequenceSteps();
}

async function saveSequence() {
    const data = {
        id: editingSequenceId || undefined,
        pipeline_id: parseInt(document.getElementById('sequencePipeline').value),
        name: document.getElementById('sequenceName').value.trim(),
        steps: tempSequenceSteps
    };

    if (!data.name || !data.pipeline_id) {
        alert('Name and pipeline are required');
        return;
    }

    try {
        await api('/api/sequences', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        closeModal('sequenceModal');
        loadSequences();
        renderSequencesSettings();
    } catch (err) {
        alert('Error saving sequence: ' + err.message);
    }
}

// ─── USERS ───
async function loadUsers() {
    try {
        const users = await api('/api/users') || [];
        const container = document.getElementById('usersList');
        if (!container) return;

        container.innerHTML = users.map(u => `
            <div class="user-item">
                <div class="info">
                    <span class="username">${escapeHtml(u.username)}</span>
                    <span class="role ${u.role}">${u.role}</span>
                </div>
                <span style="color:#888;font-size:12px;">${new Date(u.created_at).toLocaleDateString()}</span>
            </div>
        `).join('');
    } catch (err) {
        console.error('Error loading users:', err);
    }
}

function openUserModal() {
    document.getElementById('userForm').reset();
    openModal('userModal');
}

async function createUser() {
    const data = {
        username: document.getElementById('userUsername').value.trim(),
        password: document.getElementById('userPassword').value.trim(),
        role: document.getElementById('userRole').value
    };

    if (!data.username || !data.password) {
        alert('Username and password are required');
        return;
    }

    try {
        await api('/api/users', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        closeModal('userModal');
        loadUsers();
    } catch (err) {
        alert('Error creating user: ' + err.message);
    }
}

// ─── SETTINGS ───
function showSettingsTab(tabId) {
    document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.settings-panel').forEach(p => p.classList.remove('active'));

    document.getElementById('tab' + tabId.charAt(0).toUpperCase() + tabId.slice(1)).classList.add('active');
    document.getElementById('settings-' + tabId).classList.add('active');

    if (tabId === 'users') {
        loadUsers();
    } else if (tabId === 'activity') {
        loadActivityLog();
    } else if (tabId === 'sequences') {
        loadSequences().then(renderSequencesSettings);
    }
}

async function loadSettings() {
    showSettingsTab('sequences');
}

async function loadActivityLog() {
    try {
        const logs = await api('/api/activity-log') || [];
        const container = document.getElementById('activityLogList');
        if (!container) return;

        if (logs.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No activity yet</p></div>';
            return;
        }

        container.innerHTML = logs.map(log => `
            <div class="activity-log-item">
                <span class="timestamp">${new Date(log.created_at).toLocaleString()}</span>
                <div class="content">
                    <span class="action-badge ${log.action}">${log.action.replace('_', ' ')}</span>
                    ${log.username ? `<strong>${escapeHtml(log.username)}</strong>` : 'System'}
                    ${log.details ? `<span style="color:#666;">- ${escapeHtml(log.details)}</span>` : ''}
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Error loading activity log:', err);
    }
}

// ─── DASHBOARD ───
async function loadDashboard() {
    try {
        const logs = await api('/api/activity-log') || [];
        const recentActivity = document.getElementById('recentActivity');

        if (recentActivity) {
            if (logs.length === 0) {
                recentActivity.innerHTML = '<div class="empty-state" style="padding:20px"><p>No recent activity</p></div>';
            } else {
                recentActivity.innerHTML = logs.slice(0, 10).map(log => `
                    <div class="activity-item">
                        <span class="time">${new Date(log.created_at).toLocaleString()}</span>
                        <div>
                            <span class="action">${escapeHtml(log.action)}</span>
                            ${log.username ? `<span class="user">by ${escapeHtml(log.username)}</span>` : ''}
                        </div>
                    </div>
                `).join('');
            }
        }

        const overview = document.getElementById('pipelineOverview');
        if (overview && pipelines.length > 0) {
            overview.innerHTML = pipelines.map(p => `
                <div class="overview-item">
                    <span class="name">${escapeHtml(p.name)}</span>
                    <span class="count">${p.prospect_count || 0}</span>
                </div>
            `).join('');
        }
    } catch (err) {
        console.error('Error loading dashboard:', err);
    }
}

// ─── IMPORT CSV ───
function setupDragDrop() {
    const dropzone = document.getElementById('importDropzone');
    const fileInput = document.getElementById('csvFileInput');
    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });
}

function handleFile(file) {
    if (!file.name.endsWith('.csv')) {
        alert('Please upload a CSV file');
        return;
    }

    csvFile = file;

    const reader = new FileReader();
    reader.onload = function(e) {
        const text = e.target.result;
        const lines = text.split('\n').slice(0, 6);
        const preview = document.getElementById('importPreview');

        // Parse headers to show mapping
        const headers = lines[0]?.split(',').map(h => h.trim()) || [];
        const mappingInfo = analyzeCSVMapping(headers);

        preview.innerHTML = `
            <div style="background:#f8f9fa;padding:12px;border-radius:8px;margin-bottom:8px;">
                <strong>File:</strong> ${escapeHtml(file.name)}<br>
                <strong>Size:</strong> ${(file.size / 1024).toFixed(1)} KB<br>
                <strong>Detected Columns:</strong>
                <ul style="margin:8px 0 0 20px;font-size:12px;">
                    ${mappingInfo.map(m => `<li>${escapeHtml(m.header)} → <strong>${m.mapsTo}</strong></li>`).join('')}
                </ul>
            </div>
            <div style="background:#d1fae5;padding:8px 12px;border-radius:8px;margin-bottom:8px;font-size:12px;">
                <strong>✅ Enhanced Import:</strong> Status and Date Sent columns will be automatically mapped to CRM fields.
            </div>
            <pre style="background:#1a1a2e;color:#fff;padding:12px;border-radius:8px;overflow-x:auto;font-size:12px;">${escapeHtml(lines.join('\n'))}</pre>
        `;

        document.getElementById('importBtn').disabled = false;
    };
    reader.readAsText(file);
}

function analyzeCSVMapping(headers) {
    const mappings = [];
    const lowerHeaders = headers.map(h => h.toLowerCase());

    const knownMappings = {
        'first name': 'First Name',
        'first_name': 'First Name',
        'lastname': 'Last Name',
        'last name': 'Last Name',
        'last_name': 'Last Name',
        'name': 'Full Name',
        'email': 'Email',
        'e-mail': 'Email',
        'phone': 'Phone',
        'telephone': 'Phone',
        'company': 'Company',
        'organization': 'Company',
        'linkedin': 'LinkedIn URL',
        'linkedin url': 'LinkedIn URL',
        'linkedin_url': 'LinkedIn URL',
        'status': 'Status (NEW - Auto-mapped)',
        'stage': 'Status (NEW - Auto-mapped)',
        'date sent': 'Last Contact Date (NEW - Auto-mapped)',
        'date_sent': 'Last Contact Date (NEW - Auto-mapped)',
        'sent date': 'Last Contact Date (NEW - Auto-mapped)',
        'last contact': 'Last Contact Date (NEW - Auto-mapped)',
        'last_contact': 'Last Contact Date (NEW - Auto-mapped)',
        'tags': 'Tags',
        'tag': 'Tags'
    };

    headers.forEach((header, i) => {
        const lower = lowerHeaders[i];
        let mapsTo = 'Custom Field';

        for (const [key, value] of Object.entries(knownMappings)) {
            if (lower.includes(key) || key.includes(lower)) {
                mapsTo = value;
                break;
            }
        }

        mappings.push({ header, mapsTo });
    });

    return mappings;
}

function handleFileSelect(e) {
    if (e.target.files.length > 0) {
        handleFile(e.target.files[0]);
    }
}

async function importCSV() {
    if (!csvFile) {
        alert('Please select a CSV file');
        return;
    }

    const pipelineId = document.getElementById('importPipeline').value;
    if (!pipelineId) {
        alert('Please select a pipeline');
        return;
    }

    const formData = new FormData();
    formData.append('file', csvFile);
    formData.append('pipeline_id', pipelineId);

    const sequenceId = document.getElementById('importSequence').value;
    if (sequenceId) {
        formData.append('sequence_id', sequenceId);
    }

    try {
        const response = await fetch('/api/import-csv', {
            method: 'POST',
            body: formData,
            credentials: 'same-origin'
        });

        const result = await response.json();

        if (result.success) {
            alert(`Successfully imported ${result.imported} prospects!${result.errors.length > 0 ? '\n\nErrors:\n' + result.errors.join('\n') : ''}`);
            closeModal('importModal');
            loadProspects();
            renderPipelineList();
        } else {
            alert('Error: ' + (result.error || 'Import failed'));
        }
    } catch (err) {
        alert('Error importing CSV: ' + err.message);
    }
}

// ─── FILTERS ───
function clearFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('statusFilter').value = '';
    document.getElementById('tagFilter').value = '';
    document.getElementById('monthFilter').value = '';
    document.getElementById('yearFilter').value = '';
    loadProspects();
}

function populateYearFilter() {
    const select = document.getElementById('yearFilter');
    if (!select) return;

    const currentYear = new Date().getFullYear();
    let html = '<option value="">All Years</option>';
    for (let y = currentYear; y >= currentYear - 5; y--) {
        html += `<option value="${y}">${y}</option>`;
    }
    select.innerHTML = html;
}

// ─── UTILITY ───
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ─── WINDOW ERROR HANDLER ───
window.onerror = function(msg, url, line, col, error) {
    console.error('JS Error:', msg, 'at', url, ':', line, ':', col);
    return false;
};

// ─── INITIALIZATION ───
document.addEventListener('DOMContentLoaded', async function() {
    // Setup tag input
    setupTagInput();

    // Setup drag & drop
    setupDragDrop();

    // Populate year filter
    populateYearFilter();

    // Load pipelines first
    await renderPipelineList();

    // Load sequences
    await loadSequences();

    // Load prospects
    await loadProspects();

    // Load stats
    await loadStats();

    // Load dashboard
    await loadDashboard();

    // Setup pipeline change listener for sequence select
    document.getElementById('prospectPipeline')?.addEventListener('change', () => {
        loadSequencesForSelect('prospectSequence');
    });

    document.getElementById('importPipeline')?.addEventListener('change', () => {
        loadSequencesForSelect('importSequence');
    });

    // Set current user
    try {
        const response = await fetch('/api/users');
        if (response.ok) {
            const users = await response.json();
            document.getElementById('currentUser').textContent = 'Logged In';
        }
    } catch (e) {
        // Silently fail
    }

    console.log('PrimeServ CRM initialized successfully');
});