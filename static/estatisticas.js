(function () {
  const API_BASE = '/api/estatisticas';
  const token = localStorage.getItem('jwt_token');
  let charts = {};

  async function fetchJSON(url) {
    const res = await fetch(url, { headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` } });
    if (!res.ok) throw new Error(`Erro ${res.status} em ${url}`);
    return res.json();
  }

  function setText(id, text) {
    const p = document.querySelector(`#${id} p`);
    if (p) p.textContent = text;
  }

  function renderChart(id, type, labels, data, colors) {
    if (charts[id]) charts[id].destroy();
    const ctx = document.getElementById(id);
    charts[id] = new Chart(ctx, {
      type,
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: colors || [
            '#004f90', '#0074D9', '#2ECC40', '#FF851B',
            '#FF4136', '#B10DC9', '#3D9970', '#39CCCC', '#AAAAAA'
          ]
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'bottom' } },
        indexAxis: type === 'bar' ? 'y' : 'x'
      }
    });
  }

  async function carregar(periodo = 6) {
    const geral = await fetchJSON(`${API_BASE}/geral?meses=${periodo}`);

    // KPIs
    setText('totalVisitantesInicio', geral.inicio.total);
    setText('discipuladosAtivos', geral.discipulado.total_discipulado);
    setText('totalPedidosOracao', geral.oracao.total_pedidos);
    setText('totalHomens', geral.genero.homens);
    setText('totalMulheres', geral.genero.mulheres);
    setText('conversasEnviadasRecebidas', `Enviadas: ${geral.conversas.enviadas} | Recebidas: ${geral.conversas.recebidas}`);

    // Gráficos principais
    renderChart('graficoMensal', 'line', geral.mensal.map(m => m.mes), geral.mensal.map(m => m.total));
    renderChart('graficoOrigem', 'pie', geral.origem.map(o => o.origem), geral.origem.map(o => o.total));
    renderChart('graficoFases', 'bar', geral.fases.map(f => f.fase), geral.fases.map(f => f.total));

    // Demografia
    const idade = geral.demografia.idade;
    setText('idadeMedia', `${idade.idade_media ?? '—'} anos | Jovens: ${idade.jovens} | Adultos: ${idade.adultos} | Idosos: ${idade.idosos}`);

    renderChart('graficoEstadoCivil', 'pie',
      geral.demografia.estado_civil.map(e => e.estado_civil),
      geral.demografia.estado_civil.map(e => e.total)
    );

    renderChart('graficoCidades', 'bar',
      geral.demografia.cidades.map(c => c.cidade),
      geral.demografia.cidades.map(c => c.total)
    );
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!token) return (window.location.href = '/app/login');
    const sel = document.getElementById('periodoSelect');
    carregar(sel.value);
    sel.addEventListener('change', () => carregar(sel.value));
  });
})();
