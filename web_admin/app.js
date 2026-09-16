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
  ['/sync_status', 'Cek status Google Sheets Sync'],
  ['/sync', 'Sinkronkan ledger ke Google Sheets'],
  ['/dokumen_status', 'Cek Document Agent dan DeepSeek'],
  ['/makalah', 'Mulai chat dengan Document Agent'],
  ['/dokumen_baru', 'Reset konteks Document Agent'],
  ['/antrean', 'Lihat antrean TaqiDesk']
];

let selectedCommandIndex = -1;

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

function commandItems() {
  return Array.from(palette.querySelectorAll('.command-item'));
}

function selectCommand(index) {
  const items = commandItems();
  if (!items.length) {
    selectedCommandIndex = -1;
    return;
  }
  selectedCommandIndex = ((index % items.length) + items.length) % items.length;
  items.forEach((item, itemIndex) => {
    const selected = itemIndex === selectedCommandIndex;
    item.classList.toggle('active', selected);
    item.setAttribute('aria-selected', selected ? 'true' : 'false');
  });
  items[selectedCommandIndex].scrollIntoView({block: 'nearest'});
}

function hidePalette() {
  selectedCommandIndex = -1;
  palette.classList.add('hidden');
}

async function sendMessage(text = input.value) {
  text = text.trim();
  if (!text) return;
  input.value = '';
  hidePalette();
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
  if (event.isComposing) return;

  const items = commandItems();
  const paletteOpen = !palette.classList.contains('hidden') && items.length > 0;

  if (paletteOpen && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
    event.preventDefault();
    const step = event.key === 'ArrowDown' ? 1 : -1;
    selectCommand(selectedCommandIndex < 0 ? (step > 0 ? 0 : items.length - 1) : selectedCommandIndex + step);
    return;
  }

  if (paletteOpen && event.key === 'Escape') {
    event.preventDefault();
    hidePalette();
    return;
  }

  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    if (paletteOpen && selectedCommandIndex >= 0) {
      const selected = commandItems()[selectedCommandIndex];
      const command = selected?.dataset.command;
      if (command) {
        sendMessage(command);
        return;
      }
    }
    sendMessage();
  }
});

input.addEventListener('input', () => {
  const value = input.value.trim().toLowerCase();
  if (!value.startsWith('/')) {
    hidePalette();
    return;
  }

  palette.replaceChildren();
  const matches = commands.filter(([cmd]) => cmd.startsWith(value));
  for (const [cmd, description] of matches) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'command-item';
    button.dataset.command = cmd;
    button.setAttribute('role', 'option');
    button.setAttribute('aria-selected', 'false');
    button.textContent = `${cmd} — ${description}`;
    button.onclick = () => sendMessage(cmd);
    button.onmouseenter = () => {
      const items = commandItems();
      selectCommand(items.indexOf(button));
    };
    palette.appendChild(button);
  }

  const hasMatches = palette.children.length > 0;
  palette.classList.toggle('hidden', !hasMatches);
  if (hasMatches) selectCommand(0);
  else selectedCommandIndex = -1;
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
