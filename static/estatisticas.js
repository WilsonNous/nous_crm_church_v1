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
    const geral = await fetchJSON(`${API}/geral?meses=${meses}`);

    console.log("📊 Estatísticas Geral:", geral);

    // KPIs
    setText("totalVisitantesInicio", geral.total?.total);
    setText("totalHomens", geral.genero?.homens);
    setText("totalMulheres", geral.genero?.mulheres);

    // Evolução mensal
    renderChart(
      "graficoMensal",
      "line",
      safeArray(geral.mensal).map(x => x.mes),
      safeArray(geral.mensal).map(x => Number(x.total))
    );

    // Estado civil
    renderChart(
      "graficoEstadoCivil",
      "pie",
      safeArray(geral.estado_civil).map(x => x.estado_civil),
      safeArray(geral.estado_civil).map(x => Number(x.total))
    );

    // Cidades
    renderChart(
      "graficoCidades",
      "bar",
      safeArray(geral.cidades).map(x => x.cidade),
      safeArray(geral.cidades).map(x => Number(x.total))
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
    if (!token) return window.location = "/app/login";

    setupTabs();
    carregarGeral();

    document
      .getElementById("periodoSelect")
      .addEventListener("change", carregarGeral);
  });
})();
