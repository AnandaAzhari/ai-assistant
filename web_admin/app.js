const input = document.querySelector('#messageInput');
const form = document.querySelector('#chatForm');
const messages = document.querySelector('#messages');
const palette = document.querySelector('#commandPalette');
const agentStatusList = document.querySelector('#agentStatusList');
const serviceStatusList = document.querySelector('#serviceStatusList');
const onlineBadge = document.querySelector('#onlineBadge');
const appShell = document.querySelector('#appShell');
const sidebarToggle = document.querySelector('#sidebarToggle');
const sidebarClose = document.querySelector('#sidebarClose');
const sidebarScrim = document.querySelector('#sidebarScrim');
const newChatButton = document.querySelector('#newChatButton');
const activeAgentName = document.querySelector('#activeAgentName');
const activeAgentSubtitle = document.querySelector('#activeAgentSubtitle');
const activeAgentMark = document.querySelector('#activeAgentMark');

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
  ['/makalah_baru', 'Mulai makalah baru'],
  ['/antrean', 'Lihat antrean TaqiDesk']
];

const agentMeta = {
  lead: {name: 'Lead Agent', mark: 'L', subtitle: 'Orkestrasi dan routing'},
  finance: {name: 'Finance Agent', mark: 'F', subtitle: 'Keuangan dan ledger'},
  document: {name: 'Document Agent', mark: 'D', subtitle: 'Dokumen dan makalah · DeepSeek'},
  docutech: {name: 'TaqiDesk Agent', mark: 'T', subtitle: 'Operasional dan order'},
  taqidesk: {name: 'TaqiDesk Agent', mark: 'T', subtitle: 'Operasional dan order'}
};

let selectedCommandIndex = -1;

function metaFor(target = 'lead') {
  return agentMeta[target] || {name: 'Taqi AI', mark: 'T', subtitle: 'Smart Business Assistant'};
}

function setActiveAgent(target) {
  const meta = metaFor(target);
  activeAgentName.textContent = meta.name;
  activeAgentSubtitle.textContent = meta.subtitle;
  activeAgentMark.textContent = meta.mark;
}

function appendInline(parent, text) {
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) parent.append(document.createTextNode(text.slice(last, match.index)));
    const token = match[0];
    if (token.startsWith('**')) {
      const strong = document.createElement('strong');
      strong.textContent = token.slice(2, -2);
      parent.append(strong);
    } else {
      const code = document.createElement('code');
      code.textContent = token.slice(1, -1);
      parent.append(code);
    }
    last = match.index + token.length;
  }
  if (last < text.length) parent.append(document.createTextNode(text.slice(last)));
}

function renderMarkdownSafe(container, text) {
  const lines = String(text || '').replace(/\r\n/g, '\n').split('\n');
  let list = null;
  let listType = '';

  function closeList() {
    list = null;
    listType = '';
  }

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (!line.trim()) {
      closeList();
      continue;
    }

    if (/^\[Model:\s/i.test(line.trim())) {
      closeList();
      const meta = document.createElement('p');
      meta.className = 'model-meta';
      meta.textContent = line.trim();
      container.append(meta);
      continue;
    }

    const ordered = line.match(/^\s*\d+\.\s+(.+)$/);
    const unordered = line.match(/^\s*[-*]\s+(.+)$/);
    if (ordered || unordered) {
      const type = ordered ? 'ol' : 'ul';
      if (!list || listType !== type) {
        list = document.createElement(type);
        listType = type;
        container.append(list);
      }
      const item = document.createElement('li');
      appendInline(item, (ordered || unordered)[1]);
      list.append(item);
      continue;
    }

    closeList();
    const paragraph = document.createElement('p');
    appendInline(paragraph, line);
    container.append(paragraph);
  }
}

function bubble(role, text, agentName = 'Lead Agent', mark = 'L') {
  const item = document.createElement('article');
  item.className = `bubble ${role}`;

  const heading = document.createElement('div');
  heading.className = 'bubble-heading';
  const avatar = document.createElement('span');
  avatar.className = 'bubble-avatar';
  avatar.textContent = role === 'user' ? 'A' : mark;
  const title = document.createElement('strong');
  title.textContent = role === 'user' ? 'Anda' : agentName;
  heading.append(avatar, title);

  const body = document.createElement('div');
  body.className = 'bubble-content';
  renderMarkdownSafe(body, text);

  item.append(heading, body);
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
}

