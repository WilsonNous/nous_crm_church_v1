// ==============================
// script.js - CRM Church (final)
// ==============================

// Constantes
const baseUrl = 'https://nous-crm-church-v1.onrender.com';

// ------------------------------
// UTILITÁRIOS
// ------------------------------
function $(id){ return document.getElementById(id); }
function safeShow(id){ const el=$(id); if(el) el.classList.remove('hidden'); }
function safeHide(id){ const el=$(id); if(el) el.classList.add('hidden'); }

function getAuthHeaders(includeJson=true){
  const h = includeJson ? {'Content-Type':'application/json'} : {};
  const t = localStorage.getItem('jwt_token');
  if (t) h['Authorization'] = `Bearer ${t}`;
  return h;
}

async function apiRequest(endpoint, method='GET', body=null){
  const headers = getAuthHeaders(true);
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);
  const url = `${baseUrl}/api/${endpoint.replace(/^\/+/, '')}`;
  const res = await fetch(url, opts);
  if (!res.ok){
    let msg = 'Erro';
    try { const e = await res.json(); msg = e.message || e.error || msg; } catch(_){}
    throw new Error(`${res.status} - ${msg}`);
  }
  return res.json();
}

// ------------------------------
// LOG DE WHATSAPP (quando existir)
// ------------------------------
function appendLogToWhatsapp(message, isError=false){
  const logContainer = $('logContainer');
  if (!logContainer) return;
  const p = document.createElement('p');
  p.textContent = message;
  if (isError){ p.style.color='red'; p.style.fontWeight='bold'; }
  logContainer.appendChild(p);
  logContainer.scrollTop = logContainer.scrollHeight;
}

// ------------------------------
// LÓGICA SPA ANTIGA (opcional)
// ------------------------------
const appState = { currentView:'login', user:null };

function updateUI(){
  // Só use em páginas que realmente tenham os containers da SPA
  const sections = [
    'loginContainer','options','formContainer','memberFormContainer','acolhidoFormContainer',
    'whatsappLog','statusLog','iaTrainingPanel','eventosContainer'
  ];
  sections.forEach(safeHide);
  const map = {
    login:'loginContainer', options:'options', form:'formContainer',
    memberForm:'memberFormContainer', acolhidoForm:'acolhidoFormContainer',
    whatsappLog:'whatsappLog', statusLog:'statusLog', iaTrainingPanel:'iaTrainingPanel',
    eventos:'eventosContainer',
  };
  const id = map[appState.currentView];
  if (id) safeShow(id);
}
function toggleForm(){ appState.currentView='options'; updateUI(); }

// ------------------------------
// LOGIN (com redirecionamento p/ /app/menu)
// ------------------------------
function showLoginError(message){
  const c = $('loginErrorContainer');
  if (!c) return;
  c.innerHTML = `<div class="error-message">${message}</div>`;
}

async function handleLogin(event){
  if (event) event.preventDefault();
  const username = $('username')?.value || '';
  const password = $('password')?.value || '';
  if (!username || !password){ showLoginError('Preencha usuário e senha.'); return; }

  const payload = { username, password };

  try {
    // Tenta /api/login
    let res = await fetch(`${baseUrl}/api/login`, {
      method:'POST',
      headers:{ 'Content-Type':'application/json' },
      body: JSON.stringify(payload),
    });

    // Fallback /login (se aplicável)
    if (res.status === 404){
      res = await fetch(`${baseUrl}/login`, {
        method:'POST',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify(payload),
      });
    }

    if (!res.ok) throw new Error('Falha ao autenticar');
    const data = await res.json();

    if (data.status === 'success'){
      try { localStorage.setItem('jwt_token', data.token); } catch(_){}
      window.location.href = '/app/menu'; // ✅ pós-login
    } else {
      showLoginError(data.message || 'Usuário ou senha inválidos.');
    }
  } catch (err){
    console.error('Erro no login:', err);
    showLoginError('Erro ao tentar autenticar. Verifique sua conexão.');
  }
}

// ------------------------------
// VISITANTES - CADASTRO
// ------------------------------
function showError(message, containerId){
  const c=$(containerId); if(!c) return;
  c.innerHTML=''; const div=document.createElement('div');
  div.className='error-message'; div.textContent=message; c.appendChild(div);
}
function clearError(){ const c=$('registerErrorContainer'); if(c) c.innerHTML=''; }

