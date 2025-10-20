// ============================================
// campanhas.js - CRM Church (v3.1)
// ============================================
// Controle de Campanhas e Eventos - Ministério de Integração
// ---------------------------------------------
(() => {
  const API_BASE_URL = 'https://nous-crm-church-v1.onrender.com';

  // -----------------------------------------------------------
  // 🧭 Proteção: redireciona se não estiver logado
  // -----------------------------------------------------------
  document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('jwt_token');
    if (!token) {
      window.location.href = '/app/login';
    } else {
      carregarStatus(); // carrega status de campanhas ao abrir
    }
  });

  // -----------------------------------------------------------
  // 🔍 FILTRAR VISITANTES
  // -----------------------------------------------------------
  async function filtrarVisitantes(event) {
    event.preventDefault();
    const form = event.target;

    const filtros = {
      dataInicio: form.dataInicio.value,
      dataFim: form.dataFim.value,
      idadeMin: form.idadeMin.value || null,
      idadeMax: form.idadeMax.value || null,
      genero: form.genero.value || null,
    };

    try {
      const resp = await fetch(`${API_BASE_URL}/api/visitantes/filtro`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`
        },
        body: JSON.stringify(filtros)
      });

      const data = await resp.json();
      renderVisitantes(data.visitantes || []);
    } catch (err) {
      console.error('Erro ao buscar visitantes:', err);
      alert('❌ Falha ao carregar visitantes.');
    }
  }

  // Renderiza lista de visitantes filtrados
  function renderVisitantes(lista) {
    const container = document.getElementById('visitantesList');
    if (!lista.length) {
      container.innerHTML = '<p>Nenhum visitante encontrado com os filtros aplicados.</p>';
      return;
    }

    const html = `
      <table class="table-list">
        <thead>
          <tr>
            <th>Nome</th><th>Gênero</th><th>Idade</th><th>Telefone</th><th>Cadastro</th>
          </tr>
        </thead>
        <tbody>
          ${lista.map(v => `
            <tr>
              <td>${v.nome}</td>
              <td>${v.genero || '-'}</td>
              <td>${v.idade || '-'}</td>
              <td>${v.telefone}</td>
              <td>${v.data_cadastro}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    `;
    container.innerHTML = html;
  }

  // -----------------------------------------------------------
  // 📢 ENVIAR CAMPANHA
  // -----------------------------------------------------------
  async function enviarCampanha(event) {
    event.preventDefault();
    const form = event.target;

    const payload = {
      nome_evento: form.eventoNome.value,
      mensagem: form.mensagemEvento.value,
      imagem: form.imagemUrl.value
    };

    if (!confirm(`Deseja enviar a campanha "${payload.nome_evento}"?`)) return;

    try {
      const resp = await fetch(`${API_BASE_URL}/api/campanhas/enviar`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`
        },
        body: JSON.stringify(payload)
      });

      const data = await resp.json();
      alert(data.message || '✅ Campanha enviada com sucesso!');
      carregarStatus();
    } catch (err) {
      console.error('Erro ao enviar campanha:', err);
      alert('❌ Erro ao enviar campanha.');
    }
  }

  // -----------------------------------------------------------
  // 🔄 REPROCESSAR FALHAS
  // -----------------------------------------------------------
  async function reprocessarFalhas() {
    if (!confirm('Deseja reprocessar as falhas da última campanha?')) return;

    try {
      const resp = await fetch(`${API_BASE_URL}/api/campanhas/reprocessar`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('jwt_token')}` }
      });

      const data = await resp.json();
      alert(data.message || '🔄 Reprocessamento concluído.');
      carregarStatus();
    } catch (err) {
      console.error('Erro ao reprocessar falhas:', err);
      alert('❌ Falha ao reprocessar.');
    }
  }

  // -----------------------------------------------------------
  // 📊 STATUS DAS CAMPANHAS
  // -----------------------------------------------------------
  async function carregarStatus() {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/campanhas/status`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('jwt_token')}` }
      });
      const data = await resp.json();
      renderStatus(data.status || []);
    } catch (err) {
      console.error('Erro ao carregar status:', err);
    }
  }

  // Renderiza status de campanhas
  function renderStatus(statusList) {
    let container = document.getElementById('statusCampanhas');
    if (!container) {
      container = document.createElement('section');
      container.id = 'statusCampanhas';
      container.innerHTML = '<h3>Status das Campanhas</h3>';
      document.querySelector('main').appendChild(container);
    }

    if (!statusList.length) {
      container.innerHTML = '<p>Nenhuma campanha registrada ainda.</p>';
      return;
    }

    const html = `
      <h3>Status das Campanhas</h3>
      <table class="table-list">
        <thead>
          <tr><th>Data</th><th>Evento</th><th>Enviados</th><th>Falhas</th><th>Status</th></tr>
        </thead>
        <tbody>
          ${statusList.map(s => `
            <tr>
              <td>${s.data_envio}</td>
              <td>${s.nome_evento}</td>
              <td>${s.enviados}</td>
              <td>${s.falhas}</td>
              <td>${s.status}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    `;
    container.innerHTML = html;
  }

  // -----------------------------------------------------------
  // 🔗 Expõe funções globais usadas no HTML
  // -----------------------------------------------------------
  window.filtrarVisitantes = filtrarVisitantes;
  window.enviarCampanha = enviarCampanha;
  window.reprocessarFalhas = reprocessarFalhas;
})();
