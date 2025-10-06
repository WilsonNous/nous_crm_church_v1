// estatisticas.js — carrega cards da tela de Estatísticas

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
    // Preenche o <p> do card; se não achar, cai no container
    const p = document.querySelector(`#${id} p`);
    if (p) { p.textContent = text; return; }
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function num(x, def = 0) {
    const n = Number(x);
    return Number.isFinite(n) ? n : def;
  }

  // Normalizadores por tipo de endpoint
  function fmtInicio(data) {
    // aceita {total}, {valor}, {count}...
    return String(data?.total ?? data?.valor ?? data?.count ?? '—');
  }

  function fmtGeneroHomens(d) {
    // aceita {Homens}, {homens}, {masculino}, ou {percentualHomens}
    return `${num(d?.Homens ?? d?.homens ?? d?.masculino, 0)} (${num(d?.Homens_Percentual ?? d?.percentualHomens, 0)}%)`;
  }

  function fmtGeneroMulheres(d) {
    // aceita {Mulheres}, {mulheres}, {feminino}, ou {percentualMulheres}
    return `${num(d?.Mulheres ?? d?.mulheres ?? d?.feminino, 0)} (${num(d?.Mulheres_Percentual ?? d?.percentualMulheres, 0)}%)`;
  }

  function fmtDiscipulado(d) {
    // aceita {ativos}, {total}, {valor}
    return String(d?.ativos ?? d?.total ?? d?.valor ?? '—');
  }

  function fmtOracao(d) {
    return String(d?.total ?? d?.valor ?? '—');
  }

  function fmtOrigem(d) {
    // aceita lista/objeto com contagens por origem
    if (!d) return '—';
    if (Array.isArray(d)) {
      // ex.: [{origem:'instagram', total:10}, ...]
      return d.map(x => `${x.origem ?? x.source ?? '—'}: ${num(x.total ?? x.count)}`).join(' | ') || '—';
    }
    if (typeof d === 'object') {
      // ex.: {instagram:10, convite:5}
      return Object.entries(d).map(([k, v]) => `${k}: ${num(v)}`).join(' | ') || '—';
    }
    return String(d);
  }

  function fmtMensal(d) {
    // aceita lista [{mes:'2025-08', total: 23}, ...] ou objeto
    if (!d) return '—';
    const arr = Array.isArray(d) ? d : d.series ?? d.meses ?? [];
    if (!Array.isArray(arr) || !arr.length) return '—';
    const ultimo = arr[arr.length - 1];
    const penultimo = arr.length > 1 ? arr[arr.length - 2] : null;
    const totalUlt = num(ultimo?.total ?? ultimo?.count);
    const totalPen = num(penultimo?.total ?? penultimo?.count);
    const delta = totalPen ? Math.round(((totalUlt - totalPen) / totalPen) * 100) : 0;
    const mesFmt = (ultimo?.mes ?? ultimo?.month ?? 'mês');
    return `${mesFmt}: ${totalUlt} (${delta >= 0 ? '+' : ''}${delta}%)`;
  }

  function fmtConversas(d) {
    // aceita {enviadas, recebidas} ou {sent, received} etc.
    const enviadas = num(d?.enviadas ?? d?.sent);
    const recebidas = num(d?.recebidas ?? d?.received);
    return `Enviadas: ${enviadas} | Recebidas: ${recebidas}`;
  }

  async function init() {
    // bloqueio se não logado
    if (!token) { window.location.href = '/app/login'; return; }

    try {
      const [
        inicio, genero, discipulado, oracao, origem, mensal, conversas
      ] = await Promise.all([
        fetchJSON(`${API_BASE}/inicio`),
        fetchJSON(`${API_BASE}/genero`),
        fetchJSON(`${API_BASE}/discipulado`),
        fetchJSON(`${API_BASE}/oracao`),
        fetchJSON(`${API_BASE}/origem`),
        fetchJSON(`${API_BASE}/mensal`),
        fetchJSON(`${API_BASE}/conversas`)
      ]);

      setCardText('totalVisitantesInicio', fmtInicio(inicio));
      setCardText('totalHomens',            fmtGeneroHomens(genero));
      setCardText('totalMulheres',          fmtGeneroMulheres(genero));
      setCardText('discipuladosAtivos',     fmtDiscipulado(discipulado));
      setCardText('totalPedidosOracao',     fmtOracao(oracao));
      setCardText('origemCadastro',         fmtOrigem(origem));
      setCardText('evolucaoMensal',         fmtMensal(mensal));
      setCardText('conversasEnviadasRecebidas', fmtConversas(conversas));
    } catch (err) {
      console.error(err);
      alert('Erro ao carregar estatísticas.');
    }
  }

  // dispara só na página de estatísticas
  document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('statisticsContainer')) init();
  });
})();
