import { getSavedVisits, saveVisitRecord, clearAllData } from './mock_storage.js';

document.addEventListener('DOMContentLoaded', () => {
  const talkBtn = document.getElementById('talk-btn');
  const btnText = talkBtn.querySelector('.btn-text');
  const statusBadge = document.getElementById('status-badge');
  const dangerBanner = document.getElementById('danger-banner');
  const dangerMsg = document.getElementById('danger-msg');
  const transcriptBox = document.getElementById('transcript-box');
  const latencyVal = document.getElementById('latency-val');
  
  const fieldName = document.getElementById('field-name');
  const fieldAge = document.getElementById('field-age');
  const fieldSymptoms = document.getElementById('field-symptoms');
  const fieldAction = document.getElementById('field-action');
  
  const saveBtn = document.getElementById('save-btn');
  const clearBtn = document.getElementById('clear-storage-btn');
  const followupList = document.getElementById('followup-list');

  let ws = null;
  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;
  let startTime = 0;

  renderFollowups();
  connectWebSocket();

  // 1. Connect to Python WebSocket Server (Person A & B)
  function connectWebSocket() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/ws`;
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('Connected to ASHA Saathi Python Backend');
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleBackendMessage(data);
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
    };

    ws.onclose = () => {
      setTimeout(connectWebSocket, 3000);
    };
  }

  // 2. Push-to-Talk Event Listeners
  talkBtn.addEventListener('mousedown', startListening);
  talkBtn.addEventListener('mouseup', stopListening);
  talkBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startListening(); });
  talkBtn.addEventListener('touchend', (e) => { e.preventDefault(); stopListening(); });

  async function startListening() {
    if (isRecording) return;
    isRecording = true;
    startTime = performance.now();
    btnText.textContent = 'Listening...';
    talkBtn.style.background = 'linear-gradient(135deg, #ff2a85, #ffb703)';
    statusBadge.textContent = 'Listening';
    statusBadge.className = 'status-badge active';
    transcriptBox.innerHTML = '<em>Listening to voice notes...</em>';

    audioChunks = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(audioBlob);
        }
        // Stop all mic tracks to release hardware
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
    } catch (err) {
      console.error('Microphone access error:', err);
      alert('Microphone permission required for voice recording.');
      stopListeningUI();
    }
  }

  function stopListening() {
    if (!isRecording) return;
    isRecording = false;
    stopListeningUI();

    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
  }

  function stopListeningUI() {
    btnText.textContent = 'Hold to Speak';
    talkBtn.style.background = 'linear-gradient(135deg, var(--vibrant-pink), var(--marigold-orange))';
    statusBadge.textContent = 'Processing';
    statusBadge.className = 'status-badge speaking';
  }

  // 3. Handle messages returned from Python Backend
  function handleBackendMessage(data) {
    const latency = Math.round(performance.now() - startTime);
    latencyVal.textContent = latency;
    statusBadge.textContent = 'Ready';
    statusBadge.className = 'status-badge';

    if (data.transcript) transcriptBox.textContent = data.transcript;
    if (data.name) fieldName.value = data.name;
    if (data.age) fieldAge.value = data.age;
    if (data.symptoms) fieldSymptoms.value = data.symptoms;
    if (data.action) fieldAction.value = data.action;

    if (data.danger_flag) {
      dangerMsg.textContent = data.danger_reason || 'Danger sign detected! Immediate PHC referral required.';
      dangerBanner.classList.remove('hidden');
    } else {
      dangerBanner.classList.add('hidden');
    }
  }

  // 4. Save Record & Follow-up Tracker
  saveBtn.addEventListener('click', () => {
    const record = {
      name: fieldName.value.trim() || 'Synthetic Patient',
      age: fieldAge.value.trim() || 'Unspecified',
      symptoms: fieldSymptoms.value.trim() || 'None reported',
      action: fieldAction.value.trim() || 'Standard Follow-up',
      hasDangerSign: !dangerBanner.classList.contains('hidden')
    };

    saveVisitRecord(record);
    renderFollowups();
    resetForm();
    alert('Visit record saved securely!');
  });

  function renderFollowups() {
    const visits = getSavedVisits();
    followupList.innerHTML = '';

    if (visits.length === 0) {
      followupList.innerHTML = '<li class="empty-state">No saved visits yet. Complete a visit to track schedules.</li>';
      return;
    }

    visits.reverse().forEach(visit => {
      const li = document.createElement('li');
      const urgentBadge = visit.hasDangerSign ? ' 🚨 <strong style="color:var(--danger-red)">(PHC Referral)</strong>' : '';
      
      li.innerHTML = `
        <strong>${escapeHtml(visit.name)}</strong> (${escapeHtml(visit.age)}) ${urgentBadge}<br/>
        <small style="color:var(--text-muted)">📅 Saved: ${visit.timestamp} | Next Visit: In 14 Days</small><br/>
        <small style="color:var(--marigold-gold)">💉 Vaccine Schedule: TT-2 / IFA Supplement Check</small>
      `;
      followupList.appendChild(li);
    });
  }

  clearBtn.addEventListener('click', () => {
    if (confirm('Are you sure you want to delete all local synthetic data?')) {
      clearAllData();
      renderFollowups();
    }
  });

  function resetForm() {
    fieldName.value = '';
    fieldAge.value = '';
    fieldSymptoms.value = '';
    fieldAction.value = '';
    transcriptBox.innerHTML = '<em>Listening for voice input in Hindi/Regional mix...</em>';
    dangerBanner.classList.add('hidden');
  }

  function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
});