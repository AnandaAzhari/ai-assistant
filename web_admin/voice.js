const micButton = document.querySelector('#micButton');
const voiceStatus = document.querySelector('#voiceStatus');
const speakReplies = document.querySelector('#speakReplies');
const messageInput = document.querySelector('#messageInput');

const BrowserSpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition;
let listening = false;

if (BrowserSpeechRecognition) {
  recognition = new BrowserSpeechRecognition();
  recognition.lang = 'id-ID';
  recognition.interimResults = true;
  recognition.continuous = false;

  recognition.onstart = () => {
    listening = true;
    micButton.classList.add('listening');
    voiceStatus.textContent = 'Voice: mendengarkan...';
  };

  recognition.onresult = event => {
    let shown = '';
    let finalText = '';
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const text = event.results[i][0].transcript;
      shown += text;
      if (event.results[i].isFinal) finalText += text;
    }
    messageInput.value = shown.trim();
    if (finalText.trim() && window.taqiSendMessage) {
      window.taqiSendMessage(finalText.trim());
    }
  };

  recognition.onerror = event => {
    voiceStatus.textContent = `Voice: gagal (${event.error})`;
  };

  recognition.onend = () => {
    listening = false;
    micButton.classList.remove('listening');
    if (!voiceStatus.textContent.startsWith('Voice: gagal')) {
      voiceStatus.textContent = 'Voice: siap';
    }
  };

  micButton.addEventListener('click', () => {
    if (listening) recognition.stop();
    else recognition.start();
  });
  voiceStatus.textContent = 'Voice: siap';
} else {
  micButton.disabled = true;
  voiceStatus.textContent = 'Voice: speech recognition belum didukung browser ini';
}

window.addEventListener('taqi-reply', event => {
  if (!speakReplies.checked || !('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const voice = new SpeechSynthesisUtterance(event.detail);
  voice.lang = 'id-ID';
  window.speechSynthesis.speak(voice);
});
