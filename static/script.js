// --- CORRIGIDO: baseUrl sem espaços ---
const baseUrl = 'https://nous-crm-church-v1.onrender.com';

const appState = {
    currentView: 'login',
    user: null,
};

// --- IA ---
let currentTeachQuestion = null;
let perguntasPendentes = [];

function toggleSection(sectionId) {
    const sections = [
        'loginContainer', 'options', 'formContainer', 'memberFormContainer',
        'acolhidoFormContainer', 'whatsappLog', 'statusLog',
        'iaTrainingPanel', 'eventosContainer'
    ];
    sections.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });
    const targetSection = document.getElementById(sectionId);
    if (targetSection) targetSection.classList.remove('hidden');
}

function loadPendingQuestions() {
    fetch(`${baseUrl}/api/ia/pending-questions`, { credentials: 'include' })
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
        .catch(err => console.error('Erro ao carregar perguntas pendentes da IA:', err));
}

function showTeachForm(i) {
    const q = perguntasPendentes[i];
    if (!q) return;
    currentTeachQuestion = q;
    document.getElementById('teachQuestion').value = q.question;
    document.getElementById('teachAnswer').value = '';
    document.getElementById('teachCategory').value = '';
    document.getElementById('teachForm').classList.remove('hidden');
    document.getElementById('trainingList').classList.add('hidden');
}

function toggleTeachForm(show) {
    document.getElementById('teachForm')?.classList.toggle('hidden', !show);
    document.getElementById('trainingList')?.classList.toggle('hidden', show);
}

function handleTeachSubmit(e) {
    e.preventDefault();
    const answer = document.getElementById('teachAnswer').value.trim();
    const category = document.getElementById('teachCategory').value;
    if (!answer || !category) {
        alert('Por favor, preencha a resposta e a categoria.');
        return;
    }
    const formData = {
        question: currentTeachQuestion.question,
        answer,
        category
    };
    fetch(`${baseUrl}/api/ia/teach`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
        credentials: 'include'
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            alert('IA ensinada com sucesso!');
            toggleTeachForm(false);
            loadPendingQuestions();
        } else {
            alert('Erro: ' + (data.error || 'Desconhecido'));
        }
    })
    .catch(err => alert('Erro de conexão: ' + err));
}

// --- EVENTOS ---
function handleCampaignSubmit(e) {
    e.preventDefault();
    const dataInicio = document.getElementById('dataInicio').value;
    const dataFim = document.getElementById('dataFim').value;
    const idadeMin = document.getElementById('idadeMin').value;
    const idadeMax = document.getElementById('idadeMax').value;
    const genero = document.getElementById('genero').value;

    fetch(`${baseUrl}/api/eventos/filtrar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data_inicio: dataInicio, data_fim: dataFim, idade_min: idadeMin, idade_max: idadeMax, genero })
    })
    .then(r => r.json())
    .then(data => {
        const lista = document.getElementById('resultadoVisitantes');
        if (!lista) return;
        lista.innerHTML = '';
        if (data.status === "success" && data.visitantes.length > 0) {
            data.visitantes.forEach(v => {
                const div = document.createElement('div');
                div.textContent = `${v.nome} - ${v.telefone}`;
                lista.appendChild(div);
            });
        } else {
            lista.innerHTML = '<p>Nenhum visitante encontrado.</p>';
        }
    })
    .catch(err => {
        console.error("Erro ao filtrar:", err);
        alert("Erro ao buscar visitantes.");
    });
}

function enviarCampanhaSubmit(e) {
    e.preventDefault();
    const eventoNome = document.getElementById('eventoNome').value;
    const mensagem = document.getElementById('mensagemEvento').value;
    const imagemUrl = document.getElementById('imagemUrl').value;

    fetch(`${baseUrl}/api/eventos/enviar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ evento_nome: eventoNome, mensagem, imagem_url: imagemUrl })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === "success") {
            alert(`Campanha enviada para ${data.enviados.length} visitantes.`);
            appState.currentView = 'options';
            updateUI();
        } else {
            alert("Erro ao enviar campanha: " + data.message);
        }
    })
    .catch(err => {
        console.error("Erro ao enviar campanha:", err);
        alert("Erro de conexão ao enviar campanha.");
    });
}

// --- CORE ---
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    updateUI();
    loadDashboardData();
});

function initializeEventListeners() {
    const listeners = {
        'showFormButton': () => { appState.currentView = 'formContainer'; updateUI(); },
        'showMemberFormButton': () => { appState.currentView = 'memberFormContainer'; updateUI(); },
        'showAcolhidoFormButton': () => { appState.currentView = 'acolhidoFormContainer'; updateUI(); },
        'monitorStatusButton': monitorStatus,
        'sendWhatsappButton': handleWhatsappButtonClick,
        'loginForm': handleLogin,
        'visitorForm': handleFormSubmission,
        'memberForm': handleMemberFormSubmission,
        'acolhidoForm': handleAcolhidoFormSubmission,
        'showIATrainingButton': () => { appState.currentView = 'iaTrainingPanel'; updateUI(); loadPendingQuestions(); },
        'backToOptionsIAButton': () => { appState.currentView = 'options'; updateUI(); },
        'teachIAForm': handleTeachSubmit,
        'cancelTeachButton': () => toggleTeachForm(false),
        'showCampaignButton': () => { appState.currentView = 'eventosContainer'; updateUI(); },
        'backToOptionsEvento': () => { appState.currentView = 'options'; updateUI(); },
        'filtroVisitantesForm': handleCampaignSubmit,
        'enviarEventoForm': enviarCampanhaSubmit,
        // Botões de voltar genéricos
        'backToOptionsCadastroButton': () => { appState.currentView = 'options'; updateUI(); },
        'backToOptionsCadastroMembro': () => { appState.currentView = 'options'; updateUI(); },
        'backToOptionsCadastroAcolhido': () => { appState.currentView = 'options'; updateUI(); },
        'backToOptionsStatusButton': () => { appState.currentView = 'options'; updateUI(); },
        'backToOptionsWhatsappButton': () => { appState.currentView = 'options'; updateUI(); }
    };

    for (const [id, handler] of Object.entries(listeners)) {
        const el = document.getElementById(id);
        if (el) {
            const eventType = el.tagName === 'FORM' ? 'submit' : 'click';
            el.addEventListener(eventType, handler);
        }
    }
}

function updateUI() {
    const sections = [
        'loginContainer', 'options', 'formContainer', 'memberFormContainer',
        'acolhidoFormContainer', 'whatsappLog', 'statusLog',
        'iaTrainingPanel', 'eventosContainer'
    ];
    sections.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });

    const target = document.getElementById(appState.currentView);
    if (target) target.classList.remove('hidden');
}

// --- (mantém aqui todas as funções já existentes: login, whatsapp, dashboard, cadastros etc) ---

