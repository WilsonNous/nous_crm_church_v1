(function () {
  const token = localStorage.getItem("jwt_token");

  const API_BASE = "/api";
  const API = `${API_BASE}/estatisticas`;

  let charts = {};

  // ================================
  // UTILITÁRIOS
  // ================================
  function safeArray(v) {
    return Array.isArray(v) ? v : [];
  }

  async function fetchJSON(url) {
    const res = await fetch(url, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (!res.ok) throw new Error(`Erro ao acessar ${url}`);
    return res.json();
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
        plugins: { legend: { position: "bottom" } }
      }
    });
  }

  // ================================
  // ABA: GERAL
  // ================================
  async function carregarGeral() {
    const meses = document.getElementById("periodoSelect").value;
    const response = await fetchJSON(`${API}/geral?meses=${meses}`);

    console.log("📊 Estatísticas Geral (RAW):", response);

    const visitantes = response.visitantes || {};

    // =========================
    // KPIs – VISITANTES
    // =========================
    setText("totalVisitantesInicio", visitantes.inicio?.total);
    setText("totalHomens", visitantes.genero?.homens);
    setText("totalMulheres", visitantes.genero?.mulheres);

    // =========================
    // EVOLUÇÃO MENSAL
    // =========================
    renderChart(
      "graficoMensal",
      "line",
      safeArray(visitantes.mensal).map(x => x.mes),
      safeArray(visitantes.mensal).map(x => Number(x.total))
    );

    // =========================
    // ESTADO CIVIL
    // =========================
    renderChart(
      "graficoEstadoCivil",
      "pie",
      safeArray(visitantes.demografia?.estado_civil).map(x => x.estado_civil),
      safeArray(visitantes.demografia?.estado_civil).map(x => Number(x.total))
    );

    // =========================
    // CIDADES
    // =========================
    renderChart(
      "graficoCidades",
      "bar",
      safeArray(visitantes.demografia?.cidades).map(x => x.cidade),
      safeArray(visitantes.demografia?.cidades).map(x => Number(x.total))
    );
  }

  // ================================
  // TROCA DE ABAS
  // ================================
  function setupTabs() {
    document.querySelectorAll(".tab-button").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-button").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

        btn.classList.add("active");
        document.getElementById(btn.dataset.tab).classList.add("active");

        if (btn.dataset.tab === "tab-geral") carregarGeral();
      });
    });
  }

  // ================================
  // INIT
  // ================================
  document.addEventListener("DOMContentLoaded", () => {
    if (!token) {
      window.location = "/app/login";
      return;
    }

    setupTabs();
    carregarGeral();

    document
      .getElementById("periodoSelect")
      .addEventListener("change", carregarGeral);
  });
})();
