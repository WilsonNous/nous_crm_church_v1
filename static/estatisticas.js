(function () {
  const token = localStorage.getItem("jwt_token");

  const API_BASE = "/api";
  const API = `${API_BASE}/estatisticas`;

  let charts = {};
  let cacheEstatisticas = null;

  // ================================
  // UTILITÁRIOS
  // ================================
  function safeArray(v) {
    return Array.isArray(v) ? v : [];
  }

  async function fetchEstatisticas(meses = null) {
    if (cacheEstatisticas && meses === null) return cacheEstatisticas;

    const url = meses !== null
      ? `${API}/geral?meses=${meses}`
      : `${API}/geral`;

    const res = await fetch(url, {
      headers: { "Authorization": `Bearer ${token}` }
    });

    if (!res.ok) throw new Error("Erro ao buscar estatísticas");

    cacheEstatisticas = await res.json();
    return cacheEstatisticas;
  }

  function setText(id, value) {
    const el = document.querySelector(`#${id} p`);
    if (el) el.textContent = value ?? "—";
  }

  function renderChart(id, type, labels, data) {
    const ctx = document.getElementById(id);
    if (!ctx) return;

    if (charts[id]) charts[id].destroy();

    charts[id] = new Chart(ctx, {
      type,
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: [
            "#004f90",
            "#FF6B6B",
            "#2ECC40",
            "#FFCC00",
            "#7FDBFF",
            "#B10DC9",
            "#AAAAAA"
          ]
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: "bottom" }
        }
      }
    });
  }

  // ================================
  // ABA: GERAL (VISITANTES)
  // ================================
  async function carregarGeral() {
    const selectPeriodo = document.getElementById("periodoSelect");
    const meses = selectPeriodo ? selectPeriodo.value : 6;

    cacheEstatisticas = null;

    const data = await fetchEstatisticas(meses);
    const v = data.visitantes || {};

    // KPIs
    setText("totalVisitantesInicio", v.inicio?.total);
    setText("discipuladosAtivos", v.discipulado?.total_discipulado);
    setText("totalPedidosOracao", v.oracao?.total_pedidos);
    setText("totalHomens", v.genero?.homens);
    setText("totalMulheres", v.genero?.mulheres);

    setText(
      "conversasEnviadasRecebidas",
      `Enviadas: ${v.conversas?.enviadas ?? 0} | Recebidas: ${v.conversas?.recebidas ?? 0}`
    );

    // Gráficos
    renderChart(
      "graficoMensal",
      "line",
      safeArray(v.mensal).map(x => x.mes),
      safeArray(v.mensal).map(x => Number(x.total))
    );

    renderChart(
      "graficoOrigem",
      "pie",
      safeArray(v.origem).map(x => x.origem),
      safeArray(v.origem).map(x => Number(x.total))
    );

    renderChart(
      "graficoFases",
      "bar",
      safeArray(v.fases).map(x => x.fase),
      safeArray(v.fases).map(x => Number(x.total))
    );

    // Demografia
    const idade = v.demografia?.idade || {};
    setText(
      "idadeMedia",
      `${idade.idade_media ?? "—"} anos | Jovens: ${idade.jovens ?? 0} | Adultos: ${idade.adultos ?? 0} | Idosos: ${idade.idosos ?? 0}`
    );

    renderChart(
      "graficoEstadoCivil",
      "pie",
      safeArray(v.demografia?.estado_civil).map(x => x.estado_civil),
      safeArray(v.demografia?.estado_civil).map(x => Number(x.total))
    );

    renderChart(
      "graficoCidades",
      "bar",
      safeArray(v.demografia?.cidades).map(x => x.cidade),
      safeArray(v.demografia?.cidades).map(x => Number(x.total))
    );
  }

  // ================================
  // ABA: MEMBROS
  // ================================
  async function carregarMembros() {
    const data = await fetchEstatisticas();
    const m = data.membros || {};

    // KPIs
    setText("membrosTotal", m.total?.total);
    setText("membrosHomens", m.genero?.homens);
    setText("membrosMulheres", m.genero?.mulheres);

    // Caminhada espiritual
    renderChart(
      "graficoMembrosNovoComeco",
      "pie",
      ["Fizeram", "Não fizeram"],
      [
        Number(m.novo_comeco?.fizeram ?? 0),
        Number(m.novo_comeco?.nao_fizeram ?? 0)
      ]
    );

    renderChart(
      "graficoMembrosClasse",
      "pie",
      ["Fizeram", "Não fizeram"],
      [
        Number(m.classe?.fizeram ?? 0),
        Number(m.classe?.nao_fizeram ?? 0)
      ]
    );

    renderChart(
      "graficoMembrosConsagracao",
      "pie",
      ["Consagrados", "Não consagrados"],
      [
        Number(m.consagracao?.consagrados ?? 0),
        Number(m.consagracao?.nao_consagrados ?? 0)
      ]
    );

    // Perfil
    renderChart(
      "graficoMembrosEstadoCivil",
      "bar",
      safeArray(m.estado_civil).map(x => x.estado_civil),
      safeArray(m.estado_civil).map(x => Number(x.total))
    );

    renderChart(
      "graficoMembrosCidades",
      "bar",
      safeArray(m.cidades).map(x => x.cidade),
      safeArray(m.cidades).map(x => Number(x.total))
    );

    // Evolução
    renderChart(
      "graficoMembrosMensal",
      "line",
      safeArray(m.mensal).map(x => x.mes),
      safeArray(m.mensal).map(x => Number(x.total))
    );
  }

  // ================================
  // TROCA DE ABAS
  // ================================
  function setupTabs() {
    document.querySelectorAll(".tab-button").forEach(btn => {
      btn.addEventListener("click", async () => {
        document.querySelectorAll(".tab-button").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

        btn.classList.add("active");
        document.getElementById(btn.dataset.tab).classList.add("active");

        if (btn.dataset.tab === "tab-geral") await carregarGeral();
        if (btn.dataset.tab === "tab-membros") await carregarMembros();
      });
    });
  }

  // ================================
  // INIT
  // ================================
  document.addEventListener("DOMContentLoaded", async () => {
    if (!token) {
      window.location = "/app/login";
      return;
    }

    setupTabs();
    await carregarGeral();

    document
      .getElementById("periodoSelect")
      ?.addEventListener("change", carregarGeral);
  });
})();
