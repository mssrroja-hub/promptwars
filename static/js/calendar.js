// MentiNous AI — Interactive Calendar View Controller (Month, Week, Day)

import { apiRequest, showToast, escapeHtml } from './api.js';

let currentDate = new Date();
let currentViewMode = 'month'; // 'month', 'week', 'day'
let cachedCalendarData = { events: [], tasks: [] };

export async function loadCalendar() {
  const titleEl = document.getElementById('cal-display-title');
  if (titleEl) {
    const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    titleEl.textContent = `${monthNames[currentDate.getMonth()]} ${currentDate.getFullYear()}`;
  }

  try {
    cachedCalendarData = await apiRequest('/calendar/events');
    renderCurrentCalendarView();
  } catch (err) {
    console.error('Failed to load calendar events:', err);
  }
}

function renderCurrentCalendarView() {
  if (currentViewMode === 'month') {
    renderMonthView();
  } else if (currentViewMode === 'week') {
    renderWeekView();
  } else if (currentViewMode === 'day') {
    renderDayView();
  }
}

function renderMonthView() {
  const container = document.getElementById('calendar-grid-container');
  if (!container) return;

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();

  const todayStr = new Date().toISOString().split('T')[0];

  let html = `
    <div class="month-calendar-grid">
      <div class="day-header-cell">Sun</div>
      <div class="day-header-cell">Mon</div>
      <div class="day-header-cell">Tue</div>
      <div class="day-header-cell">Wed</div>
      <div class="day-header-cell">Thu</div>
      <div class="day-header-cell">Fri</div>
      <div class="day-header-cell">Sat</div>
  `;

  // Previous month trailing days
  for (let i = firstDay - 1; i >= 0; i--) {
    const d = daysInPrevMonth - i;
    html += `<div class="calendar-day-cell other-month"><span class="day-number-label">${d}</span></div>`;
  }

  // Current month days
  for (let day = 1; day <= daysInMonth; day++) {
    const dStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const isToday = dStr === todayStr;

    // Filter events and tasks on this date
    const dayEvents = (cachedCalendarData.events || []).filter(e => e.start_time && e.start_time.startsWith(dStr));
    const dayTasks = (cachedCalendarData.tasks || []).filter(t => (t.start_time && t.start_time.startsWith(dStr)) || (t.deadline && t.deadline.startsWith(dStr)));

    html += `
      <div class="calendar-day-cell ${isToday ? 'today' : ''}" data-date="${dStr}">
        <span class="day-number-label">${day}</span>
        ${dayEvents.map(e => `
          <div class="cal-event-pill ${e.event_type || 'event'}" title="${escapeHtml(e.title)} (${e.start_time})">
            ${escapeHtml(e.title)}
          </div>
        `).join('')}
        ${dayTasks.map(t => `
          <div class="cal-event-pill ${t.deadline ? 'deadline' : 'task'} ${t.status === 'completed' ? 'completed' : ''}" title="${escapeHtml(t.title)}">
            ${t.status === 'completed' ? '✓ ' : ''}${escapeHtml(t.title)}
          </div>
        `).join('')}
      </div>
    `;
  }

  // Trailing next month days to complete 35 or 42 grid cells
  const totalCells = firstDay + daysInMonth;
  const remaining = totalCells > 35 ? 42 - totalCells : 35 - totalCells;
  for (let i = 1; i <= remaining; i++) {
    html += `<div class="calendar-day-cell other-month"><span class="day-number-label">${i}</span></div>`;
  }

  html += '</div>';
  container.innerHTML = html;
}

