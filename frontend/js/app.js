/**
 * Hindi Voice Collection Bot — Frontend Application Logic v3
 *
 * V3 Bug-Fix Pass:
 *  - Single canonical scrollToBottom() (duplicate removed)
 *  - Collapsible summary card (collapsed by default, toggle on click)
 *  - Input/mic/send hidden (not just disabled) after conversation completion
 *  - Wrong Person: stage progress shows only Wrong Person + Call Closed
 *  - Status banner shows "Conversation Completed" / "Call Finished" at end
 *  - Compact summary card at bottom of chat, expandable detail section
 *  - Page scroll locked; only chat-transcript scrolls
 */

// ─────────────────────────────────────────────────────────────────────────────
// Configuration
// ─────────────────────────────────────────────────────────────────────────────
const API_BASE = '';  // empty = same origin (FastAPI serves frontend)

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────
const state = {
  sessionId: null,
  stage: null,
  isComplete: false,
  isListening: false,
  isBotSpeaking: false,
  recognition: null,
  currentAudio: null,
  hasStarted: false,
  lastIntent: null,
  lastConfidence: null,
  micEnabled: false,
  silenceRetries: 0,
  paymentLinkShown: false,
  // Enterprise UX
  callStartTime: null,
  timerInterval: null,
  // Cached session data for summary card
  sessionCustomerName: '',
  sessionAmount: 0,
  sessionBank: '',
  sessionLlmProvider: 'Groq · Llama-3',
  // State machine guards
  isProcessing: false,
  isMicStarting: false,
  summaryCardShown: false,
  isWrongPerson: false,
};

// Human-readable intent labels
const INTENT_LABELS = {
  confirm:          'Confirmed',
  deny:             'Wrong Person',
  bank_query:       'Bank Query',
  amount_query:     'Amount Query',
  link_request:     'Link Request',
  busy_interrupt:   'User Busy',
  delay_promise:    'Promise to Pay',
  payment_accept:   'Accepted Payment',
  payment_decline:  'Declined Payment',
  who_are_you:      'Identity Query',
  proceed:          'Acknowledged',
  already_paid:     'Already Paid',
  angry_customer:   'Upset Customer',
  wrong_person:     'Wrong Person',
  unclear:          'Unclear',
};

const INTENT_COLORS = {
  confirm:          '#0e7c4a',
  deny:             '#b91c1c',
  bank_query:       '#1a56db',
  amount_query:     '#1a56db',
  link_request:     '#6d28d9',
  busy_interrupt:   '#b45309',
  delay_promise:    '#b45309',
  payment_accept:   '#0e7c4a',
  payment_decline:  '#b91c1c',
  who_are_you:      '#1a56db',
  proceed:          '#475569',
  already_paid:     '#0e7c4a',
  angry_customer:   '#b91c1c',
  wrong_person:     '#b91c1c',
  unclear:          '#94a3b8',
};

// Stage display names
const STAGE_LABELS = {
  awaiting_name_confirmation: 'Name Confirmation',
  amount_due_information:     'Amount Information',
  bank_information:           'Bank Identification',
  payment_offer:              'Payment Offer',
  conversation_completed:     'Completed ✓',
  wrong_person:               'Wrong Person',
};

const STAGE_ORDER = [
  'awaiting_name_confirmation',
  'amount_due_information',
  'bank_information',
  'payment_offer',
  'conversation_completed',
];

// ─────────────────────────────────────────────────────────────────────────────
// DOM References
// ─────────────────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const dom = {
  // Form
  customerName:     $('customer-name'),
  amountDue:        $('amount-due'),
  bankName:         $('bank-name'),
  paymentLink:      $('payment-link'),

  // Buttons
  startBtn:         $('start-btn'),
  resetBtn:         $('reset-btn'),
  micBtn:           $('mic-btn'),
  sendBtn:          $('send-btn'),
  textInput:        $('text-input'),

  // Chat
  chatTranscript:   $('chat-transcript'),
  emptyState:       $('empty-state'),

  // Input rows (for hide/show on completion)
  textInputRow:     document.querySelector('.text-input-row'),
  micSection:       document.querySelector('.mic-section'),

  // Status
  statusDot:        $('status-dot'),
  statusText:       $('status-text'),
  stageBadge:       $('stage-badge'),
  voiceStatus:      $('voice-status'),

  // Info panel
  sessionIdEl:      $('session-id-display'),
  sessionName:      $('session-name-display'),
  sessionAmount:    $('session-amount-display'),
  sessionBank:      $('session-bank-display'),

  // Stage progress
  stageSteps:       document.querySelectorAll('.stage-step'),

  // Toast
  toastContainer:   $('toast-container'),

  // Summary modal
  summaryModal:     $('summary-modal'),
  summaryContent:   $('summary-content'),
  summaryClose:     $('summary-close'),

  // Enterprise UX
  callBanner:       $('call-banner'),
  callTimer:        $('call-timer'),
  callMeta:         $('call-meta'),
  callStatusDot:    $('call-status-dot'),
  callStatusLabel:  $('call-status-label'),
  callCustomerName: $('call-customer-name'),
  voiceBadgeWrap:   $('voice-badge-wrap'),
  voiceBadge:       $('voice-badge'),
};

