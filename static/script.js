// ==============================
// script.js - CRM Church (final)
// ==============================

// Constantes
const baseUrl = 'https://nous-crm-church-v1.onrender.com';

// Estado da aplicação
const appState = {
  currentView: 'login', // 'login' | 'options' | 'form' | 'memberForm' | 'acolhidoForm' | 'whatsappLog' | 'statusLog' | 'iaTrainingPanel' | 'eventos'
  user: null,
};

// ------------------------------
// UTILITÁRIOS
// ------------------------------

function $(id) {
  return document.getElementById(id);
}

function safeShow(id) {
  const el = $(id);
  if (el) el.classList.remove('hidden');
}

function safeHide(id) {
  const el = $(id);
  if (el) el.classList.add('hidden');
}

// ------------------------------
// LOGGING
// ------------------------------

function appendLogToWhatsapp(message, isError = false) {
  const logContainer = document.getElementById("logContainer");
  if (!logContainer) return;

  const p = document.createElement("p");
  p.textContent = message;
  if (isError) {
    p.style.color = "red";
    p.style.fontWeight = "bold";
  }
  logContainer.appendChild(p);

  // Scroll automático para o fim
  logContainer.scrollTop = logContainer.scrollHeight;
}

// ------------------------------
// NAVEGAÇÃO ENTRE SEÇÕES
// ------------------------------

function updateUI() {
  const allContainers = [
    'loginContainer', 'options', 'formContainer', 'memberFormContainer', 'acolhidoFormContainer',
    'whatsappLog', 'statusLog', 'iaTrainingPanel', 'eventosContainer',
  ];
  
  allContainers.forEach(safeHide);

  const viewMap = {
    'login': 'loginContainer',
    'options': 'options',
    'form': 'formContainer',
    'memberForm': 'memberFormContainer',
    'acolhidoForm': 'acolhidoFormContainer',
    'whatsappLog': 'whatsappLog',
    'statusLog': 'statusLog',
    'iaTrainingPanel': 'iaTrainingPanel',
    'eventos': 'eventosContainer',
  };

  const view = viewMap[appState.currentView];
  if (view) safeShow(view);
  else console.warn('Visão não reconhecida:', appState.currentView);
}

// ------------------------------
// LOGIN
// ------------------------------

function showLoginError(message) {
  const container = $('loginErrorContainer');
  if (!container) return;
  container.innerHTML = `<div class="error-message">${message}</div>`;
}

function handleLogin(event) {
  if (event) event.preventDefault();

  const username = $('username')?.value || '';
  const password = $('password')?.value || '';

  fetch(`${baseUrl}/api/login`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ username, password }),
  })
  .then(res => {
    if (!res.ok) throw new Error('Falha ao autenticar');
    return res.json();
  })
  .then(data => {
    if (data.status === 'success') {
      try { localStorage.setItem('jwt_token', data.token); } catch(_) {}
      appState.user = username;
      appState.currentView = 'options';
      updateUI();
    } else {
      showLoginError(data.message || 'Usuário ou senha inválidos.');
    }
  })
  .catch(err => {
    console.error('Erro no login:', err);
    showLoginError('Erro ao tentar autenticar.');
  });
}

// ------------------------------
// DASHBOARD (cards)
// ------------------------------

function loadDashboardData() {
  fetch(`${baseUrl}/api/get-dashboard-data`)
    .then(r => r.json())
    .then(data => {
      const setText = (id, v) => { const el = $(id); if (el) el.textContent = v ?? '0'; };
      const dashboardData = [
        'totalVisitantes', 'totalMembros', 'totalhomensMembro', 'totalmulheresMembro', 
        'discipuladosAtivos', 'totalHomensDiscipulado', 'totalMulheresDiscipulado', 
        'grupos_comunhao', 'totalHomens', 'percentualHomens', 'totalMulheres', 'percentualMulheres'
      ];
      dashboardData.forEach(key => setText(key, data[key]));
    })
    .catch(err => console.error('Erro ao carregar dados do dashboard:', err));
}

setInterval(loadDashboardData, 1200000);

// ------------------------------
// VISITANTES - CADASTRO
// ------------------------------

function showError(message, containerId) {
  const c = $(containerId);
  if (!c) return;
  c.innerHTML = '';
  const div = document.createElement('div');
  div.className = 'error-message';
  div.textContent = message;
  c.appendChild(div);
}

function clearError() {
  const c = $('registerErrorContainer');
  if (c) c.innerHTML = '';
}