function renderWeekView() {
  const container = document.getElementById('calendar-grid-container');
  if (!container) return;

  // Find start of week (Sunday)
  const curr = new Date(currentDate);
  const first = curr.getDate() - curr.getDay();
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  let html = '<div class="week-calendar-grid">';

  for (let i = 0; i < 7; i++) {
    const d = new Date(curr.setDate(first + i));
    const dStr = d.toISOString().split('T')[0];
    const isToday = dStr === new Date().toISOString().split('T')[0];

    const dayEvents = (cachedCalendarData.events || []).filter(e => e.start_time && e.start_time.startsWith(dStr));
    const dayTasks = (cachedCalendarData.tasks || []).filter(t => (t.start_time && t.start_time.startsWith(dStr)) || (t.deadline && t.deadline.startsWith(dStr)));

    html += `
      <div class="week-day-col ${isToday ? 'today' : ''}">
        <div class="week-day-col-header">
          <div class="day-title">${dayNames[i]}</div>
          <div class="date-title">${d.getDate()}</div>
        </div>
        <div class="week-day-events-body">
          ${dayEvents.map(e => `
            <div class="cal-event-pill ${e.event_type || 'event'}">
              <strong>${e.start_time.split(' ')[1] || ''}</strong> ${escapeHtml(e.title)}
            </div>
          `).join('')}
          ${dayTasks.map(t => `
            <div class="cal-event-pill ${t.deadline ? 'deadline' : 'task'} ${t.status === 'completed' ? 'completed' : ''}">
              <strong>${t.start_time ? t.start_time.split(' ')[1] : 'Task'}</strong> ${escapeHtml(t.title)}
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  html += '</div>';
  container.innerHTML = html;
}

function renderDayView() {
  const container = document.getElementById('calendar-grid-container');
  if (!container) return;

  const dStr = currentDate.toISOString().split('T')[0];
  const dayEvents = (cachedCalendarData.events || []).filter(e => e.start_time && e.start_time.startsWith(dStr));
  const dayTasks = (cachedCalendarData.tasks || []).filter(t => (t.start_time && t.start_time.startsWith(dStr)) || (t.deadline && t.deadline.startsWith(dStr)));

  const hours = [];
  for (let h = 8; h <= 21; h++) {
    const hStr = String(h).padStart(2, '0');
    hours.push({ hour: `${hStr}:00`, display: h > 12 ? `${h - 12}:00 PM` : `${h}:00 AM` });
  }

  let html = `
    <div class="day-view-container">
      <h3>Hourly Schedule for ${currentDate.toDateString()}</h3>
      <div class="day-timeline-list">
  `;

  html += hours.map(hr => {
    const matched = dayTasks.filter(t => t.start_time && t.start_time.includes(hr.hour.substring(0, 2) + ':'));
    return `
      <div class="day-hour-row">
        <div class="day-hour-label">${hr.display}</div>
        <div class="day-hour-events">
          ${matched.length ? matched.map(m => `
            <div class="cal-event-pill ${m.priority === 'high' ? 'deadline' : 'task'}">
              ${escapeHtml(m.title)} (${m.duration_min}m)
            </div>
          `).join('') : '<span style="color:var(--text-subtle);font-size:0.8rem;">Open Focus Window</span>'}
        </div>
      </div>
    `;
  }).join('');

  html += '</div></div>';
  container.innerHTML = html;
}

export function initCalendarControls() {
  const prevBtn = document.getElementById('cal-btn-prev');
  const nextBtn = document.getElementById('cal-btn-next');
  const todayBtn = document.getElementById('cal-btn-today');

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (currentViewMode === 'month') {
        currentDate.setMonth(currentDate.getMonth() - 1);
      } else if (currentViewMode === 'week') {
        currentDate.setDate(currentDate.getDate() - 7);
      } else {
        currentDate.setDate(currentDate.getDate() - 1);
      }
      loadCalendar();
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      if (currentViewMode === 'month') {
        currentDate.setMonth(currentDate.getMonth() + 1);
      } else if (currentViewMode === 'week') {
        currentDate.setDate(currentDate.getDate() + 7);
      } else {
        currentDate.setDate(currentDate.getDate() + 1);
      }
      loadCalendar();
    });
  }

  if (todayBtn) {
    todayBtn.addEventListener('click', () => {
      currentDate = new Date();
      loadCalendar();
    });
  }

  // View switchers
  document.querySelectorAll('.view-mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.view-mode-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentViewMode = btn.dataset.mode;
      renderCurrentCalendarView();
    });
  });
}