function addWelcome() {
  messages.replaceChildren();
  const watermark = document.createElement('div');
  watermark.className = 'empty-brand';
  watermark.setAttribute('aria-hidden', 'true');
  const logo = document.createElement('img');
  logo.src = '/taqi-ai.svg';
  logo.alt = '';
  watermark.append(logo);
  messages.append(watermark);
  bubble('assistant', 'Web Admin siap. Ketik `/` untuk melihat perintah atau pilih agent dari sidebar.', 'Lead Agent', 'L');
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

function resetTextareaHeight() {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
}

async function sendMessage(text = input.value) {
  text = String(text || '').trim();
  if (!text) return;
  input.value = '';
  resetTextareaHeight();
  hidePalette();
  bubble('user', text, 'Anda', 'A');

  try {
    const response = await fetch('/api/message', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || 'Gagal');

    const target = data.reply.target || 'lead';
    const meta = metaFor(target);
    setActiveAgent(target);
    bubble('assistant', data.reply.text, meta.name, meta.mark);
    window.dispatchEvent(new CustomEvent('taqi-reply', {detail: data.reply.text}));
  } catch (error) {
    bubble('error', `Koneksi gagal: ${error.message}`, 'Sistem', '!');
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
  resetTextareaHeight();
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
    button.onmouseenter = () => selectCommand(commandItems().indexOf(button));
    palette.appendChild(button);
  }

  const hasMatches = palette.children.length > 0;
  palette.classList.toggle('hidden', !hasMatches);
  if (hasMatches) selectCommand(0);
  else selectedCommandIndex = -1;
});

function statusClass(status) {
  const value = String(status || '').toLowerCase().replaceAll('_', ' ');
  if (value.includes('aktif') || value.includes('siap')) return 'ok';
  if (value.includes('belum') || value.includes('error') || value.includes('gagal')) return 'warn';
  return '';
}

function statusIcon(name) {
  const icons = {
    'Lead Agent': 'L',
    'Finance Agent': 'F',
    'Document Agent': 'D',
    'TaqiDesk': 'T',
    'Google Sheets': 'G',
    'Telegram': '↗'
  };
  return icons[name] || name.slice(0, 1).toUpperCase();
}

function statusItem(item) {
  const row = document.createElement('div');
  row.className = 'status-item';

  const icon = document.createElement('span');
  icon.className = 'status-icon';
  icon.textContent = statusIcon(item.name);

  const copy = document.createElement('span');
  copy.className = 'status-copy';
  const name = document.createElement('strong');
  name.textContent = item.name;
  const status = document.createElement('span');
  status.textContent = String(item.status || '').replaceAll('_', ' ');
  copy.append(name, status);

  const dot = document.createElement('span');
  dot.className = `status-dot ${statusClass(item.status)}`.trim();
  row.append(icon, copy, dot);
  return row;
}

async function loadStatus() {
  try {
    const response = await fetch('/api/status');
    const data = await response.json();
    if (!data.ok) throw new Error('Status tidak tersedia');

    onlineBadge.textContent = '● Online';
    onlineBadge.className = 'badge badge-ok';
    agentStatusList.replaceChildren();
    serviceStatusList.replaceChildren();

    for (const item of data.components || []) {
      const isService = ['Google Sheets', 'Telegram'].includes(item.name);
      (isService ? serviceStatusList : agentStatusList).appendChild(statusItem(item));
    }
  } catch {
    onlineBadge.textContent = '● Offline';
    onlineBadge.className = 'badge badge-warn';
  }
}

function isMobileSidebar() {
  return window.matchMedia('(max-width: 900px)').matches;
}

function closeSidebar() {
  appShell.classList.remove('sidebar-open');
  if (!isMobileSidebar()) {
    appShell.classList.add('sidebar-collapsed');
    localStorage.setItem('taqiSidebarCollapsed', '1');
    sidebarToggle.setAttribute('aria-expanded', 'false');
  }
}

function toggleSidebar() {
  if (isMobileSidebar()) {
    appShell.classList.toggle('sidebar-open');
    sidebarToggle.setAttribute('aria-expanded', appShell.classList.contains('sidebar-open') ? 'true' : 'false');
    return;
  }
  const collapsed = appShell.classList.toggle('sidebar-collapsed');
  localStorage.setItem('taqiSidebarCollapsed', collapsed ? '1' : '0');
  sidebarToggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
}

sidebarToggle.addEventListener('click', toggleSidebar);
sidebarClose.addEventListener('click', () => appShell.classList.remove('sidebar-open'));
sidebarScrim.addEventListener('click', () => appShell.classList.remove('sidebar-open'));

newChatButton.addEventListener('click', async () => {
  addWelcome();
  setActiveAgent('lead');
  if (isMobileSidebar()) appShell.classList.remove('sidebar-open');
  try {
    await fetch('/api/message', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: '/dokumen_baru'})
    });
  } catch {
    // Reset visual tetap aman; Document Agent dapat direset manual jika backend sedang offline.
  }
  input.focus();
});

window.addEventListener('resize', () => {
  if (!isMobileSidebar()) appShell.classList.remove('sidebar-open');
});

if (!isMobileSidebar() && localStorage.getItem('taqiSidebarCollapsed') === '1') {
  appShell.classList.add('sidebar-collapsed');
  sidebarToggle.setAttribute('aria-expanded', 'false');
}

window.taqiSendMessage = sendMessage;
loadStatus();
resetTextareaHeight();