function validatePhoneNumber(phone){
  const digits=(phone||'').replace(/\D/g,''); return digits.length===11 ? digits : null;
}
function collectFormData(){
  const phoneInput=$('phone')?.value||'';
  const validPhone=validatePhoneNumber(phoneInput);
  if(!validPhone){ alert('Número inválido. Informe DDD + número (11 dígitos).'); return null; }
  return {
    name:$('name')?.value||'', phone:validPhone, email:$('email')?.value||'',
    birthdate:$('birthdate')?.value||'', city:$('city')?.value||'',
    gender:$('gender')?.value||'', maritalStatus:$('maritalStatus')?.value||'',
    currentChurch:$('currentChurch')?.value||'', attendingChurch:$('attendingChurch')?.checked||false,
    referral:$('referral')?.value||'', membership:$('membership')?.checked||false,
    prayerRequest:$('prayerRequest')?.value||'',
    contactTime: document.querySelector('input[name="contactTime"]')?.value || $('contactTime')?.value || ''
  };
}
function validateForm(d){ return d && d.name && d.phone; }

function registerVisitor(visitorData){
  apiRequest('register','POST',visitorData)
    .then(data => {
      alert(data.message || 'Registro realizado com sucesso!');
      $('visitorForm')?.reset(); clearError();
    })
    .catch(err => showError(`Erro ao registrar: ${err.message}`, 'registerErrorContainer'));
}
function handleFormSubmission(e){
  e.preventDefault();
  const data=collectFormData();
  if (validateForm(data)) registerVisitor(data);
  else alert('Preencha os campos obrigatórios.');
}

// ------------------------------
// ACOLHIDOS
// ------------------------------
function clearAcolhidoForm(){ ['nome','telefone','situacao','observacao'].forEach(id=>{ const el=$(id); if(el) el.value=''; }); }
function handleAcolhidoFormSubmission(e){
  e.preventDefault();
  const nome=$('nome')?.value||'', telefone=$('telefone')?.value||'',
        situacao=$('situacao')?.value||'', observacao=$('observacao')?.value||'',
        dataCadastro=new Date().toISOString();
  if(!nome || !telefone || !situacao){ alert('Preencha todos os campos obrigatórios.'); return; }

  fetch(`${baseUrl}/api/acolhido`,{
    method:'POST',
    headers: getAuthHeaders(true),
    body: JSON.stringify({ nome, telefone, situacao, observacao, data_cadastro:dataCadastro })
  })
  .then(r=>r.json())
  .then(data=>{
    if(data.success){
      alert('Acolhido cadastrado com sucesso!');
      clearAcolhidoForm();
      // Nas páginas multi-HTML, volta pro menu
      window.location.href = '/app/menu';
    } else {
      alert('Erro ao cadastrar acolhido.');
    }
  })
  .catch(err=>{ console.error('Erro ao enviar dados:',err); alert('Erro ao tentar cadastrar o acolhido.'); });
}

// ------------------------------
// MONITOR DE STATUS (com paginação)
// ------------------------------
let currentPage=1;
const itemsPerPage=10;
let statusData=[];

function monitorStatus(){
  fetch(`${baseUrl}/api/monitor-status`, { method:'GET', headers: getAuthHeaders(true) })
    .then(r=>{ if(!r.ok) throw new Error(`Erro ao buscar status: ${r.statusText}`); return r.json(); })
    .then(data=>{
      statusData = Array.isArray(data) ? data : [];
      // Se estiver na SPA antiga: mostra seção
      appState.currentView='statusLog'; updateUI();
      currentPage=1; loadPageData(currentPage);
    })
    .catch(err=> showError(`Erro ao buscar status: ${err.message}`, 'logContainer'));
}

