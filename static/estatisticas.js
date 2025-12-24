(function () {
  const token = localStorage.getItem("jwt_token");

  const API_BASE = "/api";
  const API_EST = `${API_BASE}/estatisticas/geral`;
  const API_MEMBROS = `${API_BASE}/membros`;

  let charts = {};
  let cacheEst = null;
  let listaMembros = [];
  let selecionados = new Set();

  // ======================================================
  // UTIL
  // ======================================================
  const safeArray = v => Array.isArray(v) ? v : [];

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
            "#004f90", "#FF6B6B", "#2ECC40",
            "#FFCC00", "#7FDBFF", "#B10DC9", "#AAAAAA"
          ]
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } }
      }
    });
  }

  async function fetchEstatisticas() {
    if (cacheEst) return cacheEst;

    const res = await fetch(API_EST, {
      headers: { Authorization: `Bearer ${token}` }
    });

    cacheEst = await res.json();
    return cacheEst;
  }

  // ======================================================
  // ABA: GERAL (VISITANTES)
  // ======================================================
  async function carregarGeral() {
    const data = await fetchEstatisticas();
    const v = data.visitantes || {};

    setText("totalVisitantesInicio", v.inicio?.total);
    setText("discipuladosAtivos", v.discipulado?.total_discipulado);
    setText("totalPedidosOracao", v.oracao?.total_pedidos);
    setText("totalHomens", v.genero?.homens);
    setText("totalMulheres", v.genero?.mulheres);

    setText(
      "conversasEnviadasRecebidas",
      `Enviadas: ${v.conversas?.enviadas ?? 0} | Recebidas: ${v.conversas?.recebidas ?? 0}`
    );

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

  // ======================================================
  // ABA: MEMBROS
  // ======================================================
  async function carregarMembros() {
    const data = await fetchEstatisticas();
    const m = data.membros || {};

    setText("membrosTotal", m.total?.total);
    setText("membrosHomens", m.genero?.homens);
    setText("membrosMulheres", m.genero?.mulheres);
  }

  // ======================================================
  // LISTA DE MEMBROS (BACKEND REAL)
  // ======================================================
  async function carregarListaMembros(termo = "") {
    const res = await fetch(`${API_MEMBROS}?q=${encodeURIComponent(termo)}`, {
      headers: { Authorization: `Bearer ${token}` }
    });

    const data = await res.json();
    listaMembros = data.membros || [];
    renderTabela(listaMembros);
  }

  function renderTabela(lista) {
    const tbody = document.querySelector("#tabelaMembros tbody");
    if (!tbody) return;

    tbody.innerHTML = "";

    lista.forEach(m => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><input type="checkbox" data-id="${m.id}"></td>
        <td>${m.nome}</td>
        <td>${m.telefone ?? "-"}</td>
        <td>${m.estado_civil ?? "-"}</td>
        <td>${m.cidade ?? "-"}</td>
      `;
      tbody.appendChild(tr);
    });

    tbody.querySelectorAll("input[type=checkbox]").forEach(cb => {
      cb.addEventListener("change", () => {
        cb.checked ? selecionados.add(cb.dataset.id) : selecionados.delete(cb.dataset.id);
        atualizarBotaoEnvio();
      });
    });
  }

  function atualizarBotaoEnvio() {
    const btn = document.getElementById("btnEnviarMensagem");
    if (!btn) return;

    btn.disabled = selecionados.size === 0;
    btn.textContent = selecionados.size
      ? `✉️ Enviar mensagem (${selecionados.size})`
      : "✉️ Enviar mensagem";
  }

  // ======================================================
  // TABS
  // ======================================================
  function setupTabs() {
    document.querySelectorAll(".tab-button").forEach(btn => {
      btn.addEventListener("click", async () => {
        document.querySelectorAll(".tab-button").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

        btn.classList.add("active");
        const target = document.getElementById(btn.dataset.tab);
        if (target) target.classList.add("active");

        if (btn.dataset.tab === "tab-geral") await carregarGeral();
        if (btn.dataset.tab === "tab-membros") await carregarMembros();
      });
    });
  }

  // ======================================================
  // INIT
  // ======================================================
  document.addEventListener("DOMContentLoaded", async () => {
    if (!token) {
      window.location = "/app/login";
      return;
    }

    setupTabs();
    await carregarGeral();

    document.getElementById("btnAbrirListaMembros")?.addEventListener("click", async () => {
      const painel = document.getElementById("painelListaMembros");
      painel.style.display = painel.style.display === "none" ? "block" : "none";
      if (painel.style.display === "block") await carregarListaMembros();
    });

    document.getElementById("buscaMembro")?.addEventListener("input", e => {
      carregarListaMembros(e.target.value);
    });
  });
})();
