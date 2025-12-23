(function () {
  const token = localStorage.getItem("jwt_token");

  // 🔧 PREFIXO CORRETO PARA RENDER / FLASK
  const API_BASE = "/api";
  const API = `${API_BASE}/estatisticas`;

  let charts = {};

  // ================================
  // GENÉRICOS
  // ================================
  async function fetchJSON(url) {
    const res = await fetch(url, {
      headers: {
        "Authorization": `Bearer ${token}`
      }
    });

    if (!res.ok) {
      throw new Error(`Erro ao acessar ${url}`);
    }
    return res.json();
  }

  function setText(id, text) {
    const el = document.querySelector(`#${id} p`);
    if (el) el.textContent = text ?? "—";
  }

  function renderChart(id, type, labels, data, colors) {
    const ctx = document.getElementById(id);
    if (!ctx) return;

    if (charts[id]) charts[id].destroy();

    charts[id] = new Chart(ctx, {
      type,
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: colors || [
            "#004f90",
            "#FF6B6B",
            "#2ECC40",
            "#FFCC00",
            "#7FDBFF",
            "#B10DC9",
            "#AAAAAA"
          ],
          borderWidth: 1
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
  // ABA: GERAL
  // ================================
  async function carregarGeral() {
    const periodo = document.getElementById("periodoSelect").value;
    const geral = await fetchJSON(`${API}/geral?meses=${periodo}`);

    // KPIs
    setText("totalVisitantesInicio", geral.inicio?.total);
    setText("discipuladosAtivos", geral.discipulado?.total_discipulado);
    setText("totalPedidosOracao", geral.oracao?.total_pedidos);

    setText("totalHomens", geral.genero?.homens);
    setText("totalMulheres", geral.genero?.mulheres);

    setText(
      "conversasEnviadasRecebidas",
      `Enviadas: ${geral.conversas?.enviadas ?? 0} | Recebidas: ${geral.conversas?.recebidas ?? 0}`
    );

    // Gráficos
    renderChart(
      "graficoMensal",
      "line",
      geral.mensal.map(x => x.mes),
      geral.mensal.map(x => x.total)
    );

    renderChart(
      "graficoOrigem",
      "pie",
      geral.origem.map(o => o.origem),
      geral.origem.map(o => o.total)
    );

    renderChart(
      "graficoFases",
      "bar",
      geral.fases.map(f => f.fase),
      geral.fases.map(f => f.total)
    );

    // Demografia
    const idade = geral.demografia?.idade || {};
    setText(
      "idadeMedia",
      `${idade.idade_media ?? "—"} anos | Jovens: ${idade.jovens ?? 0} | Adultos: ${idade.adultos ?? 0} | Idosos: ${idade.idosos ?? 0}`
    );

    renderChart(
      "graficoEstadoCivil",
      "pie",
      geral.demografia.estado_civil.map(x => x.estado_civil),
      geral.demografia.estado_civil.map(x => x.total)
    );

    renderChart(
      "graficoCidades",
      "bar",
      geral.demografia.cidades.map(x => x.cidade),
      geral.demografia.cidades.map(x => x.total)
    );
  }

  // ================================
  // ABA: KIDS
  // ================================
  async function carregarKids() {
    const kids = await fetchJSON(`${API}/kids`);

    setText("kidsTotal", kids.totais?.total_checkins ?? 0);
    setText("kidsAlertas", kids.totais?.alertas_enviados ?? 0);
    setText("kidsPaiVeio", kids.totais?.pai_veio ?? 0);

    renderChart(
      "graficoKidsTurma",
      "bar",
      kids.turmas.map(t => t.turma),
      kids.turmas.map(t => t.total_checkins)
    );
  }

  // ================================
  // ABA: FAMÍLIAS
  // ================================
  async function carregarFamilias() {
    const familias = await fetchJSON(`${API}/familias`);

    setText("familiasAtivas", familias.totais?.familias_ativas ?? 0);
    setText("cestasEntregues", familias.totais?.total_cestas ?? 0);
    setText("necessidadesEspecificas", familias.totais?.necessidades ?? 0);

    renderChart(
      "graficoKidsFamilias",
      "line",
      familias.visitas.map(v => v.data),
      familias.visitas.map(v => v.total)
    );
  }

  // ================================
  // ABA: ALERTAS
  // ================================
  async function carregarAlertas() {
    const data = await fetchJSON(`${API}/alertas`);
    const container = document.getElementById("alertasContainer");

    container.innerHTML = "";

    data.alertas.forEach(a => {
      const card = document.createElement("div");
      card.className = "info-card";
      card.style.borderLeft = `6px solid ${cor(a.cor)}`;
      card.innerHTML = `
        <h3>${a.tipo}</h3>
        <p>${a.mensagem}</p>
      `;
      container.appendChild(card);
    });
  }

  function cor(c) {
    return {
      vermelho: "#FF3B3B",
      amarelo: "#FFCC00",
      verde: "#2ECC40",
      laranja: "#FF851B"
    }[c] || "#004f90";
  }

  // ================================
  // TROCA DE ABAS
  // ================================
  function setupTabs() {
    const buttons = document.querySelectorAll(".tab-button");
    const sections = document.querySelectorAll(".tab-content");

    buttons.forEach(btn => {
      btn.addEventListener("click", () => {
        buttons.forEach(b => b.classList.remove("active"));
        sections.forEach(sec => sec.classList.remove("active"));

        btn.classList.add("active");
        const tab = document.getElementById(btn.dataset.tab);
        tab.classList.add("active");

        if (btn.dataset.tab === "tab-geral") carregarGeral();
        if (btn.dataset.tab === "tab-kids") carregarKids();
        if (btn.dataset.tab === "tab-familias") carregarFamilias();
        if (btn.dataset.tab === "tab-alertas") carregarAlertas();
      });
    });
  }

  // ================================
  // INICIALIZAÇÃO
  // ================================
  document.addEventListener("DOMContentLoaded", () => {
    if (!token) {
      window.location = "/app/login";
      return;
    }

    setupTabs();
    carregarGeral();

    const sel = document.getElementById("periodoSelect");
    sel.addEventListener("change", carregarGeral);
  });
})();
