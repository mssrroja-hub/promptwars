// MentiNous AI — Intelligent Assistant & Scheduling Controller

import { apiRequest, showToast, escapeHtml } from './api.js';

let activeProposal = null;
let speechRecognizer = null;
let isRecording = false;

export function initAIAssistant() {
  const inputEl = document.getElementById('ai-text-input');
  const sendBtn = document.getElementById('btn-ai-send');
  const voiceBtn = document.getElementById('btn-ai-voice');
  const conversation = document.getElementById('ai-chat-conversation');

  // 1. Web Speech API Voice Input Initialization
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    speechRecognizer = new SpeechRecognition();
    speechRecognizer.continuous = false;
    speechRecognizer.interimResults = false;
    speechRecognizer.lang = 'en-US';

    speechRecognizer.onstart = () => {
      isRecording = true;
      voiceBtn.classList.add('recording');
      showToast('Listening... Speak your commitments or schedule request.', 'info');
    };

    speechRecognizer.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      inputEl.value = transcript;
      showToast('Speech recognized!', 'success');
      handleAISend();
    };

    speechRecognizer.onerror = (event) => {
      console.warn('Speech recognition notice:', event.error);
      isRecording = false;
      voiceBtn.classList.remove('recording');
      if (event.error === 'not-allowed') {
        showToast('Microphone access denied. Please use text input.', 'warning');
      }
    };

    speechRecognizer.onend = () => {
      isRecording = false;
      voiceBtn.classList.remove('recording');
    };

    voiceBtn.addEventListener('click', () => {
      if (isRecording) {
        speechRecognizer.stop();
      } else {
        try {
          speechRecognizer.start();
        } catch {
          // Restart if busy
          speechRecognizer.stop();
        }
      }
    });
  } else {
    voiceBtn.title = 'Speech recognition not supported in this browser; please type.';
    voiceBtn.addEventListener('click', () => {
      showToast('Voice input is not supported in this browser. Please use text input.', 'warning');
    });
  }

  // 2. Text Input & Send
  async function handleAISend() {
    const text = inputEl.value.trim();
    if (!text) return;

    inputEl.value = '';
    appendMessage(text, 'user');

    // Show AI thinking indicator
    const thinkingBubble = document.createElement('div');
    thinkingBubble.className = 'chat-bubble ai';
    thinkingBubble.innerHTML = '<em>Analyzing request, detecting commitments, and optimizing schedule...</em>';
    conversation.appendChild(thinkingBubble);
    conversation.scrollTop = conversation.scrollHeight;

    try {
      let data;
      // If we already have an active proposal and the user gives an edit instruction
      if (activeProposal && (text.toLowerCase().includes('move') || text.toLowerCase().includes('hour') || text.toLowerCase().includes('light') || text.toLowerCase().includes('prioritize') || text.toLowerCase().includes('add'))) {
        data = await apiRequest('/ai/adjust', 'POST', {
          proposal_id: activeProposal.proposal_id,
          items: activeProposal.items,
          instruction: text
        });
      } else {
        data = await apiRequest('/ai/propose', 'POST', { prompt: text });
      }

      thinkingBubble.remove();
      activeProposal = data;
      renderProposalMessage(data);

    } catch (err) {
      thinkingBubble.remove();
      appendMessage(`Error optimizing schedule: ${err.message}`, 'ai');
    }
  }

  sendBtn.addEventListener('click', handleAISend);
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAISend();
    }
  });

  // Example Prompt Chips
  document.querySelectorAll('.ai-example-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      inputEl.value = chip.dataset.prompt;
      handleAISend();
    });
  });
}

