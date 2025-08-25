const baseUrl = 'https://nous-crm-church-v1.onrender.com';

const appState = {
    currentView: 'login', // Pode ser 'login', 'options', 'form', 'whatsappLog', 'statusLog', etc.
    user: null, // O usuário logado
};

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
    // Evento para mostrar o formulário de Acolhido
    document.getElementById('showAcolhidoFormButton').addEventListener('click', () => {
        // Limpa os campos do formulário de Acolhido
        clearAcolhidoForm();
        appState.currentView = 'acolhidoForm';
        updateUI();
    });

    document.getElementById('showFormButton').addEventListener('click', () => {
        appState.currentView = 'form';
        updateUI();
    });

    document.getElementById('showMemberFormButton').addEventListener('click', () => {
        appState.currentView = 'memberForm';
        updateUI();
    });

    document.getElementById('backToOptionsCadastroButton').addEventListener('click', () => {
        appState.currentView = 'options';
        updateUI();
    });

    document.getElementById('backToOptionsCadastroMembro').addEventListener('click', () => {
        appState.currentView = 'options';
        updateUI();
    });

    document.getElementById('backToOptionsCadastroAcolhido').addEventListener('click', () => {
        appState.currentView = 'options';
        updateUI();
    });

    document.getElementById('backToOptionsStatusButton').addEventListener('click', () => {
        appState.currentView = 'options';
        document.getElementById('statusLog').classList.add('hidden'); // Esconde a tabela
        toggleButtons(false); // Exibe todos os botões
    });

    document.getElementById('backToOptionsWhatsappButton').addEventListener('click', () => {
        appState.currentView = 'options';
        updateUI();
    });

    // Evento para submissão do formulário de Acolhido
    document.getElementById('acolhidoForm').addEventListener('submit', handleAcolhidoFormSubmission); // Novo evento
    document.getElementById('sendWhatsappButton').addEventListener('click', handleWhatsappButtonClick);
    document.getElementById('monitorStatusButton').addEventListener('click', monitorStatus);
    document.getElementById('visitorForm').addEventListener('submit', handleFormSubmission);
    document.getElementById('memberForm').addEventListener('submit', handleMemberFormSubmission);
    document.getElementById('loginForm').addEventListener('submit', handleLogin);
}

function updateUI() {
    // Oculta todas as seções
    const allSections = [
        'options', 'formContainer', 'memberFormContainer',
        'whatsappLog', 'statusLog', 'infoCardsContainer',
        'loginContainer', 'acolhidoFormContainer'
    ];

    allSections.forEach(sectionId => {
        document.getElementById(sectionId).classList.add('hidden');
    });

    // Ocultar botões, se necessário (por exemplo, em views de formulário ou detalhes)
    document.getElementById('showFormButton').classList.add('hidden');
    document.getElementById('monitorStatusButton').classList.add('hidden');
    document.getElementById('sendWhatsappButton').classList.add('hidden');
    document.getElementById('showMemberFormButton').classList.add('hidden');
    document.getElementById('infoCardsContainer').classList.add('hidden');
    document.getElementById('showAcolhidoFormButton').classList.add('hidden');

    // Atualiza a exibição conforme o estado atual
    switch (appState.currentView) {
        case 'login':
            document.getElementById('loginContainer').classList.remove('hidden');
            break;
        case 'options':
            document.getElementById('options').classList.remove('hidden');
            document.getElementById('showFormButton').classList.remove('hidden');
            document.getElementById('monitorStatusButton').classList.remove('hidden');
            document.getElementById('sendWhatsappButton').classList.remove('hidden');
            document.getElementById('showMemberFormButton').classList.remove('hidden');
            document.getElementById('showAcolhidoFormButton').classList.remove('hidden');
            document.getElementById('infoCardsContainer').classList.remove('hidden');
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
        document.getElementById('statusLog').classList.remove('hidden');

        loadPageData(currentPage); // Carrega a primeira página
    })
    .catch(error => showError(`Erro ao buscar status: ${error.message}`));
}

// Eventos de paginação
document.getElementById('nextPageButton').addEventListener('click', () => {
    if ((currentPage * itemsPerPage) < statusData.length) {
        currentPage++;
        loadPageData(currentPage);
    }
});

document.getElementById('prevPageButton').addEventListener('click', () => {
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
            // Limpar o formulário após o cadastro bem-sucedido
            document.getElementById('visitorForm').reset();
            // Limpar mensagens de erro, se houver
            clearError();
        })
        .catch(error => showError(`Erro ao registrar: ${error.message}`, 'registerErrorContainer'));
}

function showError(message, containerId) {
    // Seleciona o container onde a mensagem de erro será exibida
    const errorContainer = document.getElementById(containerId);

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
    errorContainer.innerHTML = '';
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
            document.getElementById('totalVisitantes').textContent = data.totalVisitantes || '0';
            document.getElementById('totalMembros').innerText = data.totalMembros;
            document.getElementById('totalhomensMembro').innerText = data.totalhomensMembro;
            document.getElementById('totalmulheresMembro').innerText = data.totalmulheresMembro;
            document.getElementById('discipuladosAtivos').textContent = data.discipuladosAtivos || '0';
            document.getElementById("totalHomensDiscipulado").textContent = data.totalHomensDiscipulado || '0';
            document.getElementById("totalMulheresDiscipulado").textContent = data.totalMulheresDiscipulado || '0';

            document.getElementById('grupos_comunhao').textContent = data.grupos_comunhao || '0';

            // Exibir dados de gênero
            document.getElementById('totalHomens').textContent = data.Homens || '0';
            document.getElementById('percentualHomens').textContent = data.Homens_Percentual + '%' || '0%';
            document.getElementById('totalMulheres').textContent = data.Mulheres || '0';
            document.getElementById('percentualMulheres').textContent = data.Mulheres_Percentual + '%' || '0%';
        })
        .catch(error => {
            console.error('Erro ao carregar dados do dashboard:', error);
        });
}


// Chamar a função para carregar os dados assim que a página estiver pronta
document.addEventListener("DOMContentLoaded", loadDashboardData);

function toggleButtons(showOnlyMonitorStatus) {
    const buttons = document.querySelectorAll('#buttonContainer button');
    buttons.forEach(button => {
        if (showOnlyMonitorStatus && button.id !== 'monitorStatusButton') {
            button.classList.add('hidden'); // Esconde todos os botões, exceto "Monitorar Status"
            document.getElementById('infoCardsContainer').classList.add('hidden');
        } else {
            button.classList.remove('hidden'); // Mostra o botão
            document.getElementById('infoCardsContainer').classList.remove('hidden');
        }
    });
}

function apiRequest(endpoint, method = 'GET', body = null) {
    const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`, // Corrigido para interpolação correta
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
    document.getElementById('nome').value = '';
    document.getElementById('telefone').value = '';
    document.getElementById('situacao').value = ''; // Limpa o campo de situação
    document.getElementById('observacao').value = '';
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

// Atualização temporizada a cada 10 segundos
setInterval(loadDashboardData, 1200000); // 10000 ms = 60 segundos

