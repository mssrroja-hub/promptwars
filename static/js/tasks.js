// MentiNous AI — Task Management Controller

import { apiRequest, showToast, escapeHtml } from './api.js';

let currentFilter = 'all';

export async function loadTasks() {
  const container = document.getElementById('tasks-view-list');
  if (!container) return;

  container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);">Loading tasks...</div>';

  try {
    const data = await apiRequest('/tasks');
    const tasks = data.tasks || [];
    renderTaskList(tasks);
  } catch (err) {
    container.innerHTML = `<div style="color:var(--status-high);padding:20px;">Failed to load tasks: ${escapeHtml(err.message)}</div>`;
  }
}

function renderTaskList(tasks) {
  const container = document.getElementById('tasks-view-list');
  if (!container) return;

  const todayStr = new Date().toISOString().split('T')[0];

  // Apply Filter
  const filtered = tasks.filter(t => {
    if (currentFilter === 'today') {
      return (t.start_time && t.start_time.startsWith(todayStr)) || (t.deadline && t.deadline.startsWith(todayStr));
    }
    if (currentFilter === 'upcoming') {
      return t.status !== 'completed' && (!t.start_time || t.start_time >= todayStr);
    }
    if (currentFilter === 'completed') {
      return t.status === 'completed';
    }
    if (currentFilter === 'high') {
      return t.priority === 'high';
    }
    return true; // 'all'
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-task-placeholder">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M9 11l3 3L22 4"/>
          <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
        </svg>
        <p style="font-weight:600;font-size:1.1rem;margin-bottom:4px;">No tasks found</p>
        <p style="font-size:0.88rem;">No items match the "${currentFilter}" filter. Click "+ Add Task" to schedule one.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(t => {
    const isDone = t.status === 'completed';
    return `
      <div class="task-card ${isDone ? 'completed' : ''}" id="task-card-${t.id}">
        <input type="checkbox" class="task-checkbox task-status-toggle" data-id="${t.id}" ${isDone ? 'checked' : ''}>
        <div class="task-main">
          <div class="task-title">${escapeHtml(t.title)}</div>
          ${t.description ? `<div class="task-desc">${escapeHtml(t.description)}</div>` : ''}
          <div class="task-badges">
            <span class="badge priority-${t.priority}">${t.priority.toUpperCase()}</span>
            <span class="badge time-badge">⏱ ${t.duration_min}m</span>
            ${t.start_time ? `<span class="badge time-badge">📅 ${t.start_time}</span>` : ''}
            ${t.deadline ? `<span class="badge deadline-badge">⚠️ Due ${t.deadline}</span>` : ''}
          </div>
        </div>
        <div class="task-actions">
          <button class="task-btn-icon btn-postpone" data-id="${t.id}" title="Postpone Task">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12 6 12 12 16 14"/>
            </svg>
          </button>
          <button class="task-btn-icon delete btn-delete-task" data-id="${t.id}" title="Delete Task">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
            </svg>
          </button>
        </div>
      </div>
    `;
  }).join('');

  // Attach Event Handlers
  container.querySelectorAll('.task-status-toggle').forEach(chk => {
    chk.addEventListener('change', async (e) => {
      const id = e.target.dataset.id;
      try {
        const res = await apiRequest(`/tasks/${id}/toggle`, 'POST');
        const card = document.getElementById(`task-card-${id}`);
        if (res.task.status === 'completed') {
          card.classList.add('completed');
          showToast('Task completed! Strikethrough applied.', 'success');
        } else {
          card.classList.remove('completed');
          showToast('Task marked as pending.', 'info');
        }
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });

  container.querySelectorAll('.btn-delete-task').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const id = btn.dataset.id;
      if (!confirm('Are you sure you want to delete this task?')) return;
      try {
        await apiRequest(`/tasks/${id}`, 'DELETE');
        showToast('Task deleted.', 'info');
        loadTasks();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });

  container.querySelectorAll('.btn-postpone').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.id;
      const minutes = prompt('Postpone by how many minutes? (e.g. 30, 60)', '60');
      if (!minutes) return;
      try {
        await apiRequest(`/tasks/${id}/postpone`, 'POST', { minutes: parseInt(minutes) });
        showToast(`Task postponed by ${minutes} minutes.`, 'info');
        loadTasks();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });
}

export function initTasksControls() {
  // Filter pills
  const pills = document.querySelectorAll('.filter-pill');
  pills.forEach(p => {
    p.addEventListener('click', () => {
      pills.forEach(x => x.classList.remove('active'));
      p.classList.add('active');
      currentFilter = p.dataset.filter;
      loadTasks();
    });
  });

  // Add Task Modal Handler
  const modal = document.getElementById('modal-add-task');
  const openBtns = [document.getElementById('btn-open-add-task'), document.getElementById('btn-nav-add-task')];
  const closeBtn = document.getElementById('btn-close-task-modal');
  const cancelBtn = document.getElementById('btn-cancel-task');
  const form = document.getElementById('form-add-task');

  openBtns.forEach(b => {
    if (b) b.addEventListener('click', () => modal.classList.add('active'));
  });

  const closeModal = () => modal.classList.remove('active');
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const title = document.getElementById('task-input-title').value.trim();
      const description = document.getElementById('task-input-desc').value.trim();
      const startDate = document.getElementById('task-input-date').value;
      const startTime = document.getElementById('task-input-time').value;
      const duration = parseInt(document.getElementById('task-input-duration').value || 30);
      const priority = document.getElementById('task-input-priority').value;
      const deadline = document.getElementById('task-input-deadline').value;

      if (!title) {
        showToast('Please enter a task title.', 'warning');
        return;
      }

      let startIso = null;
      let endIso = null;
      if (startDate && startTime) {
        startIso = `${startDate} ${startTime}`;
        const dt = new Date(`${startDate}T${startTime}`);
        dt.setMinutes(dt.getMinutes() + duration);
        endIso = `${dt.toISOString().split('T')[0]} ${dt.toTimeString().substring(0, 5)}`;
      }

      try {
        await apiRequest('/tasks', 'POST', {
          title,
          description,
          start_time: startIso,
          end_time: endIso,
          duration_min: duration,
          priority,
          deadline: deadline || null,
          status: 'pending'
        });

        showToast(`Task '${title}' created!`, 'success');
        form.reset();
        closeModal();
        loadTasks();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }
}