function appendMessage(text, sender) {
  const conversation = document.getElementById('ai-chat-conversation');
  if (!conversation) return;

  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${sender}`;
  bubble.textContent = text;
  conversation.appendChild(bubble);
  conversation.scrollTop = conversation.scrollHeight;
}

function renderProposalMessage(data) {
  const conversation = document.getElementById('ai-chat-conversation');
  if (!conversation) return;

  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble ai';

  let conflictsHtml = '';
  if (data.conflicts && data.conflicts.length > 0) {
    conflictsHtml = `
      <div class="conflict-alert">
        <strong>⚠️ Conflict Advisory:</strong><br>
        ${data.conflicts.map(c => `• ${escapeHtml(c)}`).join('<br>')}
      </div>
    `;
  }

  const itemsHtml = (data.items || []).map(item => {
    const isFixed = item.type === 'fixed';
    const isDeadline = !!item.deadline;
    return `
      <div class="timeline-item ${isFixed ? 'fixed' : (isDeadline ? 'deadline' : '')}">
        <div class="timeline-time">${item.start_time ? item.start_time.split(' ')[1] : 'Flexible'} – ${item.end_time ? item.end_time.split(' ')[1] : ''}</div>
        <div class="timeline-details">
          <div class="timeline-title">${escapeHtml(item.title)}</div>
          <div class="timeline-meta">
            <span>${isFixed ? '🔒 Fixed Commitment' : '⚡ Task Block'} (${item.duration_min}m)</span>
            ${item.priority ? ` • Priority: <strong>${item.priority.toUpperCase()}</strong>` : ''}
            ${item.deadline ? ` • <span style="color:#fb7185">Due: ${item.deadline}</span>` : ''}
          </div>
        </div>
      </div>
    `;
  }).join('');

  bubble.innerHTML = `
    <div><strong>${escapeHtml(data.summary)}</strong></div>
    <div style="font-size:0.8rem;color:var(--accent-teal);margin-top:2px;">Engine: ${escapeHtml(data.mode)}</div>
    ${conflictsHtml}
    
    <div class="proposal-box">
      <h4>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
          <line x1="16" y1="2" x2="16" y2="6"/>
          <line x1="8" y1="2" x2="8" y2="6"/>
          <line x1="3" y1="10" x2="21" y2="10"/>
        </svg>
        Proposed Balanced Schedule
      </h4>
      <div class="proposal-timeline">
        ${itemsHtml}
      </div>

      <div style="font-size:0.85rem;color:var(--text-muted);margin-top:10px;">
        💡 <em>Review the proposed plan above. Tasks will only be saved to your schedule and calendar upon explicit approval.</em>
      </div>

      <div class="proposal-approval-actions">
        <button class="btn-primary btn-approve-schedule" id="btn-approve-schedule">
          ✓ Approve & Save Schedule
        </button>
        <button class="btn-secondary" id="btn-request-changes">
          ✏️ Request Changes
        </button>
      </div>

      <div class="quick-edit-chips" style="margin-top:12px;">
        <span style="font-size:0.75rem;color:var(--text-subtle);align-self:center;">Quick natural edits:</span>
        <button class="chip-btn quick-edit-chip" data-edit="Move Java to tomorrow">"Move Java to tomorrow"</button>
        <button class="chip-btn quick-edit-chip" data-edit="I need another hour for my assignment">"Need another hour"</button>
        <button class="chip-btn quick-edit-chip" data-edit="Make today's schedule lighter">"Make schedule lighter"</button>
        <button class="chip-btn quick-edit-chip" data-edit="Prioritize the upcoming deadline">"Prioritize deadline"</button>
      </div>
    </div>
  `;

  conversation.appendChild(bubble);
  conversation.scrollTop = conversation.scrollHeight;

  // Bind Approval
  bubble.querySelector('#btn-approve-schedule').addEventListener('click', async (e) => {
    const btn = e.target;
    btn.disabled = true;
    btn.textContent = 'Saving Schedule...';

    try {
      const res = await apiRequest('/ai/approve', 'POST', {
        proposal_id: data.proposal_id,
        items: data.items
      });
      showToast(res.message, 'success');
      bubble.querySelector('.proposal-approval-actions').innerHTML = `
        <div style="color:var(--accent-teal);font-weight:600;font-size:0.95rem;">
          ✨ Schedule Approved & Saved! Added to Tasks and Calendar.
        </div>
      `;
      activeProposal = null;
    } catch (err) {
      btn.disabled = false;
      btn.textContent = '✓ Approve & Save Schedule';
      showToast(err.message, 'error');
    }
  });

  // Bind Quick Edits
  bubble.querySelectorAll('.quick-edit-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.getElementById('ai-text-input').value = chip.dataset.edit;
      document.getElementById('btn-ai-send').click();
    });
  });

  bubble.querySelector('#btn-request-changes').addEventListener('click', () => {
    document.getElementById('ai-text-input').focus();
    showToast('Type how you would like to adjust the schedule (e.g. "Move Java to tomorrow").', 'info');
  });
}
