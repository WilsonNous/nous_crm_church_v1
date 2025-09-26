// --- CONFIG ---
const baseUrl = 'https://nous-crm-church-v1.onrender.com/api';

const appState = {
    currentView: 'login',
    user: null,
};

// --- PAINEL DE TREINAMENTO DA IA ---
let currentTeachQuestion = null;
let perguntasPendentes = [];

function toggleSection(sectionId) {
    const sections = [
        'loginContainer', 'options', 'formContainer', 'memberFormContainer',
        'acolhidoFormContainer', 'whatsappLog', 'statusLog',
        'iaTrainingPanel', 'campaignPanel'
    ];
    sections.forEach(id => document.getElementById(id)?.classList.add('hidden'));
    document.getElementById(sectionId)?.classList.remove('hidden');
}

function loadPendingQuestions() {
    fetch(`${baseUrl}/ia/pending-questions`, { credentials: 'include' })
        .then(r => r.json())
        .then(data => {
            perguntasPendentes = data.questions || [];
            const list = document.getElementById('pendingQuestionsList');
            const countEl = document.getElementById('pendingQuestionsCount');
            if (!list || !countEl) return;
            list.innerHTML = '';
            countEl.textContent = perguntasPendentes.length;
            if (perguntasPendentes.length === 0) {
                list.innerHTML = '<li>Nenhuma pergunta pendente.</li>';
                return;
            }
            perguntasPendentes.forEach((q, i) => {
                const li = document.createElement('li');
                li.textContent = q.question;
                li.dataset.index = i;
                li.addEventListener('click', () => showTeachForm(i));
                list.appendChild(li);
            });
        })
        .catch(err => console.error("Erro pendentes IA:", err));
}

function showTeachForm(index) {
    const q = perguntasPendentes[index];
    if (!q) return;
    currentTeachQuestion = q;
    document.getElementById('teachQuestion').value = q.question;
    document.getElementById('teachAnswer').value = '';
    document.getElementById('teachCategory').value = '';
    toggleTeachForm(true);
}
function toggleTeachForm(show) {
    document.getElementById('teachForm')?.classList.toggle('hidden', !show);
    document.getElementById('trainingList')?.classList.toggle('hidden', show);
}
function handleTeachSubmit(e) {
    e.preventDefault();
    const answer = document.getElementById('teachAnswer').value.trim();
    const category = document.getElementById('teachCategory').value;
    if (!answer || !category) return alert("Preencha resposta e categoria.");
    const formData = { question: currentTeachQuestion.question, answer, category };
    fetch(`${baseUrl}/ia/teach`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
    })
        .then(r => r.json())
        .then(d => {
            if (d.status === 'success') {
                alert("IA ensinada!");
                toggleTeachForm(false);
                loadPendingQuestions();
            } else alert("Erro: " + (d.error || 'desconhecido'));
        })
        .catch(err => alert("Erro conexão: " + err));
}

