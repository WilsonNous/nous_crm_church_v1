// ============================================
// campanhas.js - CRM Church (v3.2)
// ============================================
// Controle de Campanhas e Eventos - Ministério de Integração
// Envio 100% texto (sem imagem)
// ============================================
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
  // 📢 ENVIAR CAMPANHA (texto puro)
  // -----------------------------------------------------------
  async function enviarCampanha(event) {
    event.preventDefault();
    const form = event.target;

    // Coleta filtros ativos na tela
    const filtroForm = document.getElementById('filtroVisitantesForm');
    const filtros = {
      dataInicio: filtroForm.dataInicio.value,
      dataFim: filtroForm.dataFim.value,
      idadeMin: filtroForm.idadeMin.value || null,
      idadeMax: filtroForm.idadeMax.value || null,
      genero: filtroForm.genero.value || null,
    };

    // 🔹 Monta payload (sem imagem)
    const payload = {
      nome_evento: form.eventoNome.value,
      mensagem: form.mensagemEvento.value,
      ...filtros
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
      document.querySelector('main').appendChild(container);
    }

    if (!statusList.length) {
      container.innerHTML = `
        <h3>Status das Campanhas</h3>
        <p>Nenhuma campanha registrada.</p>
      `;
      return;
    }

    // Agrupar por evento
    const grupos = {};
    statusList.forEach(s => {
      const evento = s.nome_evento || 'Campanha Desconhecida';
      if (!grupos[evento]) grupos[evento] = [];
      grupos[evento].push(s);
    });

    let html = `
      <h3>Status das Campanhas</h3>
      <button class="btn-danger" onclick="limparStatus()">🧹 Limpar Histórico</button>
    `;

    for (const evento in grupos) {
      const itens = grupos[evento];
      html += `
        <details class="status-box" open>
          <summary><strong>${evento}</strong> <small>(${itens.length} registros)</small></summary>
          <div class="scroll-area">
            <table class="table-list compact">
              <thead>
                <tr><th>Data</th><th>Status</th></tr>
              </thead>
              <tbody>
                ${itens.map(s => `
                  <tr>
                    <td>${s.data_envio || '-'}</td>
                    <td class="status-${s.status?.toLowerCase() || 'pendente'}">${formatarStatus(s.status)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </details>
      `;
    }

    container.innerHTML = html;
  }

  function formatarStatus(status) {
    if (!status) return '-';
    const s = status.toLowerCase();
    if (s.includes('enviado')) return '✅ Enviado';
    if (s.includes('pendente')) return '⚠️ Pendente';
    if (s.includes('falha') || s.includes('erro')) return '❌ Falha';
    return status;
  }

  // -----------------------------------------------------------
  // 🧹 LIMPAR HISTÓRICO DE CAMPANHAS
  // -----------------------------------------------------------
  async function limparStatus() {
    if (!confirm("Tem certeza que deseja limpar o histórico de campanhas?")) return;

    try {
      const resp = await fetch(`${API_BASE_URL}/api/campanhas/limpar`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${localStorage.getItem('jwt_token')}`
        }
      });

      const data = await resp.json();
      alert(data.message || "🧹 Histórico de campanhas limpo com sucesso!");
      carregarStatus();
    } catch (err) {
      console.error("Erro ao limpar histórico:", err);
      alert("❌ Falha ao limpar histórico de campanhas.");
    }
  }

  // -----------------------------------------------------------
  // 🔗 Expõe funções globais usadas no HTML
  // -----------------------------------------------------------
  window.filtrarVisitantes = filtrarVisitantes;
  window.enviarCampanha = enviarCampanha;
  window.reprocessarFalhas = reprocessarFalhas;
  window.limparStatus = limparStatus;
})();
