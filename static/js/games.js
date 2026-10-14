// MentiNous AI — MentiExercise Hub Controller

import { apiRequest, showToast, escapeHtml } from './api.js';

let selectedSessionDuration = 5; // Default 5 minutes

export async function loadGamesHub() {
  // Duration Chips
  document.querySelectorAll('.duration-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.duration-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      selectedSessionDuration = parseInt(chip.dataset.duration);
      showToast(`Session length set to ${selectedSessionDuration} minutes.`, 'info');
    });
  });

  // Launch Game Buttons
  document.querySelectorAll('.btn-launch-game').forEach(btn => {
    btn.addEventListener('click', () => {
      const gameId = btn.dataset.game;
      // Requirement: Open every game in a new browser tab
      const url = `/game/${gameId}?duration=${selectedSessionDuration}`;
      window.open(url, '_blank');
    });
  });

  // Fetch Personal Bests from Database
  try {
    const data = await apiRequest('/games/scores');
    const bests = data.personal_bests || [];

    bests.forEach(item => {
      const scoreEl = document.getElementById(`pb-${item.game_id}`);
      if (scoreEl) {
        scoreEl.textContent = `${item.high_score.toLocaleString()} pts`;
      }
    });

    renderRecentGameHistory(data.recent_history || []);
  } catch (err) {
    console.error('Failed to load game scores:', err);
  }
}

function renderRecentGameHistory(history) {
  const container = document.getElementById('recent-game-history');
  if (!container) return;

  if (history.length === 0) {
    container.innerHTML = `
      <div style="text-align:center;padding:24px;color:var(--text-subtle);font-size:0.88rem;">
        No training sessions recorded yet. Launch a 5-minute mental workout to activate your neural focus!
      </div>
    `;
    return;
  }

  const gameNames = {
    'matrix-master': 'Matrix Master',
    'memory-shift': 'Memory Shift',
    'neurosprint': 'NeuroSprint',
    'star-dash': "Minty's Star Dash"
  };

  container.innerHTML = history.slice(0, 5).map(h => `
    <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:rgba(15,23,42,0.5);border-radius:8px;margin-bottom:6px;font-size:0.85rem;">
      <div>
        <strong style="color:var(--text-main);">${gameNames[h.game_id] || h.game_id}</strong>
        <span style="color:var(--text-muted);margin-left:8px;">Lvl ${h.level_reached} (${Math.round(h.duration_sec / 60)}m)</span>
      </div>
      <div>
        <span style="color:var(--accent-teal);font-weight:700;">+${h.score} pts</span>
        <span style="color:var(--text-subtle);font-size:0.75rem;margin-left:8px;">${h.accuracy}% acc</span>
      </div>
    </div>
  `).join('');
}
