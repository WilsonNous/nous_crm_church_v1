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
                // Se não for JSON, provavelmente é um redirect para login
                if (response.headers.get('content-type')?.includes('text/html')) {
                    window.location.href = '/admin/integra/learn';
                    return;
                }
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

// Adicionar evento CEP apenas se o elemento existir
const cepElement = document.getElementById('cep');
if (cepElement) {
    cepElement.addEventListener('blur', () => {
        const cep = cepElement.value.replace(/\D/g, ''); // Remove caracteres não numéricos

        if (cep.length === 8) {
            fetch(`https://viacep.com.br/ws/${cep}/json/`)
                .then(response => response.json())
                .then(data => {
                    if (!data.erro) {
                        const bairroEl = document.getElementById('bairro');
                        const cidadeEl = document.getElementById('cidade');
                        const estadoEl = document.getElementById('estado');
                        
                        if (bairroEl) bairroEl.value = data.bairro || '';
                        if (cidadeEl) cidadeEl.value = data.localidade || '';
                        if (estadoEl) estadoEl.value = data.uf || '';
                    } else {
                        alert("CEP não encontrado.");
                    }
                })
                .catch(error => console.error("Erro ao buscar CEP:", error));
        } else {
            alert("Digite um CEP válido.");
        }
    });
}

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
            document.getElementById('statusLog')?.classList.add('hidden'); // Esconde a tabela
            toggleButtons(false); // Exibe todos os botões
        },
        'backToOptionsWhatsappButton': () => { appState.currentView = 'options'; updateUI(); },
        'acolhidoForm': handleAcolhidoFormSubmission, // Novo evento
        'sendWhatsappButton': handleWhatsappButtonClick,
        'monitorStatusButton': monitorStatus,
        'visitorForm': handleFormSubmission,
        'memberForm': handleMemberFormSubmission,
        'loginForm': handleLogin,
        
        // --- NOVOS EVENTOS PARA O PAINEL DE IA ---
        'showIATrainingButton': () => {
            toggleSection('iaTrainingPanel');
            loadPendingQuestions();
        },
        'backToOptionsIAButton': () => { toggleSection('options'); },
        'cancelTeachButton': () => { toggleTeachForm(false); },
        'teachIAForm': handleTeachSubmit // Adiciona o listener para o submit do form

        'showCampaignButton': () => { 
            appState.currentView = 'campaignPanel'; 
            updateUI(); 
        },
        'backToOptionsCampaignButton': () => { 
            appState.currentView = 'options'; 
            updateUI(); 
        },
        'campaignForm': handleCampaignSubmit

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

    // Ocultar botões, se necessário (por exemplo, em views de formulário ou detalhes)
    const showFormButton = document.getElementById('showFormButton');
    const monitorStatusButton = document.getElementById('monitorStatusButton');
    const sendWhatsappButton = document.getElementById('sendWhatsappButton');
    const showMemberFormButton = document.getElementById('showMemberFormButton');
    const infoCardsContainer = document.getElementById('infoCardsContainer');
    const showAcolhidoFormButton = document.getElementById('showAcolhidoFormButton');
    const showIATrainingButton = document.getElementById('showIATrainingButton');

    if (showFormButton) showFormButton.classList.add('hidden');
    if (monitorStatusButton) monitorStatusButton.classList.add('hidden');
    if (sendWhatsappButton) sendWhatsappButton.classList.add('hidden');
    if (showMemberFormButton) showMemberFormButton.classList.add('hidden');
    if (infoCardsContainer) infoCardsContainer.classList.add('hidden');
    if (showAcolhidoFormButton) showAcolhidoFormButton.classList.add('hidden');
    if (showIATrainingButton) showIATrainingButton.classList.add('hidden');

    // Atualiza a exibição conforme o estado atual
    switch (appState.currentView) {
        case 'login':
            document.getElementById('loginContainer').classList.remove('hidden');
            break;
        case 'options':
            document.getElementById('options').classList.remove('hidden');
            if (showFormButton) showFormButton.classList.remove('hidden');
            if (monitorStatusButton) monitorStatusButton.classList.remove('hidden');
            if (sendWhatsappButton) sendWhatsappButton.classList.remove('hidden');
            if (showMemberFormButton) showMemberFormButton.classList.remove('hidden');
            if (infoCardsContainer) infoCardsContainer.classList.remove('hidden');
            if (showAcolhidoFormButton) showAcolhidoFormButton.classList.remove('hidden');
            if (showIATrainingButton) showIATrainingButton.classList.remove('hidden');
            break;
        case 'form':
            document.getElementById('formContainer').classList.remove('hidden');
            break;
        case 'memberForm':
            document.getElementById('memberFormContainer').classList.remove('hidden');
            break;
        case 'whatsappLog':
            document.getElementById('whatsappLog').classList.remove('hidden');
            break;
        case 'acolhidoForm':
            document.getElementById('acolhidoFormContainer').classList.remove('hidden');
            break;
        case 'statusLog':
            document.getElementById('statusLog').classList.remove('hidden');
            break;
        // --- NOVO ESTADO: Painel de Treinamento da IA ---
        case 'iaTrainingPanel':
            document.getElementById('iaTrainingPanel').classList.remove('hidden');
            break;
        case 'campaignPanel':
            document.getElementById('campaignPanel').classList.remove('hidden');
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
        headers: {
            'Content-Type': 'application/json',
        },
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
            // Armazenando o token no localStorage (ou sessionStorage)
            localStorage.setItem('jwt_token', data.token);

            appState.user = data.username;
            appState.currentView = 'options';
            console.log('Estado após login:', appState.currentView);
            updateUI();  // Atualiza a interface para mostrar as opções
        } else {
            showLoginError(data.message); // Exibe a mensagem de erro
        }
    })
    .catch(error => {
        console.error("Erro no login:", error);
        showLoginError("Erro ao tentar autenticar.");
    });
}