function loadPageData(page){
  const start=(page-1)*itemsPerPage, end=start+itemsPerPage;
  const items=statusData.slice(start,end);
  const tbody=$('statusList'); if(!tbody) return;
  tbody.innerHTML='';
  items.forEach(item=>{
    const tr=document.createElement('tr');
    tr.innerHTML = `
      <td>${item.id ?? ''}</td>
      <td>${item.name ?? ''}</td>
      <td>${item.phone ?? ''}</td>
      <td>${item.status ?? ''}</td>`;
    tbody.appendChild(tr);
  });
  const indicator=$('statusPageIndicator');
  if(indicator){
    const totalPages=Math.max(1, Math.ceil(statusData.length/itemsPerPage));
    indicator.textContent = `${page}/${totalPages}`;
  }
}
function handlePageChange(direction){
  const totalPages=Math.max(1, Math.ceil(statusData.length/itemsPerPage));
  const next=currentPage+direction;
  if(next>=1 && next<=totalPages){ currentPage=next; loadPageData(currentPage); }
}
function bindPagination(){
  const nextBtn=$('nextPageButton'), prevBtn=$('prevPageButton');
  if(nextBtn) nextBtn.addEventListener('click', ()=>handlePageChange(1));
  if(prevBtn) prevBtn.addEventListener('click', ()=>handlePageChange(-1));
}

// ------------------------------
// WHATSAPP (envio manual, Z-API)
// ------------------------------
function handleWhatsappButtonClick(){
  if (!confirm('Deseja enviar mensagens de boas-vindas via WhatsApp (Z-API)?')) return;
  appState.currentView='whatsappLog'; updateUI();
  fetchVisitorsAndSendMessagesManual();
}
function fetchVisitorsAndSendMessagesManual(){
  apiRequest('visitantes/fase-null')
    .then(data=>{
      if(data.status!=='success') throw new Error('Erro ao buscar visitantes.');
      const visitors=data.visitantes||[];
      const novos=visitors.filter(v=>!v.fase && !v.status);
      if(novos.length===0){ alert('Nenhum visitante novo encontrado para envio.'); return; }
      const messages=novos.map(v=>({
        numero: v.telefone,
        mensagem: `👋 A Paz de Cristo, ${v.nome || 'Visitante'}! Tudo bem com você?

Sou o *Integra+*, assistente do Ministério de Integração da MAIS DE CRISTO Canasvieiras.
Escolha uma das opções abaixo, respondendo com o número correspondente:

1⃣ Sou batizado em águas e quero me tornar membro.
2⃣ Não sou batizado e quero me tornar membro.
3⃣ Gostaria de receber orações.
4⃣ Quero saber os horários dos cultos.
5⃣ Quero entrar no grupo do WhatsApp.
6⃣ Outro assunto.

🙏 Me diga sua escolha para podermos continuar!`
      }));
      sendMessagesSequentially(messages);
    })
    .catch(err=> showError(`Erro ao buscar visitantes: ${err.message}`,'logContainer'));
}
const sleep=(ms)=>new Promise(r=>setTimeout(r,ms));
async function sendMessagesSequentially(messages, delayMs=2000){
  for(const v of (messages||[])){
    try{
      appendLogToWhatsapp(`📤 Enviando para ${v.numero}...`);
      const resp=await apiRequest('send-message-manual','POST',{ numero:v.numero, mensagem:v.mensagem });
      if(!resp || !resp.success) throw new Error(resp?.error || 'Erro ao enviar mensagem.');
      appendLogToWhatsapp(`✅ Mensagem enviada para ${v.numero}`);
      await sleep(delayMs);
    }catch(err){
      appendLogToWhatsapp(`❌ Erro ao enviar para ${v.numero}: ${err.message}`, true);
      await sleep(delayMs);
    }
  }
}

