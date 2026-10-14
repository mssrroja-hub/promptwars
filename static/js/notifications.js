// MentiNous AI — Proactive Missed-Task Notifications & Check-in Controller

import { apiRequest, showToast, escapeHtml } from './api.js';

let notificationCheckInterval = null;
let activeCheckinNotif = null;

export function initNotifications() {
  const bellBtn = document.getElementById('btn-notification-bell');
  const dropdown = document.getElementById('notification-dropdown');
  const badge = document.getElementById('notification-badge');

  if (bellBtn && dropdown) {
    bellBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      dropdown.classList.toggle('show');
      if (dropdown.classList.contains('show')) {
        loadNotificationsList();
      }
    });

    document.addEventListener('click', (e) => {
      if (!dropdown.contains(e.target) && !bellBtn.contains(e.target)) {
        dropdown.classList.remove('show');
      }
    });
  }

  // Request browser notification permission politely
  if ("Notification" in window && Notification.permission === "default") {
    // Show polite in-app prompt
    setTimeout(() => {
      const banner = document.createElement('div');
      banner.id = 'notif-perm-banner';
      banner.style.cssText = 'position:fixed;bottom:20px;left:20px;background:var(--bg-card);border:1px solid var(--accent-blue);padding:14px 18px;border-radius:12px;z-index:9999;box-shadow:var(--shadow-card);max-width:360px;';
      banner.innerHTML = `
        <div style="font-weight:600;font-size:0.92rem;margin-bottom:4px;color:var(--text-main);">Enable Browser Task Alerts?</div>
        <div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:10px;">Receive gentle check-ins when tasks finish, respecting your quiet hours.</div>
        <div style="display:flex;gap:8px;">
          <button class="btn-primary" id="btn-perm-enable" style="padding:6px 12px;font-size:0.82rem;">Allow</button>
          <button class="btn-secondary" id="btn-perm-dismiss" style="padding:6px 12px;font-size:0.82rem;">Later</button>
        </div>
      `;
      document.body.appendChild(banner);

      document.getElementById('btn-perm-enable').addEventListener('click', () => {
        Notification.requestPermission().then(perm => {
          if (perm === 'granted') showToast('Browser alerts enabled!', 'success');
          banner.remove();
        });
      });
      document.getElementById('btn-perm-dismiss').addEventListener('click', () => banner.remove());
    }, 4000);
  }

  // Proactive Missed Task Modal elements
  const modal = document.getElementById('modal-missed-task');
  const btnCompleted = document.getElementById('btn-notif-completed');
  const btnMoreTime = document.getElementById('btn-notif-more-time');
  const btnReschedule = document.getElementById('btn-notif-reschedule');
  const btnDismiss = document.getElementById('btn-notif-dismiss');

  if (btnCompleted) {
    btnCompleted.addEventListener('click', () => handleNotifAction('completed'));
  }
  if (btnMoreTime) {
    btnMoreTime.addEventListener('click', () => handleNotifAction('more_time'));
  }
  if (btnReschedule) {
    btnReschedule.addEventListener('click', () => handleNotifAction('reschedule'));
  }
  if (btnDismiss) {
    btnDismiss.addEventListener('click', () => handleNotifAction('dismiss'));
  }

  // Start check-in polling
  triggerTaskCheckin();
  if (notificationCheckInterval) clearInterval(notificationCheckInterval);
  notificationCheckInterval = setInterval(triggerTaskCheckin, 45000); // Check every 45s
}

export async function triggerTaskCheckin() {
  try {
    const res = await apiRequest('/notifications/checkin', 'POST');
    const badge = document.getElementById('notification-badge');

    if (res.in_quiet_hours) {
      if (badge) badge.classList.remove('active');
      return;
    }

    if (res.notifications && res.notifications.length > 0) {
      if (badge) badge.classList.add('active');

      // If user is not currently viewing a modal, prompt with the top missed task
      const modal = document.getElementById('modal-missed-task');
      if (modal && !modal.classList.contains('active')) {
        const topNotif = res.notifications[0];
        activeCheckinNotif = topNotif;
        showMissedTaskModal(topNotif);
      }
    } else {
      if (badge) badge.classList.remove('active');
    }
  } catch (err) {
    // Fail silently in background
    console.warn('Checkin notice:', err.message);
  }
}