function handleWhatsappButtonClick() {
    if (confirm('Você tem certeza que deseja enviar a mensagem via WhatsApp?')) {
        // Atualiza a UI para mostrar o log de WhatsApp
        appState.currentView = 'whatsappLog';
        updateUI();

        // Chama a função para buscar os visitantes e enviar a mensagem manualmente
        fetchVisitorsAndSendMessagesManual();  // Função modificada para lidar com o envio manual
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
                    ContentSid: "HX45ac2c911363fad7a701f72b3ff7a2ce",  // ID do template
                    template_name: "boasvindasvisitantes",            // Nome do template
                    params: {
                        visitor_name: visitor.name
                    }
                }));

                sendMessagesManual(messages);
            } else {
                throw new Error('Erro ao buscar visitantes.');
            }
        })
        .catch(error => showError(`Erro ao buscar visitantes: ${error.message}`));  // Correção aqui
}

function sendMessagesManual(messages) {
    messages.forEach(visitor => {
        apiRequest('send-message-manual', 'POST', {
            numero: visitor.phone,
            ContentSid: "HX45ac2c911363fad7a701f72b3ff7a2ce",  // SID do template Twilio
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
let statusData = []; // Array para armazenar todos os dados de status

// Função para carregar os dados da página atual
function loadPageData(page) {
    const startIndex = (page - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const paginatedItems = statusData.slice(startIndex, endIndex);

    console.log('Itens para a página atual:', paginatedItems); // Verifica os itens da página atual

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
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Erro ao buscar status: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        statusData = data;
        console.log(statusData);

        // Exibe apenas o botão "Monitorar Status"
        toggleButtons(true);

        // Remove a classe 'hidden' para garantir que a tabela seja visível
        const statusLog = document.getElementById('statusLog');
        if (statusLog) statusLog.classList.remove('hidden');

        loadPageData(currentPage); // Carrega a primeira página
    })
    .catch(error => showError(`Erro ao buscar status: ${error.message}`));
}

// Eventos de paginação
const nextPageButton = document.getElementById('nextPageButton');
const prevPageButton = document.getElementById('prevPageButton');

if (nextPageButton) {
    nextPageButton.addEventListener('click', () => {
        if ((currentPage * itemsPerPage) < statusData.length) {
            currentPage++;
            loadPageData(currentPage);
        }
    });
}

if (prevPageButton) {
    prevPageButton.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadPageData(currentPage);
        }
    });
}

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
        attendingChurch: document.getElementById('attendingChurch').checked,
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
            // Limpar o formulário após o cadastro bem-sucedido
            const visitorForm = document.getElementById('visitorForm');
            if (visitorForm) visitorForm.reset();
            // Limpar mensagens de erro, se houver
            clearError();
        })
        .catch(error => showError(`Erro ao registrar: ${error.message}`, 'registerErrorContainer'));
}

