// MentiNous AI — Master Application Orchestrator

import { AuthState } from './api.js';
import { initAuth, logout } from './auth.js';
import { loadDashboard, initQuickAdd } from './dashboard.js';
import { loadTasks, initTasksControls } from './tasks.js';
import { initAIAssistant } from './ai_assistant.js';
import { loadCalendar, initCalendarControls } from './calendar.js';
import { initNotifications } from './notifications.js';
import { loadGamesHub } from './games.js';
import { loadInsights } from './insights.js';
import { loadSettings, initSettingsHandlers } from './settings.js';

let currentActiveView = 'dashboard';

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Auth
  initAuth((user) => {
    bootstrapApplication(user);
  });
});

function bootstrapApplication(user) {
  // Set Profile labels
  const nameEl = document.getElementById('sidebar-user-name');
  const emailEl = document.getElementById('sidebar-user-email');
  const avatarEl = document.getElementById('sidebar-user-avatar');

  if (nameEl) nameEl.textContent = user.name;
  if (emailEl) emailEl.textContent = user.email;
  if (avatarEl) avatarEl.textContent = user.name.charAt(0).toUpperCase();

  // Initialize subsystems
  initNavigation();
  initQuickAdd();
  initTasksControls();
  initAIAssistant();
  initCalendarControls();
  initNotifications();
  initSettingsHandlers();

  // Logout button
  const logoutBtn = document.getElementById('btn-sidebar-logout');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      if (confirm('Log out of MennilNexus AI?')) {
        logout();
      }
    });
  }

  // Mobile drawer toggle
  const mobileToggle = document.getElementById('btn-mobile-menu-toggle');
  const sidebar = document.getElementById('sidebar');
  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener('click', () => {
      sidebar.classList.toggle('mobile-open');
    });
  }

  // Load default view
  switchView('dashboard');

  // Global data change listener (e.g. after notifications or scheduler updates)
  window.addEventListener('data:changed', () => {
    if (currentActiveView === 'dashboard') loadDashboard();
    if (currentActiveView === 'tasks') loadTasks();
    if (currentActiveView === 'calendar') loadCalendar();
    if (currentActiveView === 'insights') loadInsights();
  });
}

function initNavigation() {
  const views = [
    { id: 'dashboard', btnId: 'btn-nav-dashboard', viewId: 'view-dashboard', title: 'Dashboard', loader: loadDashboard },
    { id: 'ai', btnId: 'btn-nav-ai', viewId: 'view-ai', title: 'AI Assistant', loader: null },
    { id: 'tasks', btnId: 'btn-nav-tasks', viewId: 'view-tasks', title: 'Tasks & Schedules', loader: loadTasks },
    { id: 'calendar', btnId: 'btn-nav-calendar', viewId: 'view-calendar', title: 'Calendar', loader: loadCalendar },
    { id: 'games', btnId: 'btn-nav-games', viewId: 'view-games', title: 'Productivity / Energy Hub', loader: loadGamesHub },
    { id: 'insights', btnId: 'btn-nav-insights', viewId: 'view-insights', title: 'Insights', loader: loadInsights },
    { id: 'settings', btnId: 'btn-nav-settings', viewId: 'view-settings', title: 'Settings & Privacy', loader: loadSettings }
  ];

  views.forEach(v => {
    const btn = document.getElementById(v.btnId);
    if (btn) {
      btn.addEventListener('click', () => {
        switchView(v.id);
        const sidebar = document.getElementById('sidebar');
        if (sidebar) sidebar.classList.remove('mobile-open');
      });
    }
  });
}

export function switchView(viewName) {
  currentActiveView = viewName;
  const viewMap = {
    'dashboard': { viewId: 'view-dashboard', navId: 'nav-item-dashboard', title: 'Dashboard', loader: loadDashboard },
    'ai': { viewId: 'view-ai', navId: 'nav-item-ai', title: 'AI Assistant', loader: null },
    'tasks': { viewId: 'view-tasks', navId: 'nav-item-tasks', title: 'Tasks & Schedules', loader: loadTasks },
    'calendar': { viewId: 'view-calendar', navId: 'nav-item-calendar', title: 'Calendar', loader: loadCalendar },
    'games': { viewId: 'view-games', navId: 'nav-item-games', title: 'Productivity / Energy Hub', loader: loadGamesHub },
    'insights': { viewId: 'view-insights', navId: 'nav-item-insights', title: 'Insights', loader: loadInsights },
    'settings': { viewId: 'view-settings', navId: 'nav-item-settings', title: 'Settings & Privacy', loader: loadSettings }
  };

  const target = viewMap[viewName];
  if (!target) return;

  // Toggle active views
  document.querySelectorAll('.view-container').forEach(v => v.classList.remove('active'));
  const activeContainer = document.getElementById(target.viewId);
  if (activeContainer) activeContainer.classList.add('active');

  // Toggle active nav menu items
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const activeNav = document.getElementById(target.navId);
  if (activeNav) activeNav.classList.add('active');

  // Update top page title
  const titleEl = document.getElementById('navbar-page-title');
  if (titleEl) titleEl.textContent = target.title;

  // Execute view loader
  if (target.loader) {
    target.loader();
  }
}
