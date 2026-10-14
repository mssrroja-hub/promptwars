// MennilNexus AI — Personalized Pastel Dashboard Controller

import { apiRequest, AuthState, showToast, escapeHtml } from './api.js';

export async function loadDashboard() {
  const user = AuthState.getUser();
  if (!user) return;

  // 1. Personalized Greeting with ACTUAL registered name (never hardcoded)
  const greetingEl = document.getElementById('dashboard-user-greeting');
  if (greetingEl) {
    greetingEl.textContent = `Welcome back, ${user.name}! 👋`;
  }

  // Profile header info
  const profileNameEl = document.getElementById('sidebar-user-name');
  const profileEmailEl = document.getElementById('sidebar-user-email');
  const avatarEl = document.getElementById('sidebar-user-avatar');

  if (profileNameEl) profileNameEl.textContent = user.name;
  if (profileEmailEl) profileEmailEl.textContent = user.email;
  if (avatarEl) avatarEl.textContent = user.name.charAt(0).toUpperCase();

  // 2. Fetch Tasks & Metrics for Authenticated User
  try {
    const today = new Date().toISOString().split('T')[0];
    const data = await apiRequest(`/tasks?date=${today}`);
    const allTasksData = await apiRequest('/tasks');
    const tasks = data.tasks || [];
    const allTasks = allTasksData.tasks || [];

    // Calculate metrics
    const completedCount = tasks.filter(t => t.status === 'completed').length;
    const totalCount = tasks.length;
    const progressPct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

    const totalMinutes = tasks.reduce((acc, t) => acc + (t.duration_min || 0), 0);
    const focusHours = (totalMinutes / 60).toFixed(1);

    const deadlinesCount = allTasks.filter(t => t.deadline && t.status !== 'completed').length;

    // Update UI Cards
    const valProgress = document.getElementById('stat-progress-val');
    const fillProgress = document.getElementById('dashboard-progress-fill');
    const fillMiniProgress = document.getElementById('dashboard-progress-mini-fill');
    const labelCompleted = document.getElementById('stat-completed-label');
    const valFocus = document.getElementById('stat-focus-hours');
    const valDeadlines = document.getElementById('stat-deadlines-count');

    if (valProgress) valProgress.textContent = `${progressPct}%`;
    if (fillProgress) fillProgress.style.width = `${progressPct}%`;
    if (fillMiniProgress) fillMiniProgress.style.width = `${progressPct}%`;
    if (labelCompleted) labelCompleted.textContent = `${completedCount} of ${totalCount} tasks finished`;
    if (valFocus) valFocus.textContent = `${focusHours} hrs`;
    if (valDeadlines) valDeadlines.textContent = `${deadlinesCount}`;

    // 3. Render Next Up Card in Immediate Priority
    renderNextUpCard(tasks, allTasks);

    // 4. Render Today's Task Highlights
    renderDashboardTaskList(tasks);

    // 5. Fetch and Populate Game Personal Bests in Mental Fitness Panel
    loadGamePersonalBests();

    // 6. Bind View All Priority button
    const viewAllBtn = document.getElementById('btn-view-all-priority');
    if (viewAllBtn) {
      viewAllBtn.onclick = () => {
        const navTasks = document.getElementById('btn-nav-tasks');
        if (navTasks) navTasks.click();
      };
    }

  } catch (err) {
    console.error('Failed to load dashboard metrics:', err);
  }
}

