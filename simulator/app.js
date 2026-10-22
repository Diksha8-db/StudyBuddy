/**
 * StudyBuddy MCP Simulator - voice and live tool inspector client (refined)
 */
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);

  const state = {
    isListening: false,
    isSpeaking: false,
    isBusy: false,
    ttsEnabled: true,
    handsFree: false,
    activeSession: null,
    callCount: 0,
    recognition: null,
  };

  const el = {
    chat: $('chat-messages'),
    mic: $('mic-button'),
    form: $('text-input-form'),
    input: $('user-input'),
    viz: $('visualizer-container'),
    vizLabel: $('visualizer-label'),
    ttsBtn: $('tts-toggle-btn'),
    ttsOn: $('tts-icon-on'),
    ttsOff: $('tts-icon-off'),
    handsfreeBtn: $('handsfree-toggle-btn'),
    hud: $('quiz-hud'),
    hudTopic: $('quiz-hud-topic'),
    hudProgress: $('quiz-hud-progress'),
    hudFill: $('quiz-hud-fill'),
    hudQuestion: $('quiz-hud-question'),
    logs: $('inspector-logs'),
    empty: $('empty-state'),
    counter: $('call-counter'),
    clearBtn: $('clear-inspector-btn'),
    main: $('main-content'),
    inspectorBtn: $('inspector-toggle-btn'),
    closeInspectorBtn: $('close-inspector-btn'),
    tabChat: $('tab-btn-chat'),
    tabInspector: $('tab-btn-inspector'),
    mobileCounter: $('mobile-call-counter'),
    status: $('server-status'),
  };

  const sendBtn = el.form.querySelector('.send-button');

  // ---------------------------------------------------------------------
  // Server health
  // ---------------------------------------------------------------------
  async function checkHealth() {
    const label = el.status.querySelector('.status-label');
    try {
      const res = await fetch('/health', { cache: 'no-store' });
      if (!res.ok) throw new Error(res.status);
      el.status.classList.remove('status-down');
      label.textContent = 'MCP server connected';
    } catch (e) {
      el.status.classList.add('status-down');
      label.textContent = 'Server unreachable';
    }
  }

  // ---------------------------------------------------------------------
  // Speech recognition
  // ---------------------------------------------------------------------
  // ---------------------------------------------------------------------
  // Speech recognition with full-sentence buffering and silence debounce
  // ---------------------------------------------------------------------
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  let silenceTimer = null;
  let accumulatedTranscript = '';
  let utteranceDispatched = false;

  function setVizIdle() {
    if (!state.isSpeaking && !state.isListening) {
      el.viz.classList.remove('active');
      el.vizLabel.textContent = 'Mic ready';
    }
  }

  function commitSpeechUtterance() {
    if (silenceTimer) {
      clearTimeout(silenceTimer);
      silenceTimer = null;
    }
    const text = accumulatedTranscript.trim();
    accumulatedTranscript = '';

    if (state.recognition && state.isListening) {
      try {
        state.recognition.stop();
      } catch (e) {}
    }
    stopListening();

    if (text && !utteranceDispatched && !state.isBusy) {
      utteranceDispatched = true;
      el.input.value = '';
      handleUserUtterance(text);
    }
  }

  if (SR) {
    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = 'en-US';

    rec.onstart = () => {
      state.isListening = true;
      utteranceDispatched = false;
      accumulatedTranscript = '';
      if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
      }
      el.mic.classList.add('listening');
      el.mic.setAttribute('aria-pressed', 'true');
      el.viz.classList.add('active');
      el.vizLabel.textContent = 'Listening… speak your full answer';
    };

    rec.onresult = (e) => {
      let finalStr = '';
      let interimStr = '';
      for (let i = 0; i < e.results.length; ++i) {
        if (e.results[i].isFinal) {
          finalStr += e.results[i][0].transcript + ' ';
        } else {
          interimStr += e.results[i][0].transcript + ' ';
        }
      }
      const fullText = (finalStr + interimStr).trim();
      if (fullText) {
        accumulatedTranscript = fullText;
        el.input.value = fullText;
        el.vizLabel.textContent = 'Listening: "' + fullText + '"';

        // Reset silence timer on every spoken word/syllable
        if (silenceTimer) clearTimeout(silenceTimer);

        // When user pauses for 1.3 seconds of silence, commit the full sentence!
        silenceTimer = setTimeout(() => {
          commitSpeechUtterance();
        }, 1300);
      }
    };

    rec.onerror = (e) => {
      if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
      }
      stopListening();
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        el.vizLabel.textContent = 'Mic blocked. Allow microphone access or type instead.';
      } else if (e.error === 'no-speech') {
        if (accumulatedTranscript.trim()) {
          commitSpeechUtterance();
        } else {
          el.vizLabel.textContent = 'Did not catch that. Tap the mic to try again.';
        }
      }
    };

    rec.onend = () => {
      stopListening();
      // If recognition ended naturally with accumulated text, commit it
      if (accumulatedTranscript.trim() && !utteranceDispatched && !state.isBusy) {
        commitSpeechUtterance();
      }
    };

    state.recognition = rec;
  } else {
    el.vizLabel.textContent = 'Voice input is not supported here. Use the text box.';
    el.mic.disabled = true;
    el.mic.title = 'SpeechRecognition is not supported in this browser';
  }

  function startListening() {
    if (!state.recognition || state.isListening || state.isBusy) return;
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    accumulatedTranscript = '';
    utteranceDispatched = false;
    if (silenceTimer) clearTimeout(silenceTimer);
    try {
      state.recognition.start();
    } catch (e) {
      console.warn('Recognition start failed:', e);
    }
  }

  function stopListening() {
    state.isListening = false;
    el.mic.classList.remove('listening');
    el.mic.setAttribute('aria-pressed', 'false');
    setVizIdle();
  }

  el.mic.addEventListener('click', () => {
    if (state.isListening) {
      // If user clicks while speaking, commit immediately!
      if (accumulatedTranscript.trim()) {
        commitSpeechUtterance();
      } else {
        if (state.recognition) {
          try { state.recognition.stop(); } catch (e) {}
        }
        stopListening();
      }
    } else {
      startListening();
    }
  });

  // ---------------------------------------------------------------------
  // Text to speech
  // ---------------------------------------------------------------------
  let speakToken = 0;

  function maybeAutoListen() {
    if (state.handsFree && state.activeSession && !state.isBusy) {
      setTimeout(() => {
        if (!state.isBusy && !state.isSpeaking) {
          startListening();
        }
      }, 700);
    }
  }

  function speakText(text) {
    const clean = String(text || '').replace(/[*_#`]/g, '').trim();
    if (!state.ttsEnabled || !window.speechSynthesis || !clean) {
      maybeAutoListen(); // hands-free must still work when audio is muted
      return;
    }

    const token = ++speakToken;
    window.speechSynthesis.cancel();

    const u = new SpeechSynthesisUtterance(clean);
    u.rate = 1;
    u.pitch = 1;
    u.lang = 'en-US';
    const voice = window.speechSynthesis.getVoices().find(
      (v) => /Natural|Google|Samantha|Jenny/.test(v.name) && v.lang.startsWith('en')
    );
    if (voice) u.voice = voice;

    // Ignore stale events from an utterance that was cancelled by a newer one.
    u.onstart = () => {
      if (token !== speakToken) return;
      state.isSpeaking = true;
      el.viz.classList.add('active');
      el.vizLabel.textContent = 'Speaking…';
    };
    u.onend = () => {
      if (token !== speakToken) return;
      state.isSpeaking = false;
      setVizIdle();
      maybeAutoListen();
    };
    u.onerror = () => {
      if (token !== speakToken) return;
      state.isSpeaking = false;
      setVizIdle();
    };

    setTimeout(() => {
      if (token === speakToken) window.speechSynthesis.speak(u);
    }, 50);
  }

  // ---------------------------------------------------------------------
  // Chat rendering
  // ---------------------------------------------------------------------
  const ICON_USER =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
  const ICON_MIC =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="22"></line></svg>';

  function scrollChat() {
    el.chat.scrollTop = el.chat.scrollHeight;
  }

  function appendMessage(text, isUser) {
    const row = document.createElement('div');
    row.className = 'chat-message ' + (isUser ? 'user' : 'assistant');

    const avatar = document.createElement('div');
    avatar.className = 'avatar ' + (isUser ? 'user-avatar' : 'alexa-avatar');
    avatar.innerHTML = isUser ? ICON_USER : ICON_MIC;

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    const sender = document.createElement('div');
    sender.className = 'message-sender';
    sender.textContent = isUser ? 'You' : 'StudyBuddy (Alexa+)';

    const p = document.createElement('p');
    p.textContent = text;

    bubble.append(sender, p);

    if (!isUser) {
      const tag = document.createElement('div');
      tag.className = 'speech-tag';
      tag.textContent = state.ttsEnabled ? 'Spoken reply' : 'Audio muted';
      bubble.appendChild(tag);
    }

    row.append(avatar, bubble);
    el.chat.appendChild(row);
    scrollChat();
  }

  let typingRow = null;
  function showTyping() {
    hideTyping();
    typingRow = document.createElement('div');
    typingRow.className = 'chat-message assistant typing';
    typingRow.innerHTML =
      '<div class="avatar alexa-avatar">' + ICON_MIC + '</div>' +
      '<div class="message-bubble" aria-label="StudyBuddy is thinking"><span class="dots"><i></i><i></i><i></i></span></div>';
    el.chat.appendChild(typingRow);
    scrollChat();
  }
  function hideTyping() {
    if (typingRow) typingRow.remove();
    typingRow = null;
  }

  // ---------------------------------------------------------------------
  // MCP inspector
  // ---------------------------------------------------------------------
  function updateCounters() {
    el.counter.textContent = state.callCount + (state.callCount === 1 ? ' call' : ' calls');
    if (el.mobileCounter) el.mobileCounter.textContent = state.callCount;
  }

  function codeBlock(title, value) {
    const wrap = document.createDocumentFragment();
    const t = document.createElement('div');
    t.className = 'section-title';
    t.textContent = title;
    const pre = document.createElement('pre');
    pre.className = 'code-block';
    pre.textContent = JSON.stringify(value, null, 2);
    wrap.append(t, pre);
    return wrap;
  }

  function logMcpToolCall(call) {
    if (!call) return;
    if (el.empty) el.empty.classList.add('hidden');

    state.callCount += 1;
    updateCounters();

    const card = document.createElement('div');
    card.className = 'tool-call-card';

    const header = document.createElement('div');
    header.className = 'card-header';
    const badge = document.createElement('span');
    badge.className = 'tool-badge';
    badge.textContent = call.name;
    const latency = document.createElement('span');
    latency.className = 'latency-badge';
    latency.textContent = (call.latency_ms != null ? call.latency_ms : '–') + ' ms';
    header.append(badge, latency);

    const body = document.createElement('div');
    body.className = 'card-body';
    body.append(codeBlock('Arguments', call.arguments), codeBlock('MCP response', call.result));

    card.append(header, body);
    el.logs.insertBefore(card, el.logs.firstChild);
  }

  // ---------------------------------------------------------------------
  // Quiz / viva HUD
  // ---------------------------------------------------------------------
  function updateHud(s) {
    if (!s) {
      el.hud.classList.add('hidden');
      return;
    }
    el.hud.classList.remove('hidden');

    const total = Number(s.total_questions) || 0;
    const idx = Number(s.current_index) || 0;

    if (s.type === 'viva') {
      const diff = s.difficulty ? ' (' + s.difficulty + ')' : '';
      el.hudTopic.textContent = 'Viva: ' + (s.topic || 'Oral exam') + diff;
      el.hudProgress.textContent = s.is_follow_up
        ? 'Follow-up on question ' + idx + ' of ' + total
        : 'Question ' + idx + ' of ' + total;
    } else {
      el.hudTopic.textContent = 'Flashcard quiz';
      el.hudProgress.textContent = 'Question ' + idx + ' of ' + total;
    }

    const pct = total > 0 ? Math.min(100, Math.round((idx / total) * 100)) : 0;
    el.hudFill.style.width = pct + '%';
    el.hudQuestion.textContent = s.question || 'Say your answer…';
  }

  // ---------------------------------------------------------------------
  // Server communication
  // ---------------------------------------------------------------------
  function setBusy(busy) {
    state.isBusy = busy;
    sendBtn.disabled = busy;
    el.input.disabled = busy;
    if (busy) el.vizLabel.textContent = 'Calling MCP tool…';
    else if (!state.isListening && !state.isSpeaking) el.vizLabel.textContent = 'Mic ready';
  }

  async function handleUserUtterance(message) {
    if (!message || state.isBusy) return;

    const s = state.activeSession;
    appendMessage(message, true);
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    speakToken++; // invalidate any pending speech

    const payload = {
      message,
      session_id: s ? s.session_id : null,
      card_id: s ? s.card_id : null,
      question: s ? s.question : null,
      is_follow_up: s ? Boolean(s.is_follow_up) : false,
      topic: s ? s.topic : null,
      difficulty: s ? s.difficulty : null,
      current_index: s ? s.current_index : 1,
      total_questions: s ? s.total_questions : 3,
    };

    setBusy(true);
    showTyping();

    try {
      const res = await fetch('/api/simulator/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Server returned ' + res.status);
      const data = await res.json();

      hideTyping();
      state.activeSession = data.active_session || null;
      updateHud(state.activeSession);

      const reply = data.reply || data.speech || 'Done.';
      appendMessage(reply, false);
      if (data.tool_call) logMcpToolCall(data.tool_call);
      setBusy(false);
      speakText(data.speech || reply);
    } catch (err) {
      console.error('Simulator request failed:', err);
      hideTyping();
      setBusy(false);
      appendMessage(
        'I could not reach the StudyBuddy server. Check that it is running, then try again.',
        false
      );
      checkHealth();
    }
  }

  // ---------------------------------------------------------------------
  // UI wiring
  // ---------------------------------------------------------------------
  el.form.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = el.input.value.trim();
    if (!text) return;
    el.input.value = '';
    handleUserUtterance(text);
  });

  document.querySelectorAll('.chip-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const prompt = btn.getAttribute('data-prompt');
      if (prompt) handleUserUtterance(prompt);
    });
  });

  el.ttsBtn.addEventListener('click', () => {
    state.ttsEnabled = !state.ttsEnabled;
    el.ttsOn.classList.toggle('hidden', !state.ttsEnabled);
    el.ttsOff.classList.toggle('hidden', state.ttsEnabled);
    el.ttsBtn.title = state.ttsEnabled ? 'Mute spoken replies' : 'Unmute spoken replies';
    el.ttsBtn.setAttribute('aria-pressed', String(!state.ttsEnabled));
    if (!state.ttsEnabled && window.speechSynthesis) {
      speakToken++;
      window.speechSynthesis.cancel();
      state.isSpeaking = false;
      setVizIdle();
    }
  });

  el.handsfreeBtn.addEventListener('click', () => {
    state.handsFree = !state.handsFree;
    el.handsfreeBtn.classList.toggle('active', state.handsFree);
    el.handsfreeBtn.setAttribute('aria-pressed', String(state.handsFree));
  });

  el.clearBtn.addEventListener('click', () => {
    el.logs.querySelectorAll('.tool-call-card').forEach((c) => c.remove());
    state.callCount = 0;
    updateCounters();
    if (el.empty) el.empty.classList.remove('hidden');
  });

  function setActiveTab(tab) {
    el.main.setAttribute('data-active-tab', tab);
    el.tabChat.classList.toggle('active', tab === 'chat');
    el.tabInspector.classList.toggle('active', tab === 'inspector');
  }

  el.inspectorBtn.addEventListener('click', () => {
    if (window.innerWidth <= 860) {
      setActiveTab('inspector');
    } else {
      const collapsed = el.main.classList.toggle('inspector-collapsed');
      el.inspectorBtn.classList.toggle('active', !collapsed);
    }
  });

  el.closeInspectorBtn.addEventListener('click', () => {
    if (window.innerWidth <= 860) {
      setActiveTab('chat');
    } else {
      el.main.classList.add('inspector-collapsed');
      el.inspectorBtn.classList.remove('active');
    }
  });

  el.tabChat.addEventListener('click', () => setActiveTab('chat'));
  el.tabInspector.addEventListener('click', () => setActiveTab('inspector'));

  if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
  }

  checkHealth();
  setInterval(checkHealth, 30000);
})();