function showMissedTaskModal(notif) {
  const modal = document.getElementById('modal-missed-task');
  const messageEl = document.getElementById('missed-task-prompt-text');
  if (!modal || !messageEl) return;

  messageEl.textContent = notif.message;
  modal.classList.add('active');

  // Trigger browser notification if permitted
  if ("Notification" in window && Notification.permission === "granted") {
    try {
      new Notification("MentiNous AI Check-in", {
        body: notif.message,
        icon: '/static/images/brand-icon.png'
      });
    } catch {
      // ignore
    }
  }
}

async function handleNotifAction(action) {
  const modal = document.getElementById('modal-missed-task');
  if (!activeCheckinNotif) {
    if (modal) modal.classList.remove('active');
    return;
  }

  try {
    const res = await apiRequest(`/notifications/${activeCheckinNotif.id}/respond`, 'POST', { action });
    modal.classList.remove('active');

    if (action === 'more_time' && res.proposal) {
      // Propose schedule adjustment and ask for explicit approval
      const confirmApproval = confirm(`${res.proposal.summary}\n\nWould you like to approve and apply this schedule adjustment now?`);
      if (confirmApproval) {
        await apiRequest(`/tasks/${res.proposal.task_id}`, 'PUT', {
          start_time: res.proposal.new_start_time,
          end_time: res.proposal.new_end_time,
          duration_min: 30
        });
        showToast('Schedule adjustment approved and saved!', 'success');
      } else {
        showToast('Schedule adjustment was not applied.', 'info');
      }
    } else {
      showToast(res.message, 'info');
    }

    activeCheckinNotif = null;
    triggerTaskCheckin();

    // Trigger dashboard refresh event
    window.dispatchEvent(new CustomEvent('data:changed'));

  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function loadNotificationsList() {
  const listEl = document.getElementById('notif-dropdown-list');
  if (!listEl) return;

  listEl.innerHTML = '<div style="color:var(--text-muted);font-size:0.85rem;text-align:center;padding:12px;">Checking notifications...</div>';

  try {
    const res = await apiRequest('/notifications/checkin', 'POST');
    const items = res.notifications || [];

    if (items.length === 0) {
      listEl.innerHTML = '<div style="color:var(--text-subtle);font-size:0.85rem;text-align:center;padding:16px;">No unread task alerts. You are up to date!</div>';
      return;
    }

    listEl.innerHTML = items.map(n => `
      <div style="padding:10px;border-bottom:1px solid var(--border-subtle);font-size:0.86rem;">
        <div style="color:var(--text-main);margin-bottom:6px;">${escapeHtml(n.message)}</div>
        <div style="display:flex;gap:6px;">
          <button class="btn-primary notif-list-act" data-id="${n.id}" data-action="completed" style="padding:4px 8px;font-size:0.75rem;">Done</button>
          <button class="btn-secondary notif-list-act" data-id="${n.id}" data-action="more_time" style="padding:4px 8px;font-size:0.75rem;">+30m</button>
          <button class="btn-secondary notif-list-act" data-id="${n.id}" data-action="dismiss" style="padding:4px 8px;font-size:0.75rem;">Dismiss</button>
        </div>
      </div>
    `).join('');

    listEl.querySelectorAll('.notif-list-act').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = btn.dataset.id;
        const action = btn.dataset.action;
        activeCheckinNotif = { id };
        await handleNotifAction(action);
        loadNotificationsList();
      });
    });

  } catch (err) {
    listEl.innerHTML = `<div style="color:var(--status-high);font-size:0.85rem;">${escapeHtml(err.message)}</div>`;
  }
}
