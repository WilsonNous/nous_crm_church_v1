// --- CORRIGIDO: baseUrl sem espaços ---
const baseUrl = 'https://nous-crm-church-v1.onrender.com';

const appState = {
    currentView: 'login', // Pode ser 'login', 'options', 'form', 'whatsappLog', 'statusLog', etc.
    user: null, // O usuário logado
};

// --- FUNÇÕES PARA O PAINEL DE TREINAMENTO DA IA ---
let currentTeachQuestion = null;
let perguntasPendentes = []; // Cache das perguntas pendentes

function toggleSection(sectionId) {
    // Oculta todas as seções
    const sections = [
        'loginContainer', 'options', 'formContainer', 'memberFormContainer',
        'acolhidoFormContainer', 'whatsappLog', 'statusLog', 'iaTrainingPanel'
    ];
    sections.forEach(id => {
        const element = document.getElementById(id);
        if (element) element.classList.add('hidden');
    });

    // Mostra a seção solicitada
    const targetSection = document.getElementById(sectionId);
    if (targetSection) targetSection.classList.remove('hidden');
}

// --- NOVA FUNÇÃO: Carregar Perguntas Pendentes da IA ---
function loadPendingQuestions() {
    fetch(`${baseUrl}/api/ia/pending-questions`, { credentials: 'include' })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
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

            perguntasPendentes.forEach((question, index) => {
                const li = document.createElement('li');
                li.textContent = question.question;
                li.dataset.index = index;
                li.addEventListener('click', () => showTeachForm(index));
                list.appendChild(li);
            });
        })
        .catch(error => {
            console.error('Erro ao carregar perguntas pendentes da IA:', error);
            const list = document.getElementById('pendingQuestionsList');
            if (list) list.innerHTML = '<li>Erro ao carregar dados.</li>';
        });
}

// --- NOVA FUNÇÃO: Mostrar Formulário de Ensino da IA ---
function showTeachForm(index) {
    const question = perguntasPendentes[index];
    if (!question) return;

    currentTeachQuestion = question;
    
    const questionEl = document.getElementById('teachQuestion');
    const answerEl = document.getElementById('teachAnswer');
    const categoryEl = document.getElementById('teachCategory');
    const formEl = document.getElementById('teachForm');
    const listEl = document.getElementById('trainingList');

    if (questionEl) questionEl.value = question.question;
    if (answerEl) answerEl.value = '';
    if (categoryEl) categoryEl.value = '';
    if (formEl) formEl.classList.remove('hidden');
    if (listEl) listEl.classList.add('hidden');
}

// --- NOVA FUNÇÃO: Toggle Formulário de Ensino da IA ---
function toggleTeachForm(show) {
    const formEl = document.getElementById('teachForm');
    const listEl = document.getElementById('trainingList');
    if (formEl) formEl.classList.toggle('hidden', !show);
    if (listEl) listEl.classList.toggle('hidden', show);
}

// --- NOVA FUNÇÃO: Submeter Ensino da IA ---
function handleTeachSubmit(event) {
    event.preventDefault();

    const answer = document.getElementById('teachAnswer').value.trim();
    const category = document.getElementById('teachCategory').value;

    if (!answer || !category) {
        alert('Por favor, preencha a resposta e a categoria.');
        return;
    }

    const formData = {
        question: currentTeachQuestion.question,
        answer: answer,
        category: category
    };

    fetch(`${baseUrl}/api/ia/teach`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
        credentials: 'include'
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert('IA ensinada com sucesso!');
            toggleTeachForm(false);
            loadPendingQuestions(); // Recarrega a lista
        } else {
            alert('Erro: ' + (data.error || 'Desconhecido'));
        }
    })
    .catch(error => {
        alert('Erro de conexão: ' + error);
    });
}
// --- FIM DAS FUNÇÕES PARA O PAINEL DE TREINAMENTO DA IA ---

document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    updateUI();
    loadDashboardData();
});

document.getElementById('cep').addEventListener('blur', () => {
    const cep = document.getElementById('cep').value.replace(/\D/g, ''); // Remove caracteres não numéricos

    if (cep.length === 8) {
        fetch(`https://viacep.com.br/ws/${cep}/json/`)
            .then(response => response.json())
            .then(data => {
                if (!data.erro) {
                    document.getElementById('bairro').value = data.bairro || '';
                    document.getElementById('cidade').value = data.localidade || '';
                    document.getElementById('estado').value = data.uf || '';
                } else {
                    alert("CEP não encontrado.");
                }
            })
            .catch(error => console.error("Erro ao buscar CEP:", error));
    } else {
        alert("Digite um CEP válido.");
    }
});