// ─────────────────────────────────────────────────────────────────────────────
// Toast Notifications
// ─────────────────────────────────────────────────────────────────────────────
function showToast(message, type = 'info', duration = 3500) {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  dom.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ─────────────────────────────────────────────────────────────────────────────
// Status Bar
// ─────────────────────────────────────────────────────────────────────────────
function setStatus(text, dotClass = 'idle') {
  dom.statusText.textContent = text;
  dom.statusDot.className = `status-dot ${dotClass}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Voice Status Badge
// ─────────────────────────────────────────────────────────────────────────────
function setVoiceBadge(type, text) {
  if (!dom.voiceBadgeWrap || !dom.voiceBadge) return;
  if (!type) {
    dom.voiceBadgeWrap.style.display = 'none';
    return;
  }
  dom.voiceBadgeWrap.style.display = 'block';
  dom.voiceBadge.className = `voice-badge ${type}`;
  dom.voiceBadge.textContent = text;
}

// ─────────────────────────────────────────────────────────────────────────────
// Call Timer
// ─────────────────────────────────────────────────────────────────────────────
function startCallTimer() {
  state.callStartTime = Date.now();
  if (state.timerInterval) clearInterval(state.timerInterval);
  state.timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - state.callStartTime) / 1000);
    const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
    const ss = String(elapsed % 60).padStart(2, '0');
    if (dom.callTimer) dom.callTimer.textContent = `${mm}:${ss}`;
  }, 1000);
}

function stopCallTimer() {
  if (state.timerInterval) {
    clearInterval(state.timerInterval);
    state.timerInterval = null;
  }
}

function getElapsedTime() {
  if (!state.callStartTime) return '00:00';
  const elapsed = Math.floor((Date.now() - state.callStartTime) / 1000);
  const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
  const ss = String(elapsed % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Tech Panel Toggle
// ─────────────────────────────────────────────────────────────────────────────
function toggleTechPanel() {
  const panel = $('tech-panel');
  const arrow = $('tech-arrow');
  if (!panel) return;
  const open = panel.style.display !== 'none';
  panel.style.display = open ? 'none' : 'block';
  if (arrow) arrow.textContent = open ? '▶' : '▼';
}

// ─────────────────────────────────────────────────────────────────────────────
// Stage Progress
// ─────────────────────────────────────────────────────────────────────────────
function setStage(stage) {
  console.log(`[DEBUG] Stage updated: ${stage}`);
  state.stage = stage;
  const label = STAGE_LABELS[stage] || stage;
  dom.stageBadge.textContent = label;
  updateStageProgress(stage);
}

function updateStageProgress(currentStage) {
  const steps = document.querySelectorAll('.stage-step');

  // Wrong person flow — only mark first step as Wrong Person, rest as closed
  if (currentStage === 'wrong_person') {
    state.isWrongPerson = true;
    steps.forEach((step, idx) => {
      step.classList.remove('active', 'done', 'wrong');
      if (idx === 0) {
        step.classList.add('wrong');
        step.querySelector('span').textContent = 'Wrong Person';
        step.querySelector('.step-icon').textContent = '✕';
      } else if (idx === 1) {
        step.classList.add('done');
        step.querySelector('span').textContent = 'Call Closed';
        step.querySelector('.step-icon').textContent = '✓';
      }
      // Remaining steps stay grey/invisible
    });
    return;
  }

  const currentIdx = STAGE_ORDER.indexOf(currentStage);
  steps.forEach((step, idx) => {
    step.classList.remove('active', 'done', 'wrong');
    if (idx < currentIdx) step.classList.add('done');
    else if (idx === currentIdx) step.classList.add('active');
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Scroll Helper — single canonical function
// ─────────────────────────────────────────────────────────────────────────────
function scrollToBottom() {
  if (!dom.chatTranscript) return;
  requestAnimationFrame(() => {
    dom.chatTranscript.scrollTo({
      top: dom.chatTranscript.scrollHeight,
      behavior: 'smooth',
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat Transcript
// ─────────────────────────────────────────────────────────────────────────────
function hideEmptyState() {
  if (dom.emptyState) dom.emptyState.style.display = 'none';
}

function addMessage(role, text, extraHtml = '', intent = null, confidence = null) {
  hideEmptyState();
  const row = document.createElement('div');
  row.className = `message-row ${role}`;

  const time = new Date().toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit'
  });

  const avatarEmoji = role === 'bot' ? '🤖' : '👤';
  const label = role === 'bot' ? 'Bot' : 'You';

  // Intent badge for bot messages
  let intentBadgeHtml = '';
  if (role === 'bot' && intent && intent !== 'unclear') {
    const intentLabel = INTENT_LABELS[intent] || intent;
    const color = INTENT_COLORS[intent] || '#475569';
    const pct = confidence ? Math.round(confidence * 100) : null;
    intentBadgeHtml = `
      <div class="intent-badge" style="--badge-color:${color}">
        <span class="intent-tag">${intentLabel}</span>
        ${pct ? `<span class="confidence-bar"><span style="width:${pct}%"></span></span><span class="conf-pct">${pct}%</span>` : ''}
      </div>
    `;
  }

  row.innerHTML = `
    <div class="avatar ${role}">${avatarEmoji}</div>
    <div class="bubble-wrapper">
      <div class="bubble-meta">${label} · ${time}</div>
      <div class="bubble ${role}">${escapeHtml(text)}</div>
      ${extraHtml}
      ${intentBadgeHtml}
    </div>
  `;

  dom.chatTranscript.appendChild(row);
  scrollToBottom();
  return row;
}

function addThinkingIndicator() {
  hideEmptyState();
  const row = document.createElement('div');
  row.className = 'message-row bot';
  row.id = 'thinking-indicator';
  row.innerHTML = `
    <div class="avatar bot">🤖</div>
    <div class="bubble-wrapper">
      <div class="bubble thinking">
        <div class="dot-flashing"></div>
        <div class="dot-flashing"></div>
        <div class="dot-flashing"></div>
      </div>
    </div>
  `;
  dom.chatTranscript.appendChild(row);
  scrollToBottom();
}

function removeThinkingIndicator() {
  const el = document.getElementById('thinking-indicator');
  if (el) el.remove();
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(text));
  return div.innerHTML;
}

// ─────────────────────────────────────────────────────────────────────────────
// Audio Playback
// ─────────────────────────────────────────────────────────────────────────────
async function playAudio(audioUrl) {
  if (!audioUrl) return;

  if (state.currentAudio) {
    state.currentAudio.pause();
    state.currentAudio = null;
  }

  if (state.recognition && state.isListening) {
    try { state.recognition.abort(); } catch(e) {}
  }

  return new Promise((resolve) => {
    const audio = new Audio(audioUrl);
    state.currentAudio = audio;
    state.isBotSpeaking = true;
    dom.voiceStatus.textContent = '';
    dom.voiceStatus.className = 'voice-status';
    setVoiceBadge('vb-speaking', '🔊 Agent Speaking');
    setStatus('Bot speaking', 'active');

    audio.addEventListener('ended', () => {
      state.isBotSpeaking = false;
      state.currentAudio = null;
      dom.voiceStatus.textContent = '';
      dom.voiceStatus.className = 'voice-status';
      setVoiceBadge(null);
      if (!state.isComplete) {
        setStatus('Waiting for your response', 'idle');
        setVoiceBadge('vb-listening', '🎙 Listening...');
        enableInput();
        if (state.recognition && !state.isListening && state.micEnabled && !state.isMicStarting) {
          try {
            state.isMicStarting = true;
            state.recognition.start();
          } catch(e) {
            state.isMicStarting = false;
          }
        }
      }
      resolve();
    });

    audio.addEventListener('error', () => {
      state.isBotSpeaking = false;
      state.currentAudio = null;
      setVoiceBadge(null);
      if (!state.isComplete) enableInput();
      resolve();
    });

    audio.play().catch(err => {
      console.warn('Audio playback failed:', err);
      state.isBotSpeaking = false;
      if (!state.isComplete) enableInput();
      resolve();
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Input Enable / Disable / Hide
// ─────────────────────────────────────────────────────────────────────────────
function enableInput() {
  if (state.isComplete) return;
  dom.micBtn.disabled = false;
  dom.textInput.disabled = false;
  dom.sendBtn.disabled = false;
  dom.textInput.placeholder = 'Type your response or use the mic...';
}

function disableInput() {
  dom.micBtn.disabled = true;
  dom.textInput.disabled = true;
  dom.sendBtn.disabled = true;
}

/**
 * Called when conversation is fully complete.
 * Hides text input row, send button, and mic section entirely.
 */
function hideInputOnCompletion() {
  if (dom.textInputRow) dom.textInputRow.style.display = 'none';
  if (dom.micSection) dom.micSection.style.display = 'none';
}

// ─────────────────────────────────────────────────────────────────────────────
// Web Speech API — Speech Recognition (STT)
// ─────────────────────────────────────────────────────────────────────────────
const errorMessages = {
  'not-allowed':  'Microphone access denied. Please allow mic permissions.',
  'network':      'Network error. Check your connection.',
  'aborted':      'Microphone aborted.',
  'audio-capture':'No microphone found.',
  'service-not-allowed': 'Speech service blocked.',
};

function initSpeechRecognition() {
  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    showToast('Speech recognition not supported in this browser. Use Chrome.', 'error', 6000);
    dom.micBtn.disabled = true;
    dom.micBtn.title = 'Speech recognition not supported';
    return null;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = 'hi-IN';
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    state.isListening = true;
    state.isMicStarting = false;
    dom.micBtn.classList.add('recording');
    dom.micBtn.textContent = '⏹';
    dom.voiceStatus.textContent = '🎙 Listening... Speak now';
    dom.voiceStatus.className = 'voice-status listening';
    setStatus('Listening...', 'active');
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript.trim();
    if (transcript) {
      dom.textInput.value = transcript;
      processUserText(transcript);
    }
  };

  recognition.onerror = (event) => {
    if (event.error === 'no-speech') {
      state.silenceRetries++;
      if (state.silenceRetries <= 2) {
        dom.voiceStatus.textContent = `Still listening. Please respond. (${state.silenceRetries}/2)`;
        dom.voiceStatus.className = 'voice-status speaking';
      } else {
        showToast('Repeated silence. Mic paused. Click mic to resume.', 'warning');
        state.micEnabled = false;
        resetMicState();
      }
    } else {
      const msg = errorMessages[event.error] || `STT error: ${event.error}`;
      showToast(msg, 'error');
      state.micEnabled = false;
      state.isMicStarting = false;
      resetMicState();
    }
  };

  recognition.onend = () => {
    state.isMicStarting = false;
    if (state.micEnabled && !state.isBotSpeaking && !state.isComplete && state.silenceRetries <= 2) {
      try {
        state.isMicStarting = true;
        recognition.start();
      } catch (e) {
        state.isMicStarting = false;
        resetMicState();
      }
    } else {
      resetMicState();
    }
  };

  return recognition;
}

function resetMicState() {
  state.isListening = false;
  dom.micBtn.classList.remove('recording');
  dom.micBtn.textContent = '🎤';
  if (!state.isBotSpeaking && !state.isComplete) {
    if (!state.micEnabled || state.silenceRetries > 2) {
      dom.voiceStatus.textContent = 'Mic paused. Click to speak.';
      dom.voiceStatus.className = 'voice-status';
      setStatus('Waiting for you to click Mic', 'idle');
    } else {
      dom.voiceStatus.textContent = '';
      dom.voiceStatus.className = 'voice-status';
      setStatus('Waiting for your response', 'idle');
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// API Calls
// ─────────────────────────────────────────────────────────────────────────────
async function apiStartConversation(payload) {
  const resp = await fetch(`${API_BASE}/api/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || 'Failed to start conversation');
  }
  return resp.json();
}