// ------------------------------
// IA - PERGUNTAS PENDENTES
// ------------------------------
let perguntasPendentes=[];
function loadPendingQuestions(){
  fetch(`${baseUrl}/api/ia/pending-questions`, { headers:getAuthHeaders(true), credentials:'include' })
    .then(r=>r.json())
    .then(data=>{
      perguntasPendentes = data?.questions || [];
      const list=$('pendingQuestionsList'), countEl=$('pendingQuestionsCount');
      if(!list || !countEl) return;
      list.innerHTML=''; countEl.textContent=perguntasPendentes.length;
      if(perguntasPendentes.length===0){ list.innerHTML='<li>Nenhuma pergunta pendente.</li>'; return; }
      perguntasPendentes.forEach((q,idx)=>{
        const li=document.createElement('li');
        li.textContent = q.question || q.pergunta || '(sem texto)';
        li.dataset.index=String(idx);
        li.addEventListener('click', ()=>showTeachForm(idx));
        list.appendChild(li);
      });
    })
    .catch(err=>{
      console.error('Erro ao carregar perguntas pendentes:', err);
      const list=$('pendingQuestionsList'); if(list) list.innerHTML='<li>Erro ao carregar dados.</li>';
    });
}
function toggleTeachForm(show){
  const f=$('teachForm'), l=$('trainingList');
  if(f) f.classList.toggle('hidden', !show);
  if(l) l.classList.toggle('hidden', !!show);
}
function showTeachForm(index){
  const q=perguntasPendentes[index]; if(!q) return;
  const questionEl=$('teachQuestion'), answerEl=$('teachAnswer'), categoryEl=$('teachCategory');
  if(questionEl) questionEl.value = q.question || q.pergunta || '';
  if(answerEl) answerEl.value = '';
  if(categoryEl) categoryEl.value = '';
  toggleTeachForm(true);
}
function handleTeachSubmit(e){
  e.preventDefault();
  const question=$('teachQuestion')?.value?.trim();
  const answer=$('teachAnswer')?.value?.trim();
  const category=$('teachCategory')?.value?.trim();
  if(!question || !answer || !category){ alert('Preencha pergunta, resposta e categoria.'); return; }
  fetch(`${baseUrl}/api/ia/teach`,{
    method:'POST', headers:getAuthHeaders(true),
    body:JSON.stringify({ question, answer, category }), credentials:'include'
  })
  .then(r=>r.json())
  .then(data=>{
    if(data.error){ alert('Erro: '+data.error); return; }
    alert('IA ensinada com sucesso!');
    toggleTeachForm(false); loadPendingQuestions();
  })
  .catch(err=>alert('Erro de conexão: '+err));
}

// ------------------------------
// BOOTSTRAP "PAGE-AWARE"
// ------------------------------
document.addEventListener('DOMContentLoaded', ()=>{
  // 1) Proteção simples de rotas /app/*
  const path = window.location.pathname;
  const requiresAuth = path.startsWith('/app/') && !path.startsWith('/app/login');
  if (requiresAuth && !localStorage.getItem('jwt_token')){
    window.location.href = '/app/login';
    return;
  }

  // 2) Detecta se é a página SPA antiga (tem ambos os containers)
  const isLegacySPA = !!(document.getElementById('loginContainer') && document.getElementById('options'));
  if (isLegacySPA){
    // Só estas páginas usam a mecânica de "views"
    // (sem dashboard automático!)
    // Botões da SPA
    const map = {
      'showFormButton': ()=>{ appState.currentView='form'; updateUI(); },
      'showMemberFormButton': ()=>{ appState.currentView='memberForm'; updateUI(); },
      'showAcolhidoFormButton': ()=>{ clearAcolhidoForm(); appState.currentView='acolhidoForm'; updateUI(); },
      'monitorStatusButton': ()=>{ monitorStatus(); },
      'sendWhatsappButton': ()=>{ handleWhatsappButtonClick(); },
      'showIATrainingButton': ()=>{ appState.currentView='iaTrainingPanel'; updateUI(); loadPendingQuestions(); },
      'showCampaignButton': ()=>{ appState.currentView='eventos'; updateUI(); },

      'backToOptionsCadastroButton': ()=>{ appState.currentView='options'; updateUI(); },
      'backToOptionsCadastroMembro': ()=>{ appState.currentView='options'; updateUI(); },
      'backToOptionsCadastroAcolhido': ()=>{ appState.currentView='options'; updateUI(); },
      'backToOptionsWhatsappButton': ()=>{ appState.currentView='options'; updateUI(); },
      'backToOptionsStatusButton': ()=>{ appState.currentView='options'; updateUI(); },
      'backToOptionsIAButton': ()=>{ appState.currentView='options'; updateUI(); },
      'cancelTeachButton': ()=>{ toggleTeachForm(false); safeShow('trainingList'); },
      'backToOptionsEvento': ()=>{ appState.currentView='options'; updateUI(); },
    };
    Object.entries(map).forEach(([id, handler])=>{
      const el=$(id); if(!el) return;
      const eventType = el.tagName === 'FORM' ? 'submit' : 'click';
      el.addEventListener(eventType, handler);
    });

    // Paginação do monitor (se existir na SPA)
    bindPagination();

    // Mostra login por padrão
    updateUI();
  }

  // 3) Bind de formulários nas páginas multi-HTML (e também funciona na SPA, é idempotente)
  $('visitorForm')?.addEventListener('submit', handleFormSubmission);
  $('acolhidoForm')?.addEventListener('submit', handleAcolhidoFormSubmission);
  $('teachForm')?.addEventListener('submit', handleTeachSubmit);
  $('memberForm')?.addEventListener('submit', handleMemberFormSubmission);

  // 4) Paginação também nas páginas dedicadas de monitor, se existir
  if ($('nextPageButton') || $('prevPageButton')) bindPagination();

  // IMPORTANTE: Nada de loadDashboardData() automático aqui!
});


