// MentiNous AI — Insights & End-of-Day Review Controller

import { apiRequest, showToast, escapeHtml } from './api.js';

export async function loadInsights() {
  const container = document.getElementById('insights-content');
  if (!container) return;

  try {
    const data = await apiRequest('/insights/summary');
    const m = data.metrics || {};
    const lists = data.lists || {};

    // 1. Metric Numbers
    document.getElementById('eod-completed-count').textContent = m.completed_tasks || 0;
    document.getElementById('eod-unfinished-count').textContent = m.unfinished_tasks || 0;
    document.getElementById('eod-postponed-count').textContent = m.postponed_tasks || 0;
    document.getElementById('eod-rate-val').textContent = `${m.completion_rate || 0}%`;

    // 2. Supportive banner
    const banner = document.getElementById('eod-supportive-text');
    if (banner) banner.textContent = data.supportive_message;

    // 3. Render Item Lists
    renderReviewList('list-completed-tasks', lists.completed, 'completed', 'No tasks marked completed today.');
    renderReviewList('list-unfinished-tasks', lists.unfinished, 'unfinished', 'No unfinished tasks remaining.');
    renderReviewList('list-postponed-tasks', lists.postponed, 'postponed', 'No tasks postponed today.');
    renderReviewList('list-upcoming-deadlines', lists.upcoming_deadlines, 'deadline', 'No urgent upcoming deadlines.');

    // 4. Render Weekly Bar Chart
    renderWeeklyChart(data.weekly_trend || []);

    // 5. Export Review Button
    const exportBtn = document.getElementById('btn-export-eod');
    if (exportBtn) {
      exportBtn.onclick = () => exportEodSummary(data);
    }

  } catch (err) {
    console.error('Failed to load insights:', err);
  }
}

function renderReviewList(containerId, items, type, emptyMsg) {
  const el = document.getElementById(containerId);
  if (!el) return;

  if (!items || items.length === 0) {
    el.innerHTML = `<div style="color:var(--text-subtle);font-size:0.85rem;padding:8px 0;">${emptyMsg}</div>`;
    return;
  }

  el.innerHTML = items.map(i => `
    <div class="review-item-row ${type}">
      <span><strong>${escapeHtml(i.title)}</strong> ${i.duration_min ? `(${i.duration_min}m)` : ''}</span>
      <span style="color:var(--text-muted);font-size:0.78rem;">
        ${i.completed_at ? `Done ${i.completed_at.split(' ')[1] || ''}` : (i.deadline ? `Due ${i.deadline}` : (i.start_time ? i.start_time : ''))}
      </span>
    </div>
  `).join('');
}

function renderWeeklyChart(trend) {
  const chartEl = document.getElementById('weekly-chart-bars');
  if (!chartEl) return;

  chartEl.innerHTML = trend.map(d => {
    const total = d.total || 0;
    const done = d.done || 0;
    const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 10;

    return `
      <div class="bar-col">
        <div style="font-size:0.75rem;color:var(--text-muted);">${done}/${total}</div>
        <div class="bar-tube" title="${d.date}: ${done} of ${total} tasks completed (${pct}%)">
          <div class="bar-fill" style="height: ${pct}%;"></div>
        </div>
        <div class="bar-day-name">${d.day_name}</div>
      </div>
    `;
  }).join('');
}

function exportEodSummary(data) {
  const m = data.metrics;
  const today = new Date().toLocaleDateString();
  const content = `# MentiNous AI — End-of-Day Review (${today})

${data.supportive_message}

## Daily Statistics
- Total Tasks: ${m.total_tasks}
- Completed Tasks: ${m.completed_tasks} (${m.completion_rate}% completion rate)
- Unfinished Tasks: ${m.unfinished_tasks}
- Rescheduled / Postponed: ${m.postponed_tasks}
- Planned Focus Time: ${m.total_planned_minutes} minutes
- Completed Focus Time: ${m.completed_minutes} minutes

Generated with MentiNous AI.
`;

  const blob = new Blob([content], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `MentiNous_Review_${new Date().toISOString().split('T')[0]}.md`;
  a.click();
  showToast('End-of-day summary downloaded as Markdown.', 'success');
}
