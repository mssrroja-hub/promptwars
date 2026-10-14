// MentiNous AI — API Client & Global Helpers

const API_BASE = '/api';

export const AuthState = {
  getToken() {
    return localStorage.getItem('mentinous_token');
  },
  setToken(token) {
    localStorage.setItem('mentinous_token', token);
  },
  clearToken() {
    localStorage.removeItem('mentinous_token');
  },
  getUser() {
    try {
      return JSON.parse(localStorage.getItem('mentinous_user') || 'null');
    } catch {
      return null;
    }
  },
  setUser(user) {
    localStorage.setItem('mentinous_user', JSON.stringify(user));
  },
  clearUser() {
    localStorage.removeItem('mentinous_user');
  }
};

export async function apiRequest(endpoint, method = 'GET', data = null) {
  const headers = {
    'Content-Type': 'application/json'
  };
  const token = AuthState.getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const options = {
    method,
    headers
  };

  if (data && (method === 'POST' || method === 'PUT' || method === 'DELETE')) {
    options.body = JSON.stringify(data);
  }

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, options);
    const json = await res.json().catch(() => ({}));
    
    if (res.status === 401 && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/register')) {
      // Session invalid or expired
      AuthState.clearToken();
      AuthState.clearUser();
      window.dispatchEvent(new CustomEvent('auth:expired'));
      throw new Error(json.error || 'Session expired. Please log in again.');
    }

    if (!res.ok) {
      throw new Error(json.error || 'Server error occurred.');
    }

    return json;
  } catch (err) {
    console.error(`API Error [${method} ${endpoint}]:`, err);
    throw err;
  }
}

export function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${escapeHtml(message)}</span>
    <button style="background:transparent;color:var(--text-subtle);font-size:1.1rem;margin-left:8px;" onclick="this.parentElement.remove()">×</button>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

export function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>"']/g, m => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[m]);
}