// --- LOGIN ---
function handleLogin(event) {
    event.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    fetch(`${baseUrl}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    })
        .then(r => {
            if (!r.ok) throw new Error("Falha login");
            return r.json();
        })
        .then(d => {
            if (d.status === 'success') {
                localStorage.setItem('jwt_token', d.token);
                appState.user = d.username;
                appState.currentView = 'options';
                updateUI();
            } else showLoginError(d.message);
        })
        .catch(err => showLoginError("Erro login: " + err.message));
}

// --- DASHBOARD ---
function loadDashboardData() {
    fetch(`${baseUrl}/get-dashboard-data`)
        .then(r => r.json())
        .then(d => {
            document.getElementById('totalVisitantes').textContent = d.totalVisitantes || 0;
            document.getElementById('totalMembros').textContent = d.totalMembros || 0;
            document.getElementById('totalhomensMembro').textContent = d.totalhomensMembro || 0;
            document.getElementById('totalmulheresMembro').textContent = d.totalmulheresMembro || 0;
            document.getElementById('discipuladosAtivos').textContent = d.discipuladosAtivos || 0;
            document.getElementById('totalHomensDiscipulado').textContent = d.totalHomensDiscipulado || 0;
            document.getElementById('totalMulheresDiscipulado').textContent = d.totalMulheresDiscipulado || 0;
            document.getElementById('grupos_comunhao').textContent = d.grupos_comunhao || 0;
            document.getElementById('totalHomens').textContent = d.Homens || 0;
            document.getElementById('percentualHomens').textContent = (d.Homens_Percentual || 0) + '%';
            document.getElementById('totalMulheres').textContent = d.Mulheres || 0;
            document.getElementById('percentualMulheres').textContent = (d.Mulheres_Percentual || 0) + '%';
        })
        .catch(err => console.error("Erro dashboard:", err));
}
setInterval(loadDashboardData, 1200000);

// --- VISITANTES ---
function collectFormData() {
    const phoneDigits = document.getElementById('phone').value.replace(/\D/g, '');
    if (phoneDigits.length !== 11) return null;
    return {
        name: document.getElementById('name').value,
        phone: phoneDigits,
        email: document.getElementById('email').value,
        birthdate: document.getElementById('birthdate').value,
        city: document.getElementById('city').value,
        gender: document.getElementById('gender')?.value || '',
        maritalStatus: document.getElementById('maritalStatus').value,
        currentChurch: document.getElementById('currentChurch').value,
        attendingChurch: document.getElementById('attendingChurch').checked,
        referral: document.getElementById('referral').value,
        membership: document.getElementById('membership').checked,
        prayerRequest: document.getElementById('prayerRequest').value,
        contactTime: document.querySelector('input[name="contactTime"]:checked')?.value || ''
    };
}
function handleFormSubmission(e) {
    e.preventDefault();
    const data = collectFormData();
    if (!data || !data.name) return alert("Preencha corretamente.");
    apiRequest('register', 'POST', data)
        .then(d => {
            alert(d.message || "Visitante registrado!");
            document.getElementById('visitorForm')?.reset();
        })
        .catch(err => alert("Erro cadastro: " + err.message));
}

// --- ACOLHIDO ---
function clearAcolhidoForm() {
    ['nome','telefone','situacao','observacao'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
}
function handleAcolhidoFormSubmission(e) {
    e.preventDefault();
    const nome = document.getElementById('nome').value;
    const telefone = document.getElementById('telefone').value;
    const situacao = document.getElementById('situacao').value;
    const observacao = document.getElementById('observacao').value;
    if (!nome || !telefone || !situacao) return alert("Preencha campos obrigatórios.");
    fetch(`${baseUrl}/acolhido`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nome, telefone, situacao, observacao, data_cadastro: new Date().toISOString() }),
    })
        .then(r => r.json())
        .then(d => {
            if (d.success) {
                alert("Acolhido registrado!");
                clearAcolhidoForm();
                appState.currentView = 'options';
                updateUI();
            } else alert("Erro cadastro acolhido.");
        });
}

// --- CAMPANHAS ---
function handleCampaignSubmit(e) {
    e.preventDefault();
    const dataInicio = document.getElementById('campaignStartDate').value;
    const dataFim = document.getElementById('campaignEndDate').value;
    const idadeMin = document.getElementById('campaignAgeMin').value;
    const idadeMax = document.getElementById('campaignAgeMax').value;
    const genero = document.getElementById('campaignGender').value;
    const eventoNome = document.getElementById('campaignName').value;
    const mensagem = document.getElementById('campaignMessage').value;
    const imagemUrl = document.getElementById('campaignImageUrl').value;
    if (!eventoNome || !mensagem) return alert("Informe nome do evento e mensagem.");
    fetch(`${baseUrl}/eventos/filtrar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data_inicio: dataInicio, data_fim: dataFim, idade_min: idadeMin, idade_max: idadeMax, genero }),
    })
        .then(r => r.json())
        .then(d => {
            if (d.status === 'success') {
                if (d.visitantes.length === 0) return alert("Nenhum visitante encontrado.");
                enviarCampanha(d.visitantes, eventoNome, mensagem, imagemUrl);
            } else alert("Erro filtro: " + d.message);
        });
}
function enviarCampanha(visitantes, eventoNome, mensagem, imagemUrl) {
    fetch(`${baseUrl}/eventos/enviar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ visitantes, evento_nome: eventoNome, mensagem, imagem_url: imagemUrl }),
    })
        .then(r => r.json())
        .then(d => {
            if (d.status === 'success') {
                alert(`Campanha enviada para ${d.enviados.length} visitantes!`);
                appState.currentView = 'options';
                updateUI();
            } else alert("Erro campanha: " + d.message);
        });
}

// --- UTILS ---
function apiRequest(endpoint, method = 'GET', body = null) {
    const opt = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opt.body = JSON.stringify(body);
    return fetch(`${baseUrl}/${endpoint}`, opt).then(r => r.json());
}
function showLoginError(msg) {
    document.getElementById('loginErrorContainer').innerHTML = `<div class="error-message">${msg}</div>`;
}
function updateUI() {
    const all = [
        'options','formContainer','memberFormContainer','whatsappLog',
        'statusLog','infoCardsContainer','loginContainer','acolhidoFormContainer',
        'iaTrainingPanel','campaignPanel'
    ];
    all.forEach(id => document.getElementById(id)?.classList.add('hidden'));
    switch(appState.currentView){
        case 'login': document.getElementById('loginContainer').classList.remove('hidden'); break;
        case 'options': document.getElementById('options').classList.remove('hidden'); break;
        case 'form': document.getElementById('formContainer').classList.remove('hidden'); break;
        case 'memberForm': document.getElementById('memberFormContainer').classList.remove('hidden'); break;
        case 'acolhidoForm': document.getElementById('acolhidoFormContainer').classList.remove('hidden'); break;
        case 'iaTrainingPanel': document.getElementById('iaTrainingPanel').classList.remove('hidden'); break;
        case 'campaignPanel': document.getElementById('campaignPanel').classList.remove('hidden'); break;
    }
}
function initializeEventListeners() {
    const map = {
        'loginForm': handleLogin,
        'visitorForm': handleFormSubmission,
        'acolhidoForm': handleAcolhidoFormSubmission,
        'teachIAForm': handleTeachSubmit,
        'campaignForm': handleCampaignSubmit,
        'showIATrainingButton': () => { appState.currentView='iaTrainingPanel'; updateUI(); loadPendingQuestions(); },
        'backToOptionsIAButton': () => { appState.currentView='options'; updateUI(); },
        'cancelTeachButton': () => toggleTeachForm(false),
        'showCampaignButton': () => { appState.currentView='campaignPanel'; updateUI(); },
        'backToOptionsCampaignButton': () => { appState.currentView='options'; updateUI(); },
    };
    for (const [id, handler] of Object.entries(map)) {
        const el = document.getElementById(id);
        if (el) el.addEventListener(el.tagName === 'FORM' ? 'submit' : 'click', handler);
    }
}
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    updateUI();
    loadDashboardData();
});
