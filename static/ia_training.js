// ==============================
// ia_training.js - Módulo Integra+ IA
// ==============================


// Utilitários locais
function $(id) { return document.getElementById(id); }

function getAuthHeaders(includeJson = true) {
  const headers = includeJson ? { 'Content-Type': 'application/json' } : {};
  const token = localStorage.getItem('jwt_token');
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

// Estado temporário
let perguntasPendentes = [];

// ------------------------------
// Carregar perguntas pendentes
// ------------------------------
function loadPendingQuestions() {
  fetch(`${baseUrl}/api/ia/pending-questions`, { headers: getAuthHeaders(true) })
    .then(r => r.json())
    .then(data => {
      perguntasPendentes = data?.questions || [];
      const list = $('pendingQuestionsList');
      const countEl = $('pendingQuestionsCount');
      if (!list || !countEl) return;

      countEl.textContent = perguntasPendentes.length;
      list.innerHTML = '';

      if (perguntasPendentes.length === 0) {
        list.innerHTML = '<li>Nenhuma pergunta pendente.</li>';
        return;
      }

      perguntasPendentes.forEach((q, idx) => {
        const li = document.createElement('li');
        li.textContent = q.question || q.pergunta || '(sem texto)';
        li.dataset.index = idx;
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

// ------------------------------
// Mostrar formulário de ensino
// ------------------------------
function toggleTeachForm(show) {
  $('teachForm')?.classList.toggle('hidden', !show);
  $('trainingList')?.classList.toggle('hidden', !!show);
}

function showTeachForm(index) {
  const q = perguntasPendentes[index];
  if (!q) return;
  $('teachQuestion').value = q.question || q.pergunta || '';
  $('teachAnswer').value = '';
  $('teachCategory').value = '';
  toggleTeachForm(true);
}

// ------------------------------
// Enviar aprendizado
// ------------------------------
function handleTeachSubmit(e) {
  e.preventDefault();
  const question = $('teachQuestion').value.trim();
  const answer = $('teachAnswer').value.trim();
  const category = $('teachCategory').value.trim();

  if (!question || !answer || !category) {
    alert('Preencha pergunta, resposta e categoria.');
    return;
  }

  fetch(`${baseUrl}/api/ia/teach`, {
    method: 'POST',
    headers: getAuthHeaders(true),
    body: JSON.stringify({ question, answer, category })
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
    .catch(err => alert('Erro de conexão: ' + err.message));
}

// ------------------------------
// Inicialização automática
// ------------------------------
document.addEventListener('DOMContentLoaded', () => {
  if (!localStorage.getItem('jwt_token')) {
    window.location.href = '/app/login';
    return;
  }

  // Bind do formulário
  const form = $('teachIAForm');
  if (form) form.addEventListener('submit', handleTeachSubmit);

  const cancel = $('cancelTeachButton');
  if (cancel) cancel.addEventListener('click', () => toggleTeachForm(false));

  loadPendingQuestions();
});