function validatePhoneNumber(phone) {
  const digits = (phone || '').replace(/\D/g, '');
  return digits.length === 11 ? digits : null;
}

function collectFormData() {
  const phoneInput = $('phone')?.value || '';
  const validPhone = validatePhoneNumber(phoneInput);
  if (!validPhone) {
    alert('Número inválido. Informe DDD + número (11 dígitos).');
    return null;
  }

  return {
    name: $('name')?.value || '',
    phone: validPhone,
    email: $('email')?.value || '',
    birthdate: $('birthdate')?.value || '',
    city: $('city')?.value || '',
    gender: $('gender')?.value || '',
    maritalStatus: $('maritalStatus')?.value || '',
    currentChurch: $('currentChurch')?.value || '',
    attendingChurch: $('attendingChurch')?.checked || false,
    referral: $('referral')?.value || '',
    membership: $('membership')?.checked || false,
    prayerRequest: $('prayerRequest')?.value || '',
    contactTime: document.querySelector('input[name="contactTime"]')?.value || $('contactTime')?.value || ''
  };
}

function validateForm(data) {
  return data && data.name && data.phone;
}

function registerVisitor(visitorData) {
  apiRequest('register', 'POST', visitorData)
    .then(data => {
      alert(data.message || 'Registro realizado com sucesso!');
      $('visitorForm')?.reset();
      clearError();
    })
    .catch(err => showError(`Erro ao registrar: ${err.message}`, 'registerErrorContainer'));
}

function handleFormSubmission(event) {
  event.preventDefault();
  const data = collectFormData();
  if (validateForm(data)) {
    registerVisitor(data);
  } else {
    alert('Por favor, preencha os campos obrigatórios corretamente.');
  }
}

// ------------------------------
// FUNÇÕES DE API
// ------------------------------

function apiRequest(endpoint, method = 'GET', body = null) {
  const headers = { 'Content-Type': 'application/json' };
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const cleanEndpoint = endpoint.replace(/^\/+/, '');
  const url = `${baseUrl}/api/${cleanEndpoint}`;

  return fetch(url, opts)
    .then(async response => {
      if (!response.ok) {
        let msg = 'Erro desconhecido';
        try {
          const e = await response.json();
          msg = e.message || e.error || msg;
        } catch (_) {}
        throw new Error(`Erro: ${response.status} - ${msg}`);
      }
      return response.json();
    });
}

// ------------------------------
// Acolhido
// ------------------------------

function clearAcolhidoForm() {
  ['nome', 'telefone', 'situacao', 'observacao'].forEach(id => {
    const el = $(id);
    if (el) el.value = '';
  });
}

// ------------------------------
// Monitor de Status
// ------------------------------

let currentPage = 1;
const itemsPerPage = 10;
let statusData = [];

function monitorStatus() {
  fetch(`${baseUrl}/api/monitor-status`, { 
    method: 'GET', 
    headers: { 'Content-Type': 'application/json' } 
  })
  .then(r => {
    if (!r.ok) throw new Error(`Erro ao buscar status: ${r.statusText}`);
    return r.json();
  })
  .then(data => {
    statusData = Array.isArray(data) ? data : [];
    appState.currentView = 'statusLog';
    updateUI();
    currentPage = 1;
    loadPageData(currentPage);
  })
  .catch(err => showError(`Erro ao buscar status: ${err.message}`, 'logContainer'));
}

