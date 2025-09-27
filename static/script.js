// ==============================
// script.js - CRM Church (final)
// ==============================

// Base da API
const baseUrl = 'https://nous-crm-church-v1.onrender.com';

// Estado da aplicação
const appState = {
  currentView: 'login', // 'login' | 'options' | 'form' | 'memberForm' | 'acolhidoForm' | 'whatsappLog' | 'statusLog' | 'iaTrainingPanel' | 'eventos'
  user: null,
};

// ------------------------------
// Utilitários
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

// Alguns botões no HTML usam onclick com ids antigos — mapeamos aqui
function toggleForm(anyId) {
  // Independente do argumento, voltamos ao menu de opções
  appState.currentView = 'options';
  updateUI();
}

// ------------------------------
// Painel de IA - estado/variáveis
// ------------------------------
let currentTeachQuestion = null;
let perguntasPendentes = []; // cache

// ------------------------------
// Navegação entre seções
// ------------------------------
function updateUI() {
  // Esconde tudo
  const all = [
    'loginContainer',
    'options',
    'formContainer',
    'memberFormContainer',
    'acolhidoFormContainer',
    'whatsappLog',
    'statusLog',
    'iaTrainingPanel',
    'eventosContainer',
  ];
  all.forEach(safeHide);

  // Exibe a seção conforme o estado
  switch (appState.currentView) {
    case 'login':
      safeShow('loginContainer');
      break;
    case 'options':
      safeShow('options');
      safeShow('infoCardsContainer');
      safeShow('showFormButton');
      safeShow('monitorStatusButton');
      safeShow('sendWhatsappButton');
      safeShow('showMemberFormButton');
      safeShow('showAcolhidoFormButton');
      safeShow('showIATrainingButton');
      safeShow('showCampaignButton');
      break;
    case 'form':
      safeShow('formContainer');
      break;
    case 'memberForm':
      safeShow('memberFormContainer');
      break;
    case 'acolhidoForm':
      safeShow('acolhidoFormContainer');
      break;
    case 'whatsappLog':
      safeShow('whatsappLog');
      break;
    case 'statusLog':
      safeShow('statusLog');
      break;
    case 'iaTrainingPanel':
      safeShow('iaTrainingPanel');
      break;
    case 'eventos':
      safeShow('eventosContainer');
      break;
    default:
      console.warn('Visão não reconhecida:', appState.currentView);
  }
}