// ===============================
// MEMBROS - Cadastro Completo
// ===============================

function handleMemberFormSubmission(e) {
  e.preventDefault();

  // Dados básicos
  const data = {
    nome: $('nome')?.value || $('memberName')?.value || '',
    telefone: $('telefone')?.value || $('memberPhone')?.value || '',
    email: $('email')?.value || $('memberEmail')?.value || '',
    data_nascimento: $('data_nascimento')?.value || $('memberBirthday')?.value || '',

    cep: $('cep')?.value || '',
    bairro: $('bairro')?.value || $('memberNeighborhood')?.value || '',
    cidade: $('cidade')?.value || $('memberCity')?.value || '',
    estado: $('estado')?.value || $('memberState')?.value || '',

    estado_civil: $('estado_civil')?.value || '',
    conjuge_nome: $('conjuge_nome')?.value || '',

    possui_filhos: $('possui_filhos')?.value || '',
    filhos_info: $('filhos_info')?.value || '',

    novo_comeco: $('novo_comeco')?.value || '',
    novo_comeco_quando: $('novo_comeco_quando')?.value || '',

    classe_membros: $('classe_membros')?.value || '',
    apresentacao_data: $('apresentacao_data')?.value || '',

    consagracao: $('consagracao')?.value || '',
    status_membro: $('status_membro')?.value || 'ativo',
  };

  // -------------------------
  // Captura checkboxes: Discipulados
  // -------------------------
  const discipuladosSelecionados = [
    ...document.querySelectorAll("input[name='discipulados']:checked")
  ].map(el => el.value);

  data["discipulados"] = discipuladosSelecionados;

  // -------------------------
  // Captura checkboxes: Ministérios
  // -------------------------
  const ministeriosSelecionados = [
    ...document.querySelectorAll("input[name='ministerios']:checked")
  ].map(el => el.value);

  data["ministerios"] = ministeriosSelecionados;

  // Campo "outros ministérios"
  const outros = $('ministerios_outros')?.value;
  if (outros && outros.trim() !== "") {
    data["ministerios_outros"] = outros.trim();
  }

  // -------------------------
  // Validação mínima
  // -------------------------
  if (!data.nome || !data.telefone) {
    alert("Preencha nome e telefone.");
    return;
  }

  // Normalizar telefone (somente números)
  data.telefone = data.telefone.replace(/\D/g, '');

  if (data.telefone.length !== 11) {
    alert("Telefone inválido. Use DDD + número.");
    return;
  }

  // -------------------------
  // Envio para API
  // -------------------------
  fetch(`${baseUrl}/api/membros`, {
    method: "POST",
    headers: getAuthHeaders(true),
    body: JSON.stringify(data)
  })
  .then(r => r.json())
  .then(resp => {
    if (resp.error) {
      alert("Erro ao cadastrar: " + resp.error);
      return;
    }

    alert("Membro cadastrado com sucesso!");
    $('memberForm')?.reset();
    window.location.href = "/app/menu";
  })
  .catch(err => {
    console.error("Erro:", err);
    alert("Erro ao enviar dados. Tente novamente.");
  });
}