function initializeEventListeners() {
    const listeners = {
        'showAcolhidoFormButton': () => {
            clearAcolhidoForm();
            appState.currentView = 'acolhidoForm';
            updateUI();
        },
        'showFormButton': () => { appState.currentView = 'form'; updateUI(); },
        'showMemberFormButton': () => { appState.currentView = 'memberForm'; updateUI(); },
        'backToOptionsCadastroButton': () => { appState.currentView = 'options'; updateUI(); },
        'backToOptionsCadastroMembro': () => { appState.currentView = 'options'; updateUI(); },
        'backToOptionsCadastroAcolhido': () => { appState.currentView = 'options'; updateUI(); },
        'backToOptionsStatusButton': () => {
            appState.currentView = 'options';
            document.getElementById('statusLog')?.classList.add('hidden');
            toggleButtons(false);
        },
        'backToOptionsWhatsappButton': () => { appState.currentView = 'options'; updateUI(); },
        'acolhidoForm': handleAcolhidoFormSubmission,
        'sendWhatsappButton': handleWhatsappButtonClick,
        'monitorStatusButton': monitorStatus,
        'visitorForm': handleFormSubmission,
        'memberForm': handleMemberFormSubmission,
        'loginForm': handleLogin,
        
        // --- NOVOS EVENTOS PARA O PAINEL DE IA ---
        'showIATrainingButton': () => {
            appState.currentView = 'iaTrainingPanel';
            updateUI();
            loadPendingQuestions(); // Carrega as perguntas ao abrir o painel
        },
        'backToOptionsIAButton': () => { appState.currentView = 'options'; updateUI(); },
        'cancelTeachButton': () => { toggleTeachForm(false); },
        'teachForm': handleTeachSubmit // Adiciona o listener para o submit do form
        // --- FIM DOS NOVOS EVENTOS ---
    };

    for (const [id, handler] of Object.entries(listeners)) {
        const element = document.getElementById(id);
        if (element) {
            const eventType = element.tagName === 'FORM' ? 'submit' : 'click';
            element.addEventListener(eventType, handler);
        }
    }
}

function updateUI() {
    // Oculta todas as seções
    const allSections = [
        'options', 'formContainer', 'memberFormContainer',
        'whatsappLog', 'statusLog', 'infoCardsContainer',
        'loginContainer', 'acolhidoFormContainer', 'iaTrainingPanel' // Adicionado o painel de IA
    ];

    allSections.forEach(sectionId => {
        const element = document.getElementById(sectionId);
        if (element) element.classList.add('hidden');
    });

    // Ocultar botões, se necessário
    const buttonsToHide = [
        'showFormButton', 'monitorStatusButton', 'sendWhatsappButton',
        'showMemberFormButton', 'infoCardsContainer', 'showAcolhidoFormButton'
    ];
    buttonsToHide.forEach(id => {
        const element = document.getElementById(id);
        if (element) element.classList.add('hidden');
    });

    // Atualiza a exibição conforme o estado atual
    switch (appState.currentView) {
        case 'login':
            document.getElementById('loginContainer')?.classList.remove('hidden');
            break;
        case 'options':
            document.getElementById('options')?.classList.remove('hidden');
            document.getElementById('showFormButton')?.classList.remove('hidden');
            document.getElementById('monitorStatusButton')?.classList.remove('hidden');
            document.getElementById('sendWhatsappButton')?.classList.remove('hidden');
            document.getElementById('showMemberFormButton')?.classList.remove('hidden');
            document.getElementById('showAcolhidoFormButton')?.classList.remove('hidden');
            document.getElementById('infoCardsContainer')?.classList.remove('hidden');
            break;
        case 'form':
            document.getElementById('formContainer')?.classList.remove('hidden');
            break;
        case 'memberForm':
            document.getElementById('memberFormContainer')?.classList.remove('hidden');
            break;
        case 'whatsappLog':
            document.getElementById('whatsappLog')?.classList.remove('hidden');
            break;
        case 'acolhidoForm':
            document.getElementById('acolhidoFormContainer')?.classList.remove('hidden');
            break;
        case 'statusLog':
            document.getElementById('statusLog')?.classList.remove('hidden');
            break;
        // --- NOVO ESTADO: Painel de Treinamento da IA ---
        case 'iaTrainingPanel':
            document.getElementById('iaTrainingPanel')?.classList.remove('hidden');
            break;
        // --- FIM DO NOVO ESTADO ---
        default:
            console.log('Visão não reconhecida:', appState.currentView);
    }
}

