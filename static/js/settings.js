// MentiNous AI — Settings & Privacy Controller

import { apiRequest, AuthState, showToast } from './api.js';

export async function loadSettings() {
  const user = AuthState.getUser();
  if (user) {
    document.getElementById('settings-profile-name').textContent = user.name;
    document.getElementById('settings-profile-email').textContent = user.email;
    document.getElementById('settings-user-id').textContent = `#${user.id}`;
  }

  try {
    const data = await apiRequest('/settings');
    const s = data.settings || {};

    const qStart = document.getElementById('setting-quiet-start');
    const qEnd = document.getElementById('setting-quiet-end');
    const notifToggle = document.getElementById('setting-notif-enabled');
    const soundToggle = document.getElementById('setting-sound-enabled');

    if (qStart) qStart.value = s.quiet_hours_start || '22:00';
    if (qEnd) qEnd.value = s.quiet_hours_end || '07:00';
    if (notifToggle) notifToggle.checked = s.notifications_enabled !== 0;
    if (soundToggle) soundToggle.checked = s.sound_enabled !== 0;

  } catch (err) {
    console.error('Failed to load settings:', err);
  }
}

export function initSettingsHandlers() {
  // Save Preferences Form
  const prefForm = document.getElementById('form-save-preferences');
  if (prefForm) {
    prefForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const quiet_hours_start = document.getElementById('setting-quiet-start').value;
      const quiet_hours_end = document.getElementById('setting-quiet-end').value;
      const notifications_enabled = document.getElementById('setting-notif-enabled').checked;
      const sound_enabled = document.getElementById('setting-sound-enabled').checked;

      try {
        await apiRequest('/settings', 'PUT', {
          quiet_hours_start,
          quiet_hours_end,
          notifications_enabled,
          sound_enabled
        });
        showToast('Preferences updated successfully.', 'success');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  // Change Password Form
  const pwdForm = document.getElementById('form-change-password');
  if (pwdForm) {
    pwdForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const current_password = document.getElementById('pwd-current').value;
      const new_password = document.getElementById('pwd-new').value;
      const confirm_password = document.getElementById('pwd-confirm').value;

      if (new_password.length !== 4) {
        showToast('New password must be exactly 4 characters.', 'error');
        return;
      }
      if (new_password !== confirm_password) {
        showToast('New passwords do not match.', 'error');
        return;
      }

      try {
        await apiRequest('/settings/password', 'PUT', {
          current_password,
          new_password,
          confirm_password
        });
        showToast('Password successfully changed!', 'success');
        pwdForm.reset();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  // Export Data Button
  const exportBtn = document.getElementById('btn-export-data');
  if (exportBtn) {
    exportBtn.addEventListener('click', async () => {
      try {
        const data = await apiRequest('/settings/export');
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `MentiNous_User_Data_${data.user.id}.json`;
        a.click();
        showToast('Your complete data package has been downloaded.', 'success');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  // Delete Account
  const deleteBtn = document.getElementById('btn-delete-account');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', async () => {
      const confirmInput = prompt('This will permanently delete your account, tasks, schedule, and game records.\n\nType DELETE MY ACCOUNT to confirm:');
      if (confirmInput !== 'DELETE MY ACCOUNT') {
        showToast('Account deletion cancelled.', 'info');
        return;
      }

      try {
        await apiRequest('/settings/account', 'DELETE', { confirmation: confirmInput });
        AuthState.clearToken();
        AuthState.clearUser();
        alert('Your account and all associated data have been deleted.');
        window.location.reload();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }
}
