(function () {
  const API_BASE = '/api/estatisticas';
  const token = localStorage.getItem('jwt_token');
  let chartMensal, chartOrigem, chartFases;

  const authHeaders = () => ({ 'Content-Type': 'application/json', ...(token && { 'Authorization': `Bearer ${token}` }) });

  async function fetchJSON(url) {
    const res = await fetch(url, { headers: authHeaders() });
    if (!res.ok) throw new Error(`Erro ${res.status} em ${url}`);
    return res.json();
  }

  const setText = (id, text) => { const p = document.querySelector(`#${id} p`); if (p) p.textContent = text; };
  const setKPI = (id, value) => {
    const span = document.getElementById(id);
    if (!span) return;
    span.textContent = `${value >= 0 ? '+' : ''}${value}%`;
    span.className = `kpi-change ${value >= 0 ? 'kpi-up' : 'kpi-down'}`;
  };

  const pctChange = (a, b) => (b ? Math.round(((a - b) / b) * 100) : 0);

  const num = x => Number.isFinite(+x) ? +x : 0;
  const fmtInicio = d => String(d?.total ?? '—');
  const fmtGeneroHomens = d => `${num(d?.homens)} (${Math.round((num(d?.homens)/num(d?.total))*100)}%)`;
  const fmtGeneroMulheres = d => `${num(d?.mulheres)} (${Math.round((num(d?.mulheres)/num(d?.total))*100)}%)`;
  const fmtDiscipulado = d => String(d?.total_discipulado ?? '—');
  const fmtOracao = d => String(d?.total_pedidos ?? '—');
  const fmtConversas = d => `Enviadas: ${num(d?.enviadas)} | Recebidas: ${num(d?.recebidas)}`;
  const fmtMensal = arr => {
    if (!arr?.length) return '—';
    const [ult, pen] = arr;
    const diff = pctChange(ult.total, pen?.total);
    return `${ult.mes}: ${ult.total} (${diff >= 0 ? '+' : ''}${diff}%)`;
  };

  // =================== GRÁFICOS ===================
  function renderLine(ctx, data) {
    if (chartMensal) chartMensal.destroy();
    const arr = [...data].reverse();
    chartMensal = new Chart(ctx, {
      type: 'line',
      data: { labels: arr.map(d => d.mes), datasets: [{ data: arr.map(d => d.total), borderColor: '#004f90', backgroundColor: 'rgba(0,79,144,0.2)', fill: true }] },
      options: { responsive: true, plugins: { legend: { display: false } } }
    });
  }

  function renderPie(ctx, data) {
    if (chartOrigem) chartOrigem.destroy();
    chartOrigem = new Chart(ctx, {
      type: 'pie',
      data: { labels: data.map(d => d.origem), datasets: [{ data: data.map(d => d.total), backgroundColor: ['#004f90','#0074D9','#2ECC40','#FF851B','#FF4136','#B10DC9','#3D9970','#39CCCC','#AAAAAA'] }] },
      options: { plugins: { legend: { position: 'bottom' } } }
    });
  }

  function renderBars(ctx, data) {
    if (chartFases) chartFases.destroy();
    chartFases = new Chart(ctx, {
      type: 'bar',
      data: { labels: data.map(f => f.fase), datasets: [{ data: data.map(f => f.total), backgroundColor: '#004f90' }] },
      options: { indexAxis: 'y', plugins: { legend: { display: false } } }
    });
  }

  // =================== CARREGAR ===================
  async function carregar(periodo = 6) {
    try {
      const geral = await fetchJSON(`${API_BASE}/geral?meses=${periodo}`);
      setText('totalVisitantesInicio', fmtInicio(geral.inicio));
      setText('totalHomens', fmtGeneroHomens(geral.genero));
      setText('totalMulheres', fmtGeneroMulheres(geral.genero));
      setText('discipuladosAtivos', fmtDiscipulado(geral.discipulado));
      setText('totalPedidosOracao', fmtOracao(geral.oracao));
      setText('conversasEnviadasRecebidas', fmtConversas(geral.conversas));
      setText('evolucaoMensal', fmtMensal(geral.mensal));

      // KPIs baseados em dados mensais
      const ult = geral.mensal[0], pen = geral.mensal[1];
      setKPI('kpiInicio', pctChange(ult.total, pen?.total));
      setKPI('kpiDiscipulado', pctChange(geral.discipulado.total_discipulado ?? 0, geral.discipulado.prev ?? 0));
      setKPI('kpiOracao', pctChange(geral.oracao.total_pedidos ?? 0, geral.oracao.prev ?? 0));

      renderLine(document.getElementById('graficoMensal'), geral.mensal);
      renderPie(document.getElementById('graficoOrigem'), geral.origem);
      renderBars(document.getElementById('graficoFases'), geral.fases);
    } catch (e) {
      console.error('Erro ao carregar estatísticas:', e);
      alert('Erro ao carregar estatísticas.');
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!token) { window.location.href = '/app/login'; return; }
    const sel = document.getElementById('periodoSelect');
    carregar(sel.value);
    sel.addEventListener('change', () => carregar(sel.value));
  });
})();
