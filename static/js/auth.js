// MentiNous AI — Authentication Controller

import { apiRequest, AuthState, showToast } from './api.js';

export function initAuth(onAuthSuccess) {
  const authScreen = document.getElementById('auth-screen');
  const tabLogin = document.getElementById('tab-btn-login');
  const tabSignup = document.getElementById('tab-btn-signup');
  const formLogin = document.getElementById('form-login');
  const formSignup = document.getElementById('form-signup');
  const authAlert = document.getElementById('auth-alert');

  function showAlert(msg, isError = true) {
    authAlert.textContent = msg;
    authAlert.className = `auth-alert ${isError ? 'error' : 'success'}`;
  }
  function hideAlert() {
    authAlert.style.display = 'none';
  }

  // Tab switching
  tabLogin.addEventListener('click', () => {
    tabLogin.classList.add('active');
    tabSignup.classList.remove('active');
    formLogin.style.display = 'flex';
    formSignup.style.display = 'none';
    hideAlert();
  });

  tabSignup.addEventListener('click', () => {
    tabSignup.classList.add('active');
    tabLogin.classList.remove('active');
    formSignup.style.display = 'flex';
    formLogin.style.display = 'none';
    hideAlert();
  });

  // Sign Up Form Submission
  formSignup.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideAlert();

    const name = document.getElementById('signup-name').value.trim();
    const email = document.getElementById('signup-email').value.trim();
    const password = document.getElementById('signup-password').value;
    const confirmPassword = document.getElementById('signup-confirm').value;

    if (!name || name.length < 2) {
      showAlert('Please enter your full name (at least 2 characters).');
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailRegex.test(email)) {
      showAlert('Please enter a valid email address.');
      return;
    }

    // STRICT 4-CHARACTER PASSWORD PROTOTYPE RULE
    if (!password || password.length !== 4) {
      showAlert('Prototype Requirement: Password must be exactly 4 characters.');
      return;
    }

    if (password !== confirmPassword) {
      showAlert('Passwords do not match. Please verify both fields.');
      return;
    }

    try {
      const data = await apiRequest('/auth/register', 'POST', {
        name,
        email,
        password,
        confirm_password: confirmPassword
      });

      AuthState.setToken(data.token);
      AuthState.setUser(data.user);
      showToast(`Welcome to MentiNous AI, ${data.user.name}!`, 'success');
      
      authScreen.style.display = 'none';
      if (onAuthSuccess) onAuthSuccess(data.user);
    } catch (err) {
      showAlert(err.message || 'Registration failed.');
    }
  });

  // Login Form Submission
  formLogin.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideAlert();

    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;

    if (!email || !password) {
      showAlert('Please enter your registered email and password.');
      return;
    }

    try {
      const data = await apiRequest('/auth/login', 'POST', {
        email,
        password
      });

      AuthState.setToken(data.token);
      AuthState.setUser(data.user);
      showToast(`Welcome back, ${data.user.name}!`, 'success');
      
      authScreen.style.display = 'none';
      if (onAuthSuccess) onAuthSuccess(data.user);
    } catch (err) {
      showAlert(err.message || 'Invalid email or password.');
    }
  });

  // Forgot Password Flow
  const forgotBtn = document.getElementById('btn-forgot-password');
  const recoveryModal = document.getElementById('modal-recovery');
  const recoveryForm = document.getElementById('form-recovery-request');
  const resetForm = document.getElementById('form-recovery-reset');
  const recoveryNotice = document.getElementById('recovery-notice');

  forgotBtn.addEventListener('click', (e) => {
    e.preventDefault();
    recoveryModal.classList.add('active');
    recoveryForm.style.display = 'flex';
    resetForm.style.display = 'none';
    recoveryNotice.style.display = 'none';
  });

  recoveryForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('recovery-email').value.trim();
    try {
      const res = await apiRequest('/auth/forgot-password', 'POST', { email });
      recoveryNotice.style.display = 'block';
      recoveryNotice.innerHTML = `
        <strong>${res.message}</strong><br>
        <span style="color:var(--accent-teal);font-size:0.95rem;display:inline-block;margin-top:6px;">
          Development Mode: Your recovery code is <strong>${res.dev_recovery_code || '123456'}</strong>
        </span>
      `;
      // Show reset fields
      document.getElementById('reset-email-hidden').value = email;
      if (res.dev_recovery_code) {
        document.getElementById('reset-code').value = res.dev_recovery_code;
      }
      recoveryForm.style.display = 'none';
      resetForm.style.display = 'flex';
    } catch (err) {
      showToast(err.message, 'error');
    }
  });

  resetForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('reset-email-hidden').value;
    const recovery_code = document.getElementById('reset-code').value.trim();
    const new_password = document.getElementById('reset-password').value;
    const confirm_password = document.getElementById('reset-confirm').value;

    if (new_password.length !== 4) {
      showToast('New password must be exactly 4 characters.', 'error');
      return;
    }

    if (new_password !== confirm_password) {
      showToast('Passwords do not match.', 'error');
      return;
    }

    try {
      await apiRequest('/auth/reset-password', 'POST', {
        email,
        recovery_code,
        new_password,
        confirm_password
      });

      showToast('Password updated! You can now log in.', 'success');
      recoveryModal.classList.remove('active');
      tabLogin.click();
    } catch (err) {
      showToast(err.message, 'error');
    }
  });

  // Check existing session
  return checkSession(onAuthSuccess);
}

export async function checkSession(onAuthSuccess) {
  const authScreen = document.getElementById('auth-screen');
  const token = AuthState.getToken();

  if (!token) {
    authScreen.style.display = 'flex';
    return null;
  }

  try {
    const data = await apiRequest('/auth/me');
    AuthState.setUser(data.user);
    authScreen.style.display = 'none';
    if (onAuthSuccess) onAuthSuccess(data.user);
    return data.user;
  } catch {
    AuthState.clearToken();
    AuthState.clearUser();
    authScreen.style.display = 'flex';
    return null;
  }
}

export async function logout() {
  try {
    await apiRequest('/auth/logout', 'POST');
  } catch {
    // ignore
  }
  AuthState.clearToken();
  AuthState.clearUser();
  window.location.reload();
}