async function apiProcessResponse(sessionId, userText) {
  const resp = await fetch(`${API_BASE}/api/respond`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, user_text: userText }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || 'Failed to process response');
  }
  return resp.json();
}

// ─────────────────────────────────────────────────────────────────────────────
// Start Conversation
// ─────────────────────────────────────────────────────────────────────────────
async function startConversation() {
  const name   = dom.customerName.value.trim();
  const amount = parseFloat(dom.amountDue.value);
  const bank   = dom.bankName.value.trim();
  const link   = dom.paymentLink.value.trim() || 'https://pay.example.com';

  if (!name || !bank) {
    showToast('Please enter Customer Name and Bank Name.', 'error');
    return;
  }
  if (!amount || amount <= 0) {
    showToast('Please enter a valid Amount Due.', 'error');
    return;
  }

  dom.startBtn.disabled = true;
  dom.startBtn.textContent = 'Starting...';
  disableInput();
  setStatus('Connecting...', 'active');

  // Ensure input rows are visible at start
  if (dom.textInputRow) dom.textInputRow.style.display = '';
  if (dom.micSection) dom.micSection.style.display = '';

  try {
    const data = await apiStartConversation({
      customer_name: name,
      amount_due:    amount,
      bank_name:     bank,
      payment_link:  link,
    });

    state.sessionId  = data.session_id;
    state.hasStarted = true;
    state.sessionCustomerName = name;
    state.sessionAmount = amount;
    state.sessionBank = bank;

    dom.sessionIdEl.textContent    = data.session_id;
    dom.sessionName.textContent    = name;
    dom.sessionAmount.textContent  = `₹${amount.toLocaleString('en-IN')}`;
    dom.sessionBank.textContent    = bank;

    dom.customerName.disabled = true;
    dom.amountDue.disabled    = true;
    dom.bankName.disabled     = true;
    dom.paymentLink.disabled  = true;

    dom.startBtn.style.display = 'none';
    dom.resetBtn.style.display = 'block';

    state.micEnabled = true;
    state.silenceRetries = 0;
    state.recognition = initSpeechRecognition();

    if (dom.callBanner) {
      dom.callCustomerName.textContent = name;
      dom.callMeta.textContent = `Session · ${data.session_id.slice(0, 8)}…`;
      dom.callStatusLabel.textContent = 'Live Conversation';
      dom.callBanner.style.display = 'flex';
    }
    startCallTimer();

    setStage(data.stage);
    setStatus('Bot speaking', 'active');
    setVoiceBadge('vb-speaking', '🔊 Agent Speaking');
    addMessage('bot', data.bot_response);

    if (data.audio_url) {
      await playAudio(data.audio_url);
    } else {
      enableInput();
    }

  } catch (err) {
    console.error('Start error:', err);
    showToast(`Error: ${err.message}`, 'error');
    dom.startBtn.disabled = false;
    dom.startBtn.textContent = 'Start Call';
    setStatus('Error — please retry', 'error');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Process User Input
// ─────────────────────────────────────────────────────────────────────────────
async function processUserText(text) {
  if (!text || state.isComplete || state.isBotSpeaking || state.isProcessing) return;

  state.isProcessing = true;

  if (state.recognition && state.isListening) {
    try { state.recognition.stop(); } catch(e) {}
  }

  state.silenceRetries = 0;
  dom.textInput.value = '';
  disableInput();
  addMessage('user', text);
  addThinkingIndicator();
  setVoiceBadge('vb-thinking', '🧠 Understanding...');
  setStatus('Processing...', 'active');

  try {
    setVoiceBadge('vb-generating', '💬 Generating Response...');
    const data = await apiProcessResponse(state.sessionId, text);
    removeThinkingIndicator();

    state.lastIntent     = data.intent || null;
    state.lastConfidence = data.confidence || null;

    // Track LLM provider used
    if (data.llm_provider) {
      state.sessionLlmProvider = data.llm_provider;
    }

    // Payment link card (shown once)
    let extraHtml = '';
    if (data.payment_link && !state.paymentLinkShown) {
      state.paymentLinkShown = true;
      const now = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
      extraHtml = `
        <div class="payment-success-card">
          <div class="psc-header">
            <div class="psc-title">
              <span class="psc-title-icon">✅</span>
              Payment Link Ready
            </div>
            <span class="psc-badge">Link Generated</span>
          </div>
          <div class="psc-subtitle">Payment link has been generated and is ready to share.</div>
          <div class="psc-link-row">
            <span class="psc-link-icon">🔗</span>
            <a href="${data.payment_link}" target="_blank" rel="noopener noreferrer">${data.payment_link}</a>
            <a class="psc-link-open" href="${data.payment_link}" target="_blank" rel="noopener noreferrer">Open ↗</a>
          </div>
          <div class="psc-footer">
            <div class="psc-status">
              <span class="psc-status-dot"></span> Ready to Use
            </div>
            <span>${now}</span>
          </div>
        </div>
      `;
    }

    // Add bot reply
    addMessage('bot', data.bot_response, extraHtml, data.intent, data.confidence);
    setStage(data.stage);

    // ── Conversation Complete ────────────────────────────────────────────────
    if (data.is_complete && !state.summaryCardShown) {
      state.isComplete = true;
      state.summaryCardShown = true;
      const isWrongPerson = (data.stage === 'wrong_person');
      state.isWrongPerson = isWrongPerson;

      stopCallTimer();
      const finalDuration = getElapsedTime();

      // Status bar
      setStatus('Conversation Completed', 'complete');
      setVoiceBadge('vb-done', '✅ Call Finished');

      // Call banner
      if (dom.callStatusDot) dom.callStatusDot.classList.add('ended');
      if (dom.callStatusLabel) dom.callStatusLabel.textContent = 'Call Finished';
      if (dom.callMeta) dom.callMeta.textContent = `Duration: ${finalDuration}`;

      // Determine outcome text
      const outcomeText = isWrongPerson
        ? '✕ Wrong Person — Call Closed'
        : (data.payment_link || state.paymentLinkShown)
          ? '✓ Payment Link Sent'
          : '✓ Conversation Concluded';

      const completedTime = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });

      // ── Compact summary card (collapsed by default) ──────────────────────
      const summaryCard = document.createElement('div');
      summaryCard.className = 'call-summary-card';
      summaryCard.id = 'call-summary-card';
      summaryCard.innerHTML = `
        <div class="cs-header">
          <span>📋 Call Summary</span>
          <span class="cs-time">${completedTime}</span>
        </div>
        <div class="cs-compact-grid">
          <div class="cs-item">
            <span class="cs-label">Customer</span>
            <span class="cs-value">${escapeHtml(state.sessionCustomerName)}</span>
          </div>
          <div class="cs-item">
            <span class="cs-label">Amount</span>
            <span class="cs-value yellow">₹${Number(state.sessionAmount).toLocaleString('en-IN')}</span>
          </div>
          <div class="cs-item">
            <span class="cs-label">Bank</span>
            <span class="cs-value">${escapeHtml(state.sessionBank)}</span>
          </div>
          <div class="cs-item">
            <span class="cs-label">Duration</span>
            <span class="cs-value">${finalDuration}</span>
          </div>
          <div class="cs-item">
            <span class="cs-label">Voice</span>
            <span class="cs-value blue">Edge TTS</span>
          </div>
          <div class="cs-item">
            <span class="cs-label">LLM</span>
            <span class="cs-value blue">Groq · Llama-3</span>
          </div>
        </div>
        <div class="cs-outcome">
          <span class="cs-outcome-label">Final Outcome</span>
          <span class="cs-outcome-value">${outcomeText}</span>
        </div>
        <button class="cs-detail-toggle" id="cs-detail-toggle" onclick="toggleSummaryDetail()">
          ▶ View Detailed Log
        </button>
        <div class="cs-detail-section" id="cs-detail-section" style="display:none;">
          <p class="cs-detail-loading">Loading…</p>
        </div>
      `;
      dom.chatTranscript.appendChild(summaryCard);

      // ── Completion footer: Start New Conversation button ─────────────────
      const footer = document.createElement('div');
      footer.className = 'completion-footer';
      footer.id = 'completion-footer';
      footer.innerHTML = `
        <span class="cf-label">✅ Conversation ended at ${completedTime}</span>
        <button class="btn btn-secondary cf-new-btn" onclick="resetConversation()">↺ Start New Conversation</button>
      `;
      dom.chatTranscript.appendChild(footer);
      scrollToBottom();

      // Hide input controls permanently
      hideInputOnCompletion();
      disableInput();
    }

    // Play audio
    if (data.audio_url) {
      await playAudio(data.audio_url);
    } else if (!data.is_complete) {
      enableInput();
    }

  } catch (err) {
    removeThinkingIndicator();
    console.error('Response error:', err);
    showToast(`Failed to process response: ${err.message}`, 'error');
    setStatus('Error — please retry', 'error');
    if (!state.isComplete) enableInput();
  } finally {
    state.isProcessing = false;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Collapsible Summary Detail
// ─────────────────────────────────────────────────────────────────────────────
let summaryDetailLoaded = false;

async function toggleSummaryDetail() {
  const section = $('cs-detail-section');
  const toggle  = $('cs-detail-toggle');
  if (!section || !toggle) return;

  const isOpen = section.style.display !== 'none';
  if (isOpen) {
    section.style.display = 'none';
    toggle.textContent = '▶ View Detailed Log';
    scrollToBottom();
    return;
  }

  section.style.display = 'block';
  toggle.textContent = '▼ Hide Detailed Log';

  if (!summaryDetailLoaded) {
    summaryDetailLoaded = true;
    try {
      const resp = await fetch(`${API_BASE}/api/session/${state.sessionId}/summary`);
      if (!resp.ok) throw new Error('Failed to fetch summary');
      const data = await resp.json();

      const logRows = (data.conversation_log || []).map(entry => {
        const ts = new Date(entry.timestamp).toLocaleTimeString('en-IN', {
          hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
        const intentLabel = INTENT_LABELS[entry.intent] || entry.intent;
        const pct = Math.round((entry.confidence || 0) * 100);
        return `
          <div class="log-entry">
            <div class="log-meta">${ts} &nbsp;|&nbsp; <span class="log-intent">${intentLabel}</span> <span class="log-conf">${pct}%</span></div>
            <div class="log-user">👤 ${escapeHtml(entry.user_message)}</div>
            <div class="log-bot">🤖 ${escapeHtml(entry.bot_response)}</div>
          </div>
        `;
      }).join('');

      const intentsHtml = (data.intents_detected || []).map(i =>
        `<span class="intent-chip" style="background:${INTENT_COLORS[i] || '#475569'}">${INTENT_LABELS[i] || i}</span>`
      ).join(' ');

      section.innerHTML = `
        <div class="cs-detail-inner">
          <div class="cs-detail-block">
            <div class="cs-detail-title">Intents Detected</div>
            <div class="intent-chips">${intentsHtml || '<span style="color:rgba(255,255,255,0.4)">None detected</span>'}</div>
          </div>
          <div class="cs-detail-block">
            <div class="cs-detail-title">Conversation Log (${data.turn_count || 0} turns · ${data.duration_seconds || 0}s)</div>
            <div class="log-list">${logRows || '<p style="color:rgba(255,255,255,0.4)">No log entries.</p>'}</div>
          </div>
        </div>
      `;
    } catch (err) {
      section.innerHTML = `<p class="cs-detail-error">Could not load log: ${err.message}</p>`;
    }
  }

  scrollToBottom();
}

// ─────────────────────────────────────────────────────────────────────────────
// Summary Modal (full-page, triggered from View Full Log)
// ─────────────────────────────────────────────────────────────────────────────
async function showSummary() {
  if (!state.sessionId) return;
  try {
    const resp = await fetch(`${API_BASE}/api/session/${state.sessionId}/summary`);
    if (!resp.ok) throw new Error('Failed to fetch summary');
    const data = await resp.json();

    const logRows = (data.conversation_log || []).map(entry => {
      const ts = new Date(entry.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      const intentLabel = INTENT_LABELS[entry.intent] || entry.intent;
      const pct = Math.round((entry.confidence || 0) * 100);
      return `
        <div class="log-entry">
          <div class="log-meta">${ts} &nbsp;|&nbsp; <span class="log-intent">${intentLabel}</span> <span class="log-conf">${pct}%</span></div>
          <div class="log-user">👤 ${escapeHtml(entry.user_message)}</div>
          <div class="log-bot">🤖 ${escapeHtml(entry.bot_response)}</div>
        </div>
      `;
    }).join('');

    const intentsHtml = (data.intents_detected || []).map(i =>
      `<span class="intent-chip" style="background:${INTENT_COLORS[i] || '#475569'}">${INTENT_LABELS[i] || i}</span>`
    ).join(' ');

    dom.summaryContent.innerHTML = `
      <div class="summary-grid">
        <div class="summary-item"><span>Customer</span><strong>${escapeHtml(data.customer_name)}</strong></div>
        <div class="summary-item"><span>Amount</span><strong>₹${data.amount_due.toLocaleString('en-IN')}</strong></div>
        <div class="summary-item"><span>Bank</span><strong>${escapeHtml(data.bank_name)}</strong></div>
        <div class="summary-item"><span>Status</span><strong>${data.is_complete ? '✅ Completed' : '🔄 In Progress'}</strong></div>
        <div class="summary-item"><span>Payment Link Sent</span><strong>${data.payment_link_sent ? '✅ Yes' : '❌ No'}</strong></div>
        <div class="summary-item"><span>Turns</span><strong>${data.turn_count}</strong></div>
        <div class="summary-item"><span>Duration</span><strong>${data.duration_seconds}s</strong></div>
      </div>
      <div class="summary-section">
        <div class="summary-section-title">Intents Detected</div>
        <div class="intent-chips">${intentsHtml || '<span style="color:#94a3b8">None</span>'}</div>
      </div>
      <div class="summary-section">
        <div class="summary-section-title">Conversation Log</div>
        <div class="log-list">${logRows || '<p style="color:#94a3b8">No log entries.</p>'}</div>
      </div>
    `;

    dom.summaryModal.style.display = 'flex';
  } catch (err) {
    showToast('Could not load summary: ' + err.message, 'error');
  }
}

function closeSummary() {
  if (dom.summaryModal) dom.summaryModal.style.display = 'none';
}

// ─────────────────────────────────────────────────────────────────────────────
// Mic Button
// ─────────────────────────────────────────────────────────────────────────────
function handleMicClick() {
  if (!state.recognition) {
    showToast('Speech recognition not available.', 'error');
    return;
  }
  if (state.isListening) {
    state.micEnabled = false;
    state.recognition.stop();
    resetMicState();
  } else if (!state.isComplete) {
    state.micEnabled = true;
    state.silenceRetries = 0;
    if (state.isBotSpeaking && state.currentAudio) {
      state.currentAudio.pause();
      state.isBotSpeaking = false;
      dom.voiceStatus.textContent = '';
      setStatus('Interrupted. Listening...', 'active');
    }
    try {
      state.recognition.start();
    } catch (e) {
      showToast('Could not start microphone. Please try again.', 'error');
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Text Input Send
// ─────────────────────────────────────────────────────────────────────────────
function handleSend() {
  const text = dom.textInput.value.trim();
  if (text && !state.isComplete) {
    if (state.isBotSpeaking && state.currentAudio) {
      state.currentAudio.pause();
      state.isBotSpeaking = false;
    }
    processUserText(text);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Reset Conversation
// ─────────────────────────────────────────────────────────────────────────────
function resetConversation() {
  if (state.currentAudio) {
    state.currentAudio.pause();
    state.currentAudio.src = '';
    state.currentAudio = null;
  }
  if (state.recognition) {
    state.micEnabled = false;
    try { state.recognition.abort(); } catch(e) {}
    state.recognition.onstart = null;
    state.recognition.onresult = null;
    state.recognition.onerror = null;
    state.recognition.onend = null;
    state.recognition = null;
  }
  stopCallTimer();

  state.sessionId           = null;
  state.stage               = null;
  state.isComplete          = false;
  state.isListening         = false;
  state.isBotSpeaking       = false;
  state.hasStarted          = false;
  state.paymentLinkShown    = false;
  state.callStartTime       = null;
  state.timerInterval       = null;
  state.sessionCustomerName = '';
  state.sessionAmount       = 0;
  state.sessionBank         = '';
  state.isProcessing        = false;
  state.isMicStarting       = false;
  state.summaryCardShown    = false;
  state.isWrongPerson       = false;
  state.lastIntent          = null;
  state.lastConfidence      = null;
  summaryDetailLoaded       = false;

  // Restore input rows visibility
  if (dom.textInputRow) dom.textInputRow.style.display = '';
  if (dom.micSection) dom.micSection.style.display = '';

  dom.chatTranscript.innerHTML = `
    <div class="empty-state" id="empty-state">
      <div class="icon">🏦</div>
      <p>Configure customer details and click<br><strong>Start Call</strong> to begin the voice session.</p>
    </div>
  `;
  dom.emptyState = $('empty-state');

  dom.customerName.disabled = false;
  dom.amountDue.disabled    = false;
  dom.bankName.disabled     = false;
  dom.paymentLink.disabled  = false;

  dom.startBtn.style.display  = 'block';
  dom.startBtn.disabled       = false;
  dom.startBtn.textContent    = '▶ Start Call';
  dom.resetBtn.style.display  = 'none';

  disableInput();
  setStatus('Ready to start', 'idle');
  dom.stageBadge.textContent    = 'Not started';
  dom.voiceStatus.textContent   = '';
  dom.voiceStatus.className     = 'voice-status';
  dom.sessionIdEl.textContent   = '—';
  dom.sessionName.textContent   = '—';
  dom.sessionAmount.textContent = '—';
  dom.sessionBank.textContent   = '—';
  dom.textInput.value           = '';
  dom.textInput.placeholder     = 'Start a call first...';

  closeSummary();
  setVoiceBadge(null);

  if (dom.callBanner) dom.callBanner.style.display = 'none';
  if (dom.callTimer)  dom.callTimer.textContent = '00:00';
  if (dom.callStatusDot) dom.callStatusDot.classList.remove('ended');
  if (dom.callStatusLabel) dom.callStatusLabel.textContent = 'Connecting';
  if (dom.callCustomerName) dom.callCustomerName.textContent = '—';
  if (dom.callMeta) dom.callMeta.textContent = 'Initializing…';

  // Reset stage steps text back to originals
  const stepLabels = ['Customer Verified', 'Amount Explained', 'Bank Info Shared', 'Payment Offered', 'Link Generated'];
  const stepIcons  = ['1', '2', '3', '4', '✓'];
  document.querySelectorAll('.stage-step').forEach((s, i) => {
    s.classList.remove('active', 'done', 'wrong');
    const span = s.querySelector('span');
    const icon = s.querySelector('.step-icon');
    if (span && stepLabels[i]) span.textContent = stepLabels[i];
    if (icon && stepIcons[i])  icon.textContent  = stepIcons[i];
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Event Listeners
// ─────────────────────────────────────────────────────────────────────────────
dom.startBtn.addEventListener('click', startConversation);
dom.resetBtn.addEventListener('click', resetConversation);
dom.micBtn.addEventListener('click', handleMicClick);
dom.sendBtn.addEventListener('click', handleSend);

if (dom.summaryClose) {
  dom.summaryClose.addEventListener('click', closeSummary);
}
if (dom.summaryModal) {
  dom.summaryModal.addEventListener('click', (e) => {
    if (e.target === dom.summaryModal) closeSummary();
  });
}

dom.textInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// Init
// ─────────────────────────────────────────────────────────────────────────────
(function init() {
  setStatus('Ready to start', 'idle');
  disableInput();
  dom.resetBtn.style.display = 'none';
  dom.textInput.placeholder  = 'Start a call first...';
  setVoiceBadge(null);
  console.log('AI Voice Collection System v3 — UI/UX Bug-Fix Pass loaded.');
})();