function showError(message, containerId) {
    // Seleciona o container onde a mensagem de erro será exibida
    const errorContainer = document.getElementById(containerId);
    if (!errorContainer) return;

    // Cria um elemento para a mensagem de erro
    const errorElement = document.createElement('div');
    errorElement.className = 'error-message'; // Adicione uma classe para estilização
    errorElement.textContent = message;

    // Limpa qualquer mensagem de erro anterior
    errorContainer.innerHTML = '';

    // Adiciona a mensagem de erro ao container
    errorContainer.appendChild(errorElement);
}

function clearError() {
    // Limpa a mensagem de erro, se houver
    const errorContainer = document.getElementById('registerErrorContainer');
    if (errorContainer) errorContainer.innerHTML = '';
}

function showLoginError(message) {
    const errorContainer = document.getElementById('loginErrorContainer');
    if (!errorContainer) return;
    
    errorContainer.innerHTML = `<div class="error-message">${message}</div>`;
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

    // Enviar dados do formulário de membro (substitua com sua lógica real)
    fetch(`${baseUrl}/api/membros`, {
        method: 'POST',
        body: JSON.stringify(data),
        headers: {
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(result => {
        alert('Membro cadastrado com sucesso!');
        appState.currentView = 'options'; // Redireciona para as opções após envio
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
            const totalVisitantes = document.getElementById('totalVisitantes');
            const totalMembros = document.getElementById('totalMembros');
            const totalhomensMembro = document.getElementById('totalhomensMembro');
            const totalmulheresMembro = document.getElementById('totalmulheresMembro');
            const discipuladosAtivos = document.getElementById('discipuladosAtivos');
            const totalHomensDiscipulado = document.getElementById('totalHomensDiscipulado');
            const totalMulheresDiscipulado = document.getElementById('totalMulheresDiscipulado');
            const gruposComunhao = document.getElementById('grupos_comunhao');
            const totalHomens = document.getElementById('totalHomens');
            const percentualHomens = document.getElementById('percentualHomens');
            const totalMulheres = document.getElementById('totalMulheres');
            const percentualMulheres = document.getElementById('percentualMulheres');

            if (totalVisitantes) totalVisitantes.textContent = data.totalVisitantes || '0';
            if (totalMembros) totalMembros.textContent = data.totalMembros || '0';
            if (totalhomensMembro) totalhomensMembro.textContent = data.totalhomensMembro || '0';
            if (totalmulheresMembro) totalmulheresMembro.textContent = data.totalmulheresMembro || '0';
            if (discipuladosAtivos) discipuladosAtivos.textContent = data.discipuladosAtivos || '0';
            if (totalHomensDiscipulado) totalHomensDiscipulado.textContent = data.totalHomensDiscipulado || '0';
            if (totalMulheresDiscipulado) totalMulheresDiscipulado.textContent = data.totalMulheresDiscipulado || '0';
            if (gruposComunhao) gruposComunhao.textContent = data.grupos_comunhao || '0';
            if (totalHomens) totalHomens.textContent = data.Homens || '0';
            if (percentualHomens) percentualHomens.textContent = (data.Homens_Percentual || '0') + '%';
            if (totalMulheres) totalMulheres.textContent = data.Mulheres || '0';
            if (percentualMulheres) percentualMulheres.textContent = (data.Mulheres_Percentual || '0') + '%';
        })
        .catch(error => {
            console.error('Erro ao carregar dados do dashboard:', error);
        });
}

// Chamar a função para carregar os dados assim que a página estiver pronta
document.addEventListener("DOMContentLoaded", loadDashboardData);

function toggleButtons(showOnlyMonitorStatus) {
    const buttons = document.querySelectorAll('#buttonContainer button');
    const infoCardsContainer = document.getElementById('infoCardsContainer');
    
    buttons.forEach(button => {
        if (showOnlyMonitorStatus && button.id !== 'monitorStatusButton') {
            button.classList.add('hidden'); // Esconde todos os botões, exceto "Monitorar Status"
            if (infoCardsContainer) infoCardsContainer.classList.add('hidden');
        } else {
            button.classList.remove('hidden'); // Mostra o botão
            if (infoCardsContainer) infoCardsContainer.classList.remove('hidden');
        }
    });
}

// --- CORRIGIDO: Removido localStorage.getItem('token') ---
function apiRequest(endpoint, method = 'GET', body = null) {
    const headers = {
        'Content-Type': 'application/json'
    };
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

// Função para limpar os campos do formulário de Acolhido
function clearAcolhidoForm() {
    const nome = document.getElementById('nome');
    const telefone = document.getElementById('telefone');
    const situacao = document.getElementById('situacao');
    const observacao = document.getElementById('observacao');
    
    if (nome) nome.value = '';
    if (telefone) telefone.value = '';
    if (situacao) situacao.value = ''; // Limpa o campo de situação
    if (observacao) observacao.value = '';
}

// Função para tratar a submissão do formulário de Acolhido
function handleAcolhidoFormSubmission(event) {
    event.preventDefault();

    // Coleta os dados do formulário de Acolhido
    const nome = document.getElementById('nome').value;
    const telefone = document.getElementById('telefone').value;
    const situacao = document.getElementById('situacao').value;
    const observacao = document.getElementById('observacao').value;
    const dataCadastro = new Date().toISOString(); // Data atual

    // Validação básica
    if (!nome || !telefone || !situacao) {
        alert("Por favor, preencha todos os campos obrigatórios.");
        return;
    }

    // Envia os dados para o servidor
    fetch(`${baseUrl}/api/acolhido`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            nome,
            telefone,
            situacao,
            observacao,
            data_cadastro: dataCadastro,
        }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert("Acolhido cadastrado com sucesso!");
            clearAcolhidoForm(); // Limpa o formulário após o cadastro
            appState.currentView = 'options'; // Volta para a tela de opções
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
// --- FUNÇÃO: Submeter filtro de campanha ---
function handleCampaignSubmit(event) {
    event.preventDefault();

    const dataInicio = document.getElementById('campaignStartDate').value;
    const dataFim = document.getElementById('campaignEndDate').value;
    const idadeMin = document.getElementById('campaignAgeMin').value;
    const idadeMax = document.getElementById('campaignAgeMax').value;
    const genero = document.getElementById('campaignGender').value;
    const eventoNome = document.getElementById('campaignName').value;
    const mensagem = document.getElementById('campaignMessage').value;
    const imagemUrl = document.getElementById('campaignImageUrl').value;

    if (!eventoNome || !mensagem) {
        alert("Preencha pelo menos o nome do evento e a mensagem.");
        return;
    }

    fetch(`${baseUrl}/api/eventos/filtrar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data_inicio: dataInicio, data_fim: dataFim, idade_min: idadeMin, idade_max: idadeMax, genero })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === "success") {
            const visitantes = data.visitantes;
            if (visitantes.length === 0) {
                alert("Nenhum visitante encontrado com esses filtros.");
                return;
            }

            // envia a campanha
            enviarCampanha(visitantes, eventoNome, mensagem, imagemUrl);
        } else {
            alert("Erro ao filtrar visitantes: " + data.message);
        }
    })
    .catch(error => {
        console.error("Erro ao filtrar:", error);
        alert("Erro ao buscar visitantes.");
    });
}

// --- FUNÇÃO: Enviar campanha ---
function enviarCampanha(visitantes, eventoNome, mensagem, imagemUrl) {
    fetch(`${baseUrl}/api/eventos/enviar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ visitantes, evento_nome: eventoNome, mensagem, imagem_url: imagemUrl })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === "success") {
            alert(`Campanha enviada para ${data.enviados.length} visitantes.`);
            appState.currentView = 'options';
            updateUI();
        } else {
            alert("Erro ao enviar campanha: " + data.message);
        }
    })
    .catch(error => {
        console.error("Erro ao enviar campanha:", error);
        alert("Erro de conexão ao enviar campanha.");
    });
}

// Atualização temporizada a cada 20 minutos
setInterval(loadDashboardData, 1200000); // 1200000 ms = 20 minutos


