const input = document.querySelector('#messageInput');
const form = document.querySelector('#chatForm');
const messages = document.querySelector('#messages');
const palette = document.querySelector('#commandPalette');
const statusGrid = document.querySelector('#statusGrid');
const onlineBadge = document.querySelector('#onlineBadge');

const commands = [
  ['/status', 'Cek status sistem'],
  ['/bantuan', 'Lihat bantuan'],
  ['/saldo', 'Lihat saldo'],
  ['/akun', 'Lihat akun dan saldo awal'],
  ['/kategori', 'Lihat kategori yang sudah dipelajari'],
  ['/hari_ini', 'Laporan hari ini'],
  ['/bulan_ini', 'Laporan bulan ini'],
  ['/antrean', 'Lihat antrean TaqiDesk']
];

function bubble(role, text) {
  const item = document.createElement('article');
  item.className = `bubble ${role}`;
  const title = document.createElement('strong');
  title.textContent = role === 'user' ? 'Anda' : 'Lead Agent';
  const body = document.createElement('p');
  body.textContent = text;
  item.append(title, body);
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
}

async function sendMessage(text = input.value) {
  text = text.trim();
  if (!text) return;
  input.value = '';
  palette.classList.add('hidden');
  bubble('user', text);
  try {
    const response = await fetch('/api/message', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || 'Gagal');
    bubble('assistant', data.reply.text);
    window.dispatchEvent(new CustomEvent('taqi-reply', {detail: data.reply.text}));
  } catch (error) {
    bubble('error', `Koneksi gagal: ${error.message}`);
  }
}

form.addEventListener('submit', event => {
  event.preventDefault();
  sendMessage();
});

input.addEventListener('keydown', event => {
  // Enter mengirim pesan. Shift+Enter tetap membuat baris baru.
  // Saat IME/composition aktif, jangan memaksa submit.
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    sendMessage();
  }
});

input.addEventListener('input', () => {
  const value = input.value.trim().toLowerCase();
  if (!value.startsWith('/')) {
    palette.classList.add('hidden');
    return;
  }
  palette.replaceChildren();
  for (const [cmd, description] of commands.filter(([cmd]) => cmd.startsWith(value))) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'command-item';
    button.textContent = `${cmd} — ${description}`;
    button.onclick = () => sendMessage(cmd);
    palette.appendChild(button);
  }
  palette.classList.toggle('hidden', palette.children.length === 0);
});

async function loadStatus() {
  try {
    const response = await fetch('/api/status');
    const data = await response.json();
    onlineBadge.textContent = '● Online';
    onlineBadge.className = 'badge badge-ok';
    statusGrid.replaceChildren();
    for (const item of data.components) {
      const card = document.createElement('div');
      card.className = 'status-card';
      card.innerHTML = `<strong></strong><span></span>`;
      card.querySelector('strong').textContent = item.name;
      card.querySelector('span').textContent = item.status.replaceAll('_', ' ');
      statusGrid.appendChild(card);
    }
  } catch {
    onlineBadge.textContent = '● Offline';
    onlineBadge.className = 'badge badge-warn';
  }
}

window.taqiSendMessage = sendMessage;
loadStatus();