function handleLogin(event) {
    event.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    fetch(`${baseUrl}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        }
        throw new Error('Falha ao autenticar');
    })
    .then(data => {
        if (data.status === 'success') {
            localStorage.setItem('jwt_token', data.token);
            appState.user = data.username;
            appState.currentView = 'options';
            updateUI();
        } else {
            showLoginError(data.message);
        }
    })
    .catch(error => {
        console.error("Erro no login:", error);
        showLoginError("Erro ao tentar autenticar.");
    });
}

function handleWhatsappButtonClick() {
    if (confirm('Você tem certeza que deseja enviar a mensagem via WhatsApp?')) {
        appState.currentView = 'whatsappLog';
        updateUI();
        fetchVisitorsAndSendMessagesManual();
    }
}

function fetchVisitorsAndSendMessagesManual() {
    apiRequest('get_visitors')
        .then(data => {
            if (data.status === 'success') {
                const visitors = data.visitors;
                if (visitors.length === 0) {
                    alert('Nenhum visitante encontrado.');
                    return;
                }
                const messages = visitors.map(visitor => ({
                    phone: visitor.phone,
                    ContentSid: "HX45ac2c911363fad7a701f72b3ff7a2ce",
                    template_name: "boasvindasvisitantes",
                    params: { visitor_name: visitor.name }
                }));
                sendMessagesManual(messages);
            } else {
                throw new Error('Erro ao buscar visitantes.');
            }
        })
        .catch(error => showError(`Erro ao buscar visitantes: ${error.message}`));
}

function sendMessagesManual(messages) {
    messages.forEach(visitor => {
        apiRequest('send-message-manual', 'POST', {
            numero: visitor.phone,
            ContentSid: "HX45ac2c911363fad7a701f72b3ff7a2ce",
            params: visitor.params
        })
        .then(data => {
            if (data.success) {
                alert('Mensagem enviada manualmente com sucesso para ' + visitor.phone);
            } else {
                throw new Error(data.error || 'Erro ao enviar mensagem.');
            }
        })
        .catch(error => showError(`Erro ao enviar mensagens manuais: ${error.message}`));
    });
}

let currentPage = 1;
const itemsPerPage = 10;
let statusData = [];

function loadPageData(page) {
    const startIndex = (page - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const paginatedItems = statusData.slice(startIndex, endIndex);

    const statusList = document.getElementById('statusList');
    if (!statusList) return;
    statusList.innerHTML = '';

    paginatedItems.forEach(item => {
        const row = `<tr>
            <td>${item.id}</td>
            <td>${item.name}</td>
            <td>${item.phone}</td>
            <td>${item.status}</td>
        </tr>`;
        statusList.innerHTML += row;
    });
}

function monitorStatus() {
    fetch(`${baseUrl}/monitor-status`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Erro ao buscar status: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        statusData = data;
        toggleButtons(true);
        document.getElementById('statusLog')?.classList.remove('hidden');
        loadPageData(currentPage);
    })
    .catch(error => showError(`Erro ao buscar status: ${error.message}`));
}

document.getElementById('nextPageButton')?.addEventListener('click', () => {
    if ((currentPage * itemsPerPage) < statusData.length) {
        currentPage++;
        loadPageData(currentPage);
    }
});

document.getElementById('prevPageButton')?.addEventListener('click', () => {
    if (currentPage > 1) {
        currentPage--;
        loadPageData(currentPage);
    }
});

function handleFormSubmission(event) {
    event.preventDefault();
    const visitorData = collectFormData();

    if (validateForm(visitorData)) {
        registerVisitor(visitorData);
    } else {
        alert('Por favor, preencha os campos obrigatórios corretamente.');
    }
}

function collectFormData() {
    const phoneInput = document.getElementById('phone').value;
    const validPhone = validatePhoneNumber(phoneInput);

    if (validPhone === null) {
        alert('Número de telefone inválido. Por favor, insira um número com DDD e 9 dígitos.');
        return null;
    }

    return {
        name: document.getElementById('name').value,
        phone: validPhone,
        email: document.getElementById('email').value,
        birthdate: document.getElementById('birthdate').value,
        city: document.getElementById('city').value,
        gender: document.querySelector('#gender')?.value || '',
        maritalStatus: document.getElementById('maritalStatus').value,
        currentChurch: document.getElementById('currentChurch').value,
        attendingChurch: document.getElementById('attendingChurch').value,
        referral: document.getElementById('referral').value,
        membership: document.getElementById('membership').checked,
        prayerRequest: document.getElementById('prayerRequest').value,
        contactTime: document.querySelector('input[name="contactTime"]:checked')?.value || ''
    };
}

function validateForm(data) {
    return data && data.name && data.phone;
}

function validatePhoneNumber(phone) {
    const phoneDigits = phone.replace(/\D/g, '');
    return phoneDigits.length === 11 ? phoneDigits : null;
}

function registerVisitor(visitorData) {
    apiRequest('register', 'POST', visitorData)
        .then(data => {
            alert(data.message || 'Registro bem-sucedido!');
            document.getElementById('visitorForm').reset();
            clearError();
        })
        .catch(error => showError(`Erro ao registrar: ${error.message}`, 'registerErrorContainer'));
}

function showError(message, containerId) {
    const errorContainer = document.getElementById(containerId);
    if (!errorContainer) return;
    const errorElement = document.createElement('div');
    errorElement.className = 'error-message';
    errorElement.textContent = message;
    errorContainer.innerHTML = '';
    errorContainer.appendChild(errorElement);
}

function clearError() {
    const errorContainer = document.getElementById('registerErrorContainer');
    if (errorContainer) errorContainer.innerHTML = '';
}

function handleMemberFormSubmission(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const data = {
        name: formData.get('name'),
        email: formData.get('email'),
        phone: formData.get('phone'),
        membershipDate: formData.get('membershipDate'),
    };

    fetch(`${baseUrl}/api/membros`, {
        method: 'POST',
        body: JSON.stringify(data),
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(result => {
        alert('Membro cadastrado com sucesso!');
        appState.currentView = 'options';
        updateUI();
    })
    .catch(error => {
        console.error('Erro ao cadastrar membro:', error);
        alert('Erro ao cadastrar membro!');
    });
}

function loadDashboardData() {
    fetch(`${baseUrl}/get-dashboard-data`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('totalVisitantes').textContent = data.totalVisitantes || '0';
            document.getElementById('totalMembros').innerText = data.totalMembros;
            document.getElementById('totalhomensMembro').innerText = data.totalhomensMembro;
            document.getElementById('totalmulheresMembro').innerText = data.totalmulheresMembro;
            document.getElementById('discipuladosAtivos').textContent = data.discipuladosAtivos || '0';
            document.getElementById("totalHomensDiscipulado").textContent = data.totalHomensDiscipulado || '0';
            document.getElementById("totalMulheresDiscipulado").textContent = data.totalMulheresDiscipulado || '0';
            document.getElementById('grupos_comunhao').textContent = data.grupos_comunhao || '0';
            document.getElementById('totalHomens').textContent = data.Homens || '0';
            document.getElementById('percentualHomens').textContent = data.Homens_Percentual + '%' || '0%';
            document.getElementById('totalMulheres').textContent = data.Mulheres || '0';
            document.getElementById('percentualMulheres').textContent = data.Mulheres_Percentual + '%' || '0%';
        })
        .catch(error => {
            console.error('Erro ao carregar dados do dashboard:', error);
        });
}

function toggleButtons(showOnlyMonitorStatus) {
    const buttons = document.querySelectorAll('#buttonContainer button');
    const infoCards = document.getElementById('infoCardsContainer');
    buttons.forEach(button => {
        if (showOnlyMonitorStatus && button.id !== 'monitorStatusButton') {
            button.classList.add('hidden');
            if (infoCards) infoCards.classList.add('hidden');
        } else {
            button.classList.remove('hidden');
            if (infoCards) infoCards.classList.remove('hidden');
        }
    });
}

// --- CORRIGIDO: Removido localStorage.getItem('token') ---
function apiRequest(endpoint, method = 'GET', body = null) {
    const headers = { 'Content-Type': 'application/json' };
    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);

    return fetch(`${baseUrl}/${endpoint}`, options)
        .then(response => {
            if (!response.ok) {
                return response.json().then(errorData => {
                    throw new Error(`Erro: ${response.status} - ${errorData.message || 'Erro desconhecido'}`);
                });
            }
            return response.json();
        })
        .catch(error => {
            console.error('Erro na apiRequest:', error);
            throw error;
        });
}

function clearAcolhidoForm() {
    document.getElementById('nome').value = '';
    document.getElementById('telefone').value = '';
    document.getElementById('situacao').value = '';
    document.getElementById('observacao').value = '';
}

function handleAcolhidoFormSubmission(event) {
    event.preventDefault();

    const nome = document.getElementById('nome').value;
    const telefone = document.getElementById('telefone').value;
    const situacao = document.getElementById('situacao').value;
    const observacao = document.getElementById('observacao').value;
    const dataCadastro = new Date().toISOString();

    if (!nome || !telefone || !situacao) {
        alert("Por favor, preencha todos os campos obrigatórios.");
        return;
    }

    fetch(`${baseUrl}/api/acolhido`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nome, telefone, situacao, observacao, data_cadastro: dataCadastro })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert("Acolhido cadastrado com sucesso!");
            clearAcolhidoForm();
            appState.currentView = 'options';
            updateUI();
        } else {
            alert("Erro ao cadastrar acolhido.");
        }
    })
    .catch(error => {
        console.error("Erro ao enviar dados:", error);
        alert("Erro ao tentar cadastrar o acolhido.");
    });
}

setInterval(loadDashboardData, 1200000);