function renderNextUpCard(todayTasks, allTasks) {
  const container = document.getElementById('next-up-container');
  if (!container) return;

  // Filter highest priority pending tasks (prioritize high priority first, then start time)
  const pending = todayTasks.filter(t => t.status !== 'completed');
  pending.sort((a, b) => {
    if (a.priority === 'high' && b.priority !== 'high') return -1;
    if (b.priority === 'high' && a.priority !== 'high') return 1;
    return (a.start_time || '').localeCompare(b.start_time || '');
  });

  if (pending.length === 0) {
    container.innerHTML = `
      <div class="empty-friendly-state">
        <div class="empty-friendly-icon">🧠✨</div>
        <div class="empty-friendly-title">No pending tasks remaining for today!</div>
        <div class="empty-friendly-desc">Great job making today count! Take a mindful break or play a quick mental workout. 💜</div>
      </div>
    `;
    return;
  }

  const nextTask = pending[0];
  const startTime = nextTask.start_time ? nextTask.start_time.split(' ')[1] : 'Flexible Focus';
  const endTime = nextTask.end_time ? nextTask.end_time.split(' ')[1] : '';

  container.innerHTML = `
    <div class="priority-task-item">
      <div>
        <div class="priority-task-title">${escapeHtml(nextTask.title)}</div>
        <div class="priority-task-meta">
          <span>⏰ ${startTime}${endTime ? ' – ' + endTime : ''} (${nextTask.duration_min}m)</span>
          <span class="badge priority-${nextTask.priority}">${nextTask.priority.toUpperCase()}</span>
          ${nextTask.deadline ? `<span class="badge deadline-badge">⚠️ Due ${nextTask.deadline}</span>` : ''}
        </div>
      </div>
      <div class="priority-actions">
        <button class="btn-primary" id="btn-nextup-complete" data-id="${nextTask.id}" style="padding:8px 16px;font-size:0.86rem;">
          ✓ Mark Done
        </button>
        <button class="btn-secondary" id="btn-nextup-postpone" data-id="${nextTask.id}" style="padding:8px 14px;font-size:0.86rem;">
          +30m Later
        </button>
      </div>
    </div>
  `;

  document.getElementById('btn-nextup-complete').addEventListener('click', async () => {
    try {
      await apiRequest(`/tasks/${nextTask.id}/toggle`, 'POST');
      showToast(`'${nextTask.title}' completed! Keep up the momentum! 🌱`, 'success');
      loadDashboard();
    } catch (err) {
      showToast(err.message, 'error');
    }
  });

  document.getElementById('btn-nextup-postpone').addEventListener('click', async () => {
    try {
      await apiRequest(`/tasks/${nextTask.id}/postpone`, 'POST', { minutes: 30 });
      showToast(`Postponed by 30 mins`, 'info');
      loadDashboard();
    } catch (err) {
      showToast(err.message, 'error');
    }
  });
}

function renderDashboardTaskList(tasks) {
  const container = document.getElementById('dashboard-task-list');
  if (!container) return;

  if (tasks.length === 0) {
    container.innerHTML = `
      <div class="empty-friendly-state" style="padding:28px 16px;">
        <div class="empty-friendly-icon">📋✨</div>
        <div class="empty-friendly-title">No tasks for today!</div>
        <div class="empty-friendly-desc">Plan something amazing for tomorrow 💜 or use Quick Add above.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = tasks.slice(0, 6).map(task => {
    const isDone = task.status === 'completed';
    return `
      <div class="task-card ${isDone ? 'completed' : ''}" style="margin-bottom:10px;">
        <input type="checkbox" class="task-checkbox dash-task-toggle" data-id="${task.id}" ${isDone ? 'checked' : ''}>
        <div class="task-main">
          <div class="task-title">${escapeHtml(task.title)}</div>
          <div class="task-badges">
            <span class="badge priority-${task.priority}">${task.priority}</span>
            <span class="badge time-badge">⏱ ${task.duration_min}m</span>
            ${task.start_time ? `<span class="badge time-badge">📅 ${task.start_time.split(' ')[1]}</span>` : ''}
            ${task.deadline ? `<span class="badge deadline-badge">Due ${task.deadline}</span>` : ''}
          </div>
        </div>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.dash-task-toggle').forEach(chk => {
    chk.addEventListener('change', async (e) => {
      const id = e.target.dataset.id;
      try {
        await apiRequest(`/tasks/${id}/toggle`, 'POST');
        loadDashboard();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });
}

async function loadGamePersonalBests() {
  try {
    const data = await apiRequest('/games/scores');
    const bests = data.personal_bests || [];

    const map = {
      'matrix-master': 'dash-pb-matrix',
      'memory-shift': 'dash-pb-memory',
      'neurosprint': 'dash-pb-neurosprint',
      'star-dash': 'dash-pb-stardash'
    };

    bests.forEach(item => {
      const elId = map[item.game_id];
      if (elId) {
        const el = document.getElementById(elId);
        if (el) el.textContent = `🏆 Best: ${item.high_score.toLocaleString()} pts`;
      }
    });
  } catch {
    // Non-fatal
  }
}

export function initQuickAdd() {
  const input = document.getElementById('quick-add-input');
  const btn = document.getElementById('btn-quick-add');
  if (!input || !btn) return;

  async function handleAdd() {
    const title = input.value.trim();
    if (!title) return;

    try {
      const today = new Date().toISOString().split('T')[0];
      await apiRequest('/tasks', 'POST', {
        title,
        duration_min: 45,
        priority: 'medium',
        start_time: `${today} 14:00`,
        status: 'pending'
      });
      input.value = '';
      showToast(`Task '${title}' scheduled for today! 🌱`, 'success');
      loadDashboard();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  btn.addEventListener('click', handleAdd);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleAdd();
  });
}
