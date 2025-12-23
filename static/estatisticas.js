(function () {
  const token = localStorage.getItem("jwt_token");

  // 🔧 API BASE (Render / Flask)
  const API_BASE = "/api";
  const API = `${API_BASE}/estatisticas`;

  let charts = {};

  // ================================
  // UTILITÁRIOS
  // ================================
  function safeArray(value) {
    return Array.isArray(value) ? value : [];
  }

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

    console.log("📊 Estatísticas Geral:", geral);

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
      safeArray(geral.mensal).map(x => x.mes),
      safeArray(geral.mensal).map(x => x.total)
    );

    renderChart(
      "graficoOrigem",
      "pie",
      safeArray(geral.origem).map(o => o.origem),
      safeArray(geral.origem).map(o => o.total)
    );

    renderChart(
      "graficoFases",
      "bar",
      safeArray(geral.fases).map(f => f.fase),
      safeArray(geral.fases).map(f => f.total)
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
      safeArray(geral.demografia?.estado_civil).map(x => x.estado_civil),
      safeArray(geral.demografia?.estado_civil).map(x => x.total)
    );

    renderChart(
      "graficoCidades",
      "bar",
      safeArray(geral.demografia?.cidades).map(x => x.cidade),
      safeArray(geral.demografia?.cidades).map(x => x.total)
    );
  }

  // ================================
  // ABA: KIDS
  // ================================
  async function carregarKids() {
    const kids = await fetchJSON(`${API}/kids`);

    console.log("🧒 Estatísticas Kids:", kids);

    setText("kidsTotal", kids.totais?.total_checkins ?? 0);
    setText("kidsAlertas", kids.totais?.alertas_enviados ?? 0);
    setText("kidsPaiVeio", kids.totais?.pai_veio ?? 0);

    renderChart(
      "graficoKidsTurma",
      "bar",
      safeArray(kids.turmas).map(t => t.turma),
      safeArray(kids.turmas).map(t => t.total_checkins)
    );
  }

  // ================================
  // ABA: FAMÍLIAS
  // ================================
  async function carregarFamilias() {
    const familias = await fetchJSON(`${API}/familias`);

    console.log("🏠 Estatísticas Famílias:", familias);

    setText("familiasAtivas", familias.totais?.familias_ativas ?? 0);
    setText("cestasEntregues", familias.totais?.total_cestas ?? 0);
    setText("necessidadesEspecificas", familias.totais?.necessidades ?? 0);

    renderChart(
      "graficoKidsFamilias",
      "line",
      safeArray(familias.visitas).map(v => v.data),
      safeArray(familias.visitas).map(v => v.total)
    );
  }

  // ================================
  // ABA: ALERTAS
  // ================================
  async function carregarAlertas() {
    const data = await fetchJSON(`${API}/alertas`);
    const container = document.getElementById("alertasContainer");

    console.log("⚠️ Alertas Pastorais:", data);

    container.innerHTML = "";

    safeArray(data.alertas).forEach(a => {
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
        document.getElementById(btn.dataset.tab).classList.add("active");

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
