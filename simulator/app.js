/**
 * StudyBuddy MCP Simulator - Voice & Live Tool Inspector Client
 */

(function () {
  'use strict';

  // State Management
  const state = {
    isListening: false,
    isSpeaking: false,
    ttsEnabled: true,
    handsFree: false,
    activeSession: null, // { session_id, card_id, total_questions, current_index, question }
    callCount: 0,
    recognition: null,
  };

  // DOM Elements
  const chatMessages = document.getElementById('chat-messages');
  const micButton = document.getElementById('mic-button');
  const textInputForm = document.getElementById('text-input-form');
  const userInput = document.getElementById('user-input');
  const visualizerContainer = document.getElementById('visualizer-container');
  const visualizerLabel = document.getElementById('visualizer-label');
  const ttsToggleBtn = document.getElementById('tts-toggle-btn');
  const ttsIconOn = document.getElementById('tts-icon-on');
  const ttsIconOff = document.getElementById('tts-icon-off');
  const handsfreeToggleBtn = document.getElementById('handsfree-toggle-btn');
  const quizHud = document.getElementById('quiz-hud');
  const quizHudTopic = document.getElementById('quiz-hud-topic');
  const quizHudProgress = document.getElementById('quiz-hud-progress');
  const quizHudFill = document.getElementById('quiz-hud-fill');
  const quizHudQuestion = document.getElementById('quiz-hud-question');
  const inspectorLogs = document.getElementById('inspector-logs');
  const emptyState = document.getElementById('empty-state');
  const callCounter = document.getElementById('call-counter');
  const clearInspectorBtn = document.getElementById('clear-inspector-btn');

  // =========================================================================
  // Web Speech API: Speech Recognition Setup
  // =========================================================================

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (SpeechRecognition) {
    state.recognition = new SpeechRecognition();
    state.recognition.continuous = false;
    state.recognition.interimResults = false;
    state.recognition.lang = 'en-US';

    state.recognition.onstart = function () {
      state.isListening = true;
      micButton.classList.add('listening');
      visualizerContainer.classList.add('active');
      visualizerLabel.textContent = 'Listening to your voice...';
    };

    state.recognition.onresult = function (event) {
      const transcript = event.results[0][0].transcript;
      if (transcript && transcript.trim()) {
        handleUserUtterance(transcript.trim());
      }
    };

    state.recognition.onerror = function (event) {
      console.warn('Speech recognition event:', event.error);
      stopListening();
      if (event.error === 'not-allowed') {
        visualizerLabel.textContent = 'Mic permission denied';
      } else {
        visualizerLabel.textContent = 'Mic ready';
      }
    };

    state.recognition.onend = function () {
      stopListening();
    };
  } else {
    visualizerLabel.textContent = 'Speech STT not supported in browser. Use typing input.';
    micButton.style.opacity = '0.5';
    micButton.title = 'SpeechRecognition not supported in this browser';
  }

  function startListening() {
    if (!state.recognition) {
      alert('SpeechRecognition is not supported in this browser. Please use Google Chrome, Edge, or Safari, or use the text box.');
      return;
    }
    // Cancel any ongoing TTS speech before listening
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    try {
      state.recognition.start();
    } catch (e) {
      console.error('Failed to start recognition:', e);
    }
  }

  function stopListening() {
    state.isListening = false;
    micButton.classList.remove('listening');
    if (!state.isSpeaking) {
      visualizerContainer.classList.remove('active');
      visualizerLabel.textContent = 'Mic Ready';
    }
  }

  function toggleListening() {
    if (state.isListening) {
      if (state.recognition) state.recognition.stop();
      stopListening();
    } else {
      startListening();
    }
  }

  // =========================================================================
  // Web Speech API: Text-to-Speech (TTS)
  // =========================================================================

  function speakText(text) {
    if (!state.ttsEnabled || !window.speechSynthesis) return;

    window.speechSynthesis.cancel();

    // Remove any special formatting or markdown characters for speech
    const cleanSpeech = text.replace(/[*_#`[\]()]/g, '').trim();
    if (!cleanSpeech) return;

    const utterance = new SpeechSynthesisUtterance(cleanSpeech);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.lang = 'en-US';

    // Pick a natural English voice if available
    const voices = window.speechSynthesis.getVoices();
    const naturalVoice = voices.find(v => (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha') || v.name.includes('Jenny')) && v.lang.startsWith('en'));
    if (naturalVoice) {
      utterance.voice = naturalVoice;
    }

    state.isSpeaking = true;
    visualizerContainer.classList.add('active');
    visualizerLabel.textContent = 'StudyBuddy is speaking...';

    utterance.onend = function () {
      state.isSpeaking = false;
      visualizerContainer.classList.remove('active');
      visualizerLabel.textContent = 'Mic Ready';

      // If Hands-Free mode is enabled and a quiz is in progress, automatically listen for the answer
      if (state.handsFree && state.activeSession) {
        setTimeout(() => {
          startListening();
        }, 300);
      }
    };

    utterance.onerror = function () {
      state.isSpeaking = false;
      visualizerContainer.classList.remove('active');
      visualizerLabel.textContent = 'Mic Ready';
    };

    window.speechSynthesis.speak(utterance);
  }

  // =========================================================================
  // Chat Message Rendering
  // =========================================================================

  function appendMessage(sender, text, isUser = false) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${isUser ? 'user' : 'assistant'}`;

    const avatarDiv = document.createElement('div');
    avatarDiv.className = `avatar ${isUser ? 'user-avatar' : 'alexa-avatar'}`;
    if (isUser) {
      avatarDiv.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
          <circle cx="12" cy="7" r="4"></circle>
        </svg>
      `;
    } else {
      avatarDiv.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
          <line x1="12" y1="19" x2="12" y2="22"></line>
        </svg>
      `;
    }

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    const senderHeader = document.createElement('div');
    senderHeader.className = 'message-sender';
    senderHeader.textContent = isUser ? 'You (Spoken Voice)' : 'StudyBuddy (Alexa+)';

    const textP = document.createElement('p');
    textP.textContent = text;

    bubble.appendChild(senderHeader);
    bubble.appendChild(textP);

    if (!isUser) {
      const tag = document.createElement('div');
      tag.className = 'speech-tag';
      tag.textContent = 'Spoken via Alexa+ TTS';
      bubble.appendChild(tag);
    }

    msgDiv.appendChild(avatarDiv);
    msgDiv.appendChild(bubble);
    chatMessages.appendChild(msgDiv);

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // =========================================================================
  // Live MCP Inspector Renderer
  // =========================================================================

  function logMcpToolCall(toolCall) {
    if (!toolCall) return;

    if (emptyState) {
      emptyState.classList.add('hidden');
    }

    state.callCount += 1;
    callCounter.textContent = `${state.callCount} Call${state.callCount === 1 ? '' : 's'}`;

    const card = document.createElement('div');
    card.className = 'tool-call-card';

    const header = document.createElement('div');
    header.className = 'card-header';

    const toolBadge = document.createElement('span');
    toolBadge.className = 'tool-badge';
    toolBadge.textContent = toolCall.name;

    const latencyBadge = document.createElement('span');
    latencyBadge.className = 'latency-badge';
    latencyBadge.textContent = `${toolCall.latency_ms} ms`;

    header.appendChild(toolBadge);
    header.appendChild(latencyBadge);

    const body = document.createElement('div');
    body.className = 'card-body';

    // Arguments Section
    const argsTitle = document.createElement('div');
    argsTitle.className = 'section-title';
    argsTitle.textContent = 'Arguments';

    const argsPre = document.createElement('pre');
    argsPre.className = 'code-block';
    argsPre.textContent = JSON.stringify(toolCall.arguments, null, 2);

    // Result Section
    const resultTitle = document.createElement('div');
    resultTitle.className = 'section-title';
    resultTitle.textContent = 'MCP Response';

    const resultPre = document.createElement('pre');
    resultPre.className = 'code-block';
    resultPre.textContent = JSON.stringify(toolCall.result, null, 2);

    body.appendChild(argsTitle);
    body.appendChild(argsPre);
    body.appendChild(resultTitle);
    body.appendChild(resultPre);

    card.appendChild(header);
    card.appendChild(body);

    inspectorLogs.insertBefore(card, inspectorLogs.firstChild);
  }

  // =========================================================================
  // Quiz HUD Updater
  // =========================================================================

  function updateQuizHud(session) {
    if (!session) {
      quizHud.classList.add('hidden');
      return;
    }

    quizHud.classList.remove('hidden');
    quizHudProgress.textContent = `Question ${session.current_index} of ${session.total_questions}`;

    const pct = Math.round((session.current_index / session.total_questions) * 100);
    quizHudFill.style.width = `${pct}%`;
    quizHudQuestion.textContent = session.question || 'Answer the question above...';
  }

  // =========================================================================
  // Server Communication
  // =========================================================================

  async function handleUserUtterance(messageText) {
    if (!messageText) return;

    appendMessage('user', messageText, true);

    const payload = {
      message: messageText,
      session_id: state.activeSession ? state.activeSession.session_id : null,
      card_id: state.activeSession ? state.activeSession.card_id : null,
    };

    visualizerLabel.textContent = 'Processing MCP Tool Call...';

    try {
      const response = await fetch('/api/simulator/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const data = await response.json();

      // Update quiz session state
      state.activeSession = data.active_session;
      updateQuizHud(state.activeSession);

      // Render assistant speech reply
      appendMessage('assistant', data.reply, false);

      // Log the MCP tool call to the live inspector
      if (data.tool_call) {
        logMcpToolCall(data.tool_call);
      }

      // Voice TTS output
      if (data.speech) {
        speakText(data.speech);
      }
    } catch (err) {
      console.error('Error contacting server:', err);
      appendMessage('assistant', "Sorry, I had trouble connecting to the StudyBuddy MCP server. Please make sure the server is running.", false);
    }
  }

  // =========================================================================
  // Event Listeners
  // =========================================================================

  micButton.addEventListener('click', toggleListening);

  textInputForm.addEventListener('submit', function (e) {
    e.preventDefault();
    const text = userInput.value.trim();
    if (text) {
      userInput.value = '';
      handleUserUtterance(text);
    }
  });

  // Quick Action Chips
  document.querySelectorAll('.chip-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      const prompt = this.getAttribute('data-prompt');
      if (prompt) {
        handleUserUtterance(prompt);
      }
    });
  });

  // TTS Toggle
  ttsToggleBtn.addEventListener('click', function () {
    state.ttsEnabled = !state.ttsEnabled;
    if (state.ttsEnabled) {
      ttsIconOn.classList.remove('hidden');
      ttsIconOff.classList.add('hidden');
      ttsToggleBtn.title = 'Mute Spoken Audio';
    } else {
      ttsIconOn.classList.add('hidden');
      ttsIconOff.classList.remove('hidden');
      ttsToggleBtn.title = 'Unmute Spoken Audio';
      if (window.speechSynthesis) window.speechSynthesis.cancel();
    }
  });

  // Hands-Free Toggle
  handsfreeToggleBtn.addEventListener('click', function () {
    state.handsFree = !state.handsFree;
    this.classList.toggle('active', state.handsFree);
  });

  // Clear Inspector Log
  clearInspectorBtn.addEventListener('click', function () {
    inspectorLogs.innerHTML = '';
    state.callCount = 0;
    callCounter.textContent = '0 Calls';
    if (emptyState) {
      emptyState.classList.remove('hidden');
      inspectorLogs.appendChild(emptyState);
    }
  });

  // Initialize Voices for SpeechSynthesis
  if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = () => {
      // Warm up voices list
      window.speechSynthesis.getVoices();
    };
  }

})();
