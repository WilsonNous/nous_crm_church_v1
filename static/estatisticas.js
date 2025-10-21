// estatisticas.js — versão otimizada (carrega todas as estatísticas em uma requisição)

(function () {
  const API_BASE = '/api/estatisticas';
  const token = localStorage.getItem('jwt_token');

  function authHeaders() {
    const h = { 'Content-Type': 'application/json' };
    if (token) h['Authorization'] = `Bearer ${token}`;
    return h;
  }

  async function fetchJSON(url) {
    const res = await fetch(url, { headers: authHeaders() });
    if (!res.ok) throw new Error(`Falha ${res.status} em ${url}`);
    return res.json();
  }

  function setCardText(id, text) {
    const p = document.querySelector(`#${id} p`);
    if (p) p.textContent = text;
  }

  const num = (x, def = 0) => Number.isFinite(+x) ? +x : def;

  // ----------------------------
  // Funções de formatação
  // ----------------------------
  const fmtInicio = d => String(d?.total ?? '—');
  const fmtGeneroHomens = d => `${num(d?.homens)} (${Math.round((num(d?.homens)/num(d?.total))*100)}%)`;
  const fmtGeneroMulheres = d => `${num(d?.mulheres)} (${Math.round((num(d?.mulheres)/num(d?.total))*100)}%)`;
  const fmtDiscipulado = d => String(d?.total_discipulado ?? '—');
  const fmtOracao = d => String(d?.total_pedidos ?? '—');
  const fmtOrigem = arr => Array.isArray(arr) ? arr.map(x => `${x.origem}: ${num(x.total)}`).join(' | ') : '—';
  const fmtMensal = arr => {
    if (!Array.isArray(arr) || !arr.length) return '—';
    const ult = arr[0], pen = arr[1];
    const diff = pen ? Math.round(((ult.total - pen.total) / pen.total) * 100) : 0;
    return `${ult.mes}: ${ult.total} (${diff >= 0 ? '+' : ''}${diff}%)`;
  };
  const fmtConversas = d => `Enviadas: ${num(d?.enviadas)} | Recebidas: ${num(d?.recebidas)}`;

  // ----------------------------
  // Inicialização
  // ----------------------------
  async function init() {
    if (!token) { window.location.href = '/app/login'; return; }

    try {
      const geral = await fetchJSON(`${API_BASE}/geral`);
      setCardText('totalVisitantesInicio', fmtInicio(geral.inicio));
      setCardText('totalHomens', fmtGeneroHomens(geral.genero));
      setCardText('totalMulheres', fmtGeneroMulheres(geral.genero));
      setCardText('discipuladosAtivos', fmtDiscipulado(geral.discipulado));
      setCardText('totalPedidosOracao', fmtOracao(geral.oracao));
      setCardText('origemCadastro', fmtOrigem(geral.origem));
      setCardText('evolucaoMensal', fmtMensal(geral.mensal));
      setCardText('conversasEnviadasRecebidas', fmtConversas(geral.conversas));
    } catch (err) {
      console.error('Erro ao carregar estatísticas:', err);
      alert('Erro ao carregar estatísticas.');
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('statisticsContainer')) init();
  });
})();