// ------------------------------
// Login
// ------------------------------
function showLoginError(message) {
  const c = $('loginErrorContainer');
  if (!c) return;
  c.innerHTML = `<div class="error-message">${message}</div>`;
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
// Dashboard (cards)
// ------------------------------
function loadDashboardData() {
  fetch(`${baseUrl}/api/get-dashboard-data`)
    .then(r => r.json())
    .then(data => {
      const setText = (id, v) => { const el = $(id); if (el) el.textContent = v ?? '0'; };

      setText('totalVisitantes', data.totalVisitantes);
      setText('totalMembros', data.totalMembros);
      setText('totalhomensMembro', data.totalhomensMembro);
      setText('totalmulheresMembro', data.totalmulheresMembro);

      setText('discipuladosAtivos', data.discipuladosAtivos);
      setText('totalHomensDiscipulado', data.totalHomensDiscipulado);
      setText('totalMulheresDiscipulado', data.totalMulheresDiscipulado);

      setText('grupos_comunhao', data.grupos_comunhao);

      setText('totalHomens', data.Homens);
      setText('percentualHomens', (data.Homens_Percentual || 0) + '%');
      setText('totalMulheres', data.Mulheres);
      setText('percentualMulheres', (data.Mulheres_Percentual || 0) + '%');
    })
    .catch(err => console.error('Erro ao carregar dados do dashboard:', err));
}
setInterval(loadDashboardData, 1200000);

// ------------------------------
// Visitantes - Cadastro
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

// Corrigido: sempre prefixar /api/
function apiRequest(endpoint, method = 'GET', body = null) {
  const headers = { 'Content-Type': 'application/json' };
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  return fetch(`${baseUrl}/api/${endpoint}`, opts)
    .then(async response => {
      if (!response.ok) {
        let msg = 'Erro desconhecido';
        try {
          const e = await response.json();
          msg = e.message || e.error || msg;
        } catch(_) {}
        throw new Error(`Erro: ${response.status} - ${msg}`);
      }
      return response.json();
    });
}

function registerVisitor(visitorData) {
  apiRequest('register', 'POST', visitorData)
    .then(data => {
      alert(data.message || 'Registro realizado com sucesso!');
      const form = $('visitorForm');
      if (form) form.reset();
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
// Membros - Cadastro
// ------------------------------
function saveMember(event) {
  event.preventDefault();
  const data = {
    nome: $('memberName')?.value || '',
    telefone: $('memberPhone')?.value || '',
    email: $('memberEmail')?.value || '',
    data_nascimento: $('memberBirthday')?.value || '',
    cep: $('cep')?.value || '',
    bairro: $('memberNeighborhood')?.value || '',
    cidade: $('memberCity')?.value || '',
    estado: $('memberState')?.value || '',
    status_membro: $('memberStatus')?.value || 'ativo',
  };

  fetch(`${baseUrl}/api/membros`, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(data),
  })
    .then(r => r.json())
    .then(_ => {
      alert('Membro cadastrado com sucesso!');
      appState.currentView = 'options';
      updateUI();
    })
    .catch(err => {
      console.error('Erro ao cadastrar membro:', err);
      alert('Erro ao cadastrar membro!');
    });
}

// CEP auto-preenchimento
(function bindCEP() {
  const cepEl = $('cep');
  if (!cepEl) return;
  cepEl.addEventListener('blur', () => {
    const cep = (cepEl.value || '').replace(/\D/g, '');
    if (cep.length !== 8) {
      alert('Digite um CEP válido.');
      return;
    }
    fetch(`https://viacep.com.br/ws/${cep}/json/`)
      .then(r => r.json())
      .then(data => {
        if (data.erro) { alert('CEP não encontrado.'); return; }
        const bairroEl = $('memberNeighborhood');
        const cidadeEl = $('memberCity');
        const estadoEl = $('memberState');
        if (bairroEl) bairroEl.value = data.bairro || '';
        if (cidadeEl) cidadeEl.value = data.localidade || '';
        if (estadoEl) estadoEl.value = data.uf || '';
      })
      .catch(err => console.error('Erro ao buscar CEP:', err));
  });
})();

// ------------------------------
// Acolhido - Cadastro
// ------------------------------
function clearAcolhidoForm() {
  ['nome', 'telefone', 'situacao', 'observacao'].forEach(id => {
    const el = $(id); if (el) el.value = '';
  });
}

function handleAcolhidoFormSubmission(event) {
  event.preventDefault();
  const nome = $('nome')?.value || '';
  const telefone = $('telefone')?.value || '';
  const situacao = $('situacao')?.value || '';
  const observacao = $('observacao')?.value || '';
  const dataCadastro = new Date().toISOString();

  if (!nome || !telefone || !situacao) {
    alert('Por favor, preencha todos os campos obrigatórios.');
    return;
  }

  fetch(`${baseUrl}/api/acolhido`, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ nome, telefone, situacao, observacao, data_cadastro: dataCadastro }),
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        alert('Acolhido cadastrado com sucesso!');
        clearAcolhidoForm();
        appState.currentView = 'options';
        updateUI();
      } else {
        alert('Erro ao cadastrar acolhido.');
      }
    })
    .catch(err => {
      console.error('Erro ao enviar dados:', err);
      alert('Erro ao tentar cadastrar o acolhido.');
    });
}

// ------------------------------
// WhatsApp - Envio manual
// ------------------------------
function handleWhatsappButtonClick() {
  if (!confirm('Deseja enviar a mensagem via WhatsApp?')) return;
  appState.currentView = 'whatsappLog';
  updateUI();
  fetchVisitorsAndSendMessagesManual();
}

function fetchVisitorsAndSendMessagesManual() {
  apiRequest('get_visitors')
    .then(data => {
      if (data.status !== 'success') throw new Error('Erro ao buscar visitantes.');
      const visitors = data.visitors || [];
      if (visitors.length === 0) { alert('Nenhum visitante encontrado.'); return; }
      const messages = visitors.map(v => ({
        phone: v.phone,
        ContentSid: 'HX45ac2c911363fad7a701f72b3ff7a2ce',
        template_name: 'boasvindasvisitantes',
        params: { visitor_name: v.name }
      }));
      sendMessagesManual(messages);
    })
    .catch(err => showError(`Erro ao buscar visitantes: ${err.message}`, 'logContainer'));
}