function loadPageData(page) {
  const start = (page - 1) * itemsPerPage;
  const end = start + itemsPerPage;
  const items = statusData.slice(start, end);
  const tbody = $('statusList');
  if (!tbody) return;
  tbody.innerHTML = '';
  items.forEach(item => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${item.id}</td>
      <td>${item.name}</td>
      <td>${item.phone}</td>
      <td>${item.status}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ------------------------------
// WhatsApp
// ------------------------------

function handleWhatsappButtonClick() {
  if (!confirm('Deseja enviar mensagens de boas-vindas via WhatsApp (Z-API)?')) return;
  appState.currentView = 'whatsappLog';
  updateUI();
  fetchVisitorsAndSendMessagesManual();
}

function fetchVisitorsAndSendMessagesManual() {
  apiRequest('visitantes/fase-null')
    .then(data => {
      if (data.status !== 'success') throw new Error('Erro ao buscar visitantes.');
      const visitors = data.visitantes || [];

      const novos = visitors.filter(v => !v.fase && !v.status);
      if (novos.length === 0) {
        alert('Nenhum visitante novo encontrado para envio.');
        return;
      }

      const messages = novos.map(v => ({
        numero: v.telefone,
        mensagem: `👋 A Paz de Cristo, ${v.nome || "Visitante"}! Tudo bem com você?`
      }));

      sendMessagesSequentially(messages);
    })
    .catch(err => showError(`Erro ao buscar visitantes: ${err.message}`, 'logContainer'));
}

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function sendMessagesSequentially(messages, delayMs = 2000) {
  for (const v of (messages || [])) {
    try {
      appendLogToWhatsapp(`📤 Enviando para ${v.numero} (${v.name || "Visitante"})...`);

      const resp = await apiRequest('send-message-manual', 'POST', {
        numero: v.numero,
        mensagem: v.mensagem
      });

      if (!resp || !resp.success) throw new Error(resp?.error || 'Erro ao enviar mensagem.');

      appendLogToWhatsapp(`✅ Mensagem enviada para ${v.numero}`);
      await sleep(delayMs);
    } catch (err) {
      appendLogToWhatsapp(`❌ Erro ao enviar para ${v.numero}: ${err.message}`, true);
      await sleep(delayMs);
    }
  }
}

// ------------------------------
// IA - Perguntas Pendentes
// ------------------------------

let perguntasPendentes = [];

function loadPendingQuestions() {
  fetch(`${baseUrl}/api/ia/pending-questions`, { credentials: 'include' })
    .then(response => response.json())
    .then(data => {
      perguntasPendentes = data.questions || [];
      const list = $('pendingQuestionsList');
      const countEl = $('pendingQuestionsCount');
      if (list && countEl) {
        list.innerHTML = '';
        countEl.textContent = perguntasPendentes.length;
        if (perguntasPendentes.length === 0) {
          list.innerHTML = '<li>Nenhuma pergunta pendente.</li>';
        } else {
          perguntasPendentes.forEach((q, idx) => {
            const li = document.createElement('li');
            li.textContent = q.question || q.pergunta || '(sem texto)';
            li.dataset.index = String(idx);
            li.addEventListener('click', () => showTeachForm(idx));
            list.appendChild(li);
          });
        }
      }
    })
    .catch(err => {
      console.error('Erro ao carregar perguntas pendentes:', err);
      const list = $('pendingQuestionsList');
      if (list) list.innerHTML = '<li>Erro ao carregar dados.</li>';
    });
}

// ------------------------------
// INICIALIZAÇÃO
// ------------------------------

function initializeEventListeners() {
  const map = {
    'showFormButton': () => { appState.currentView = 'form'; updateUI(); },
    'showMemberFormButton': () => { appState.currentView = 'memberForm'; updateUI(); },
    'showAcolhidoFormButton': () => { clearAcolhidoForm(); appState.currentView = 'acolhidoForm'; updateUI(); },
    'monitorStatusButton': () => { monitorStatus(); },
    'sendWhatsappButton': () => { handleWhatsappButtonClick(); },
    'showIATrainingButton': () => { appState.currentView = 'iaTrainingPanel'; updateUI(); loadPendingQuestions(); },
    'showCampaignButton': () => { appState.currentView = 'eventos'; updateUI(); },

    'backToOptionsCadastroButton': () => { appState.currentView = 'options'; updateUI(); },
    'backToOptionsCadastroMembro': () => { appState.currentView = 'options'; updateUI(); },
    'backToOptionsCadastroAcolhido': () => { appState.currentView = 'options'; updateUI(); },
    'backToOptionsWhatsappButton': () => { appState.currentView = 'options'; updateUI(); },
    'backToOptionsStatusButton': () => { appState.currentView = 'options'; updateUI(); },
    'backToOptionsIAButton': () => { appState.currentView = 'options'; updateUI(); },
    'cancelTeachButton': () => { toggleTeachForm(false); safeShow('trainingList'); },

    'backToOptionsEvento': () => { appState.currentView = 'options'; updateUI(); },
  };

  Object.entries(map).forEach(([id, handler]) => {
    const el = $(id);
    if (!el) return;
    const eventType = el.tagName === 'FORM' ? 'submit' : 'click';
    el.addEventListener(eventType, handler);
  });

  const visitorForm = $('visitorForm');
  if (visitorForm) visitorForm.addEventListener('submit', handleFormSubmission);

  bindPagination();
}

document.addEventListener('DOMContentLoaded', () => {
  initializeEventListeners();
  updateUI();
  loadDashboardData();
});