function sendMessagesManual(messages) {
  (messages || []).forEach(v => {
    apiRequest('send-message-manual', 'POST', {
      numero: v.phone,
      ContentSid: 'HX45ac2c911363fad7a701f72b3ff7a2ce',
      params: v.params
    })
      .then(data => {
        if (!data.success) throw new Error(data.error || 'Erro ao enviar mensagem.');
        alert('Mensagem enviada para ' + v.phone);
      })
      .catch(err => showError(`Erro ao enviar mensagens: ${err.message}`, 'logContainer'));
  });
}

// ------------------------------
// Monitorar Status
// ------------------------------
let currentPage = 1;
const itemsPerPage = 10;
let statusData = [];

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

function monitorStatus() {
  fetch(`${baseUrl}/api/monitor-status`, { method: 'GET', headers: { 'Content-Type': 'application/json' } })
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

function bindPagination() {
  const nextBtn = $('nextPageButton');
  const prevBtn = $('prevPageButton');
  if (nextBtn) nextBtn.addEventListener('click', () => {
    if (currentPage * itemsPerPage < statusData.length) {
      currentPage += 1;
      loadPageData(currentPage);
    }
  });
  if (prevBtn) prevBtn.addEventListener('click', () => {
    if (currentPage > 1) {
      currentPage -= 1;
      loadPageData(currentPage);
    }
  });
}

// ------------------------------
// IA - Painel
// ------------------------------
function loadPendingQuestions() {
  fetch(`${baseUrl}/api/ia/pending-questions`, { credentials: 'include' })
    .then(response => {
      if (!response.ok) {
        const ct = response.headers.get('content-type') || '';
        if (ct.includes('text/html')) {
          window.location.href = '/admin/integra/learn';
          return null;
        }
        throw new Error(`HTTP ${response.status}`);
      }
      return response.json();
    })
    .then(data => {
      if (!data) return;
      perguntasPendentes = data.questions || [];
      const list = $('pendingQuestionsList');
      const countEl = $('pendingQuestionsCount');
      if (!list || !countEl) return;
      list.innerHTML = '';
      countEl.textContent = perguntasPendentes.length;
      if (perguntasPendentes.length === 0) {
        list.innerHTML = '<li>Nenhuma pergunta pendente.</li>';
        return;
      }
      perguntasPendentes.forEach((q, idx) => {
        const li = document.createElement('li');
        li.textContent = q.question || q.pergunta || '(sem texto)';
        li.dataset.index = String(idx);
        li.addEventListener('click', () => showTeachForm(idx));
        list.appendChild(li);
      });
    })
    .catch(err => {
      console.error('Erro ao carregar perguntas pendentes:', err);
      const list = $('pendingQuestionsList');
      if (list) list.innerHTML = '<li>Erro ao carregar dados.</li>';
    });
}

function showTeachForm(index) {
  const question = perguntasPendentes[index];
  if (!question) return;
  currentTeachQuestion = question;

  const questionEl = $('teachQuestion');
  const answerEl = $('teachAnswer');
  const categoryEl = $('teachCategory');

  if (questionEl) questionEl.value = question.question || '';
  if (answerEl) answerEl.value = '';
  if (categoryEl) categoryEl.value = '';

  safeHide('trainingList');
  safeShow('teachForm');
}

function toggleTeachForm(show) {
  const f = $('teachForm');
  const l = $('trainingList');
  if (f) f.classList.toggle('hidden', !show);
  if (l) l.classList.toggle('hidden', !!show);
}

function handleTeachSubmit(event) {
  event.preventDefault();
  const answer = $('teachAnswer')?.value.trim();
  const category = $('teachCategory')?.value;
  if (!currentTeachQuestion || !answer || !category) {
    alert('Preencha resposta e categoria.');
    return;
  }
  const payload = {
    question: currentTeachQuestion.question,
    answer,
    category
  };
  fetch(`${baseUrl}/api/ia/teach`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    credentials: 'include'
  })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        alert('Erro: ' + data.error);
        return;
      }
      alert('IA ensinada com sucesso!');
      toggleTeachForm(false);
      loadPendingQuestions();
    })
    .catch(err => alert('Erro de conexão: ' + err));
}

// ------------------------------
// Campanhas de Eventos
// ------------------------------
let visitantesFiltrados = [];

function renderResultadoVisitantes(lista) {
  const cont = $('resultadoVisitantes');
  if (!cont) return;
  if (!lista || lista.length === 0) {
    cont.innerHTML = '<p>Nenhum visitante encontrado com esses filtros.</p>';
    return;
  }
  cont.innerHTML = `
    <p><strong>Total:</strong> ${lista.length}</p>
    <ul>${lista.map(v => `<li>${v.nome || v.name || '(Sem nome)'} — ${v.telefone || v.phone || ''}</li>`).join('')}</ul>
  `;
}

function handleFiltroVisitantesSubmit(event) {
  event.preventDefault();
  const data_inicio = $('dataInicio')?.value || '';
  const data_fim = $('dataFim')?.value || '';
  const idade_min = $('idadeMin')?.value || '';
  const idade_max = $('idadeMax')?.value || '';
  const genero = $('genero')?.value || '';

  fetch(`${baseUrl}/api/eventos/filtrar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data_inicio, data_fim, idade_min, idade_max, genero })
  })
    .then(r => r.json())
    .then(data => {
      if (data.status !== 'success') {
        alert('Erro ao filtrar: ' + (data.message || 'desconhecido'));
        return;
      }
      visitantesFiltrados = data.visitantes || [];
      renderResultadoVisitantes(visitantesFiltrados);
    })
    .catch(err => {
      console.error('Erro ao filtrar:', err);
      alert('Erro ao buscar visitantes.');
    });
}

function handleEnviarEventoSubmit(event) {
  event.preventDefault();
  const evento_nome = $('eventoNome')?.value || '';
  const mensagem = $('mensagemEvento')?.value || '';
  const imagem_url = $('imagemUrl')?.value || '';

  if (!evento_nome || !mensagem) {
    alert('Informe pelo menos nome do evento e a mensagem.');
    return;
  }
  if (!visitantesFiltrados || visitantesFiltrados.length === 0) {
    alert('Filtre e selecione visitantes antes de enviar.');
    return;
  }

  // Cria barra de progresso
  const cont = $('resultadoVisitantes');
  cont.innerHTML = `
    <div id="progressBarContainer" style="width:100%; background:#eee; border:1px solid #ccc; margin:10px 0;">
      <div id="progressBar" style="width:0%; height:25px; background:#28a745; text-align:center; color:#fff;">0%</div>
    </div>
  `;

  fetch(`${baseUrl}/api/eventos/enviar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      visitantes: visitantesFiltrados,
      evento_nome,
      mensagem,
      imagem_url
    })
  })
    .then(r => r.json())
    .then(data => {
      if (data.status !== 'success') {
        alert('Erro ao enviar campanha: ' + (data.message || 'desconhecido'));
        return;
      }

      // Atualiza a barra conforme enviados
      const enviados = data.enviados || [];
      const total = visitantesFiltrados.length;
      let count = 0;

      enviados.forEach((_, idx) => {
        count++;
        const pct = Math.round((count / total) * 100);
        const bar = $('progressBar');
        if (bar) {
          bar.style.width = pct + '%';
          bar.textContent = pct + '%';
        }
      });

      alert(`Campanha enviada para ${enviados.length} visitantes.`);
      appState.currentView = 'options';
      updateUI();
    })
    .catch(err => {
      console.error('Erro ao enviar campanha:', err);
      alert('Erro de conexão ao enviar campanha.');
    });
}


// ------------------------------
// Listeners / Boot
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

  const acolhidoForm = $('acolhidoForm');
  if (acolhidoForm) acolhidoForm.addEventListener('submit', handleAcolhidoFormSubmission);

  bindPagination();

  const filtroForm = $('filtroVisitantesForm');
  if (filtroForm) filtroForm.addEventListener('submit', handleFiltroVisitantesSubmit);

  const enviarEventoForm = $('enviarEventoForm');
  if (enviarEventoForm) enviarEventoForm.addEventListener('submit', handleEnviarEventoSubmit);
}

document.addEventListener('DOMContentLoaded', () => {
  initializeEventListeners();
  updateUI();
  loadDashboardData();
});

