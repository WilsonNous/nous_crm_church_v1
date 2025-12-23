(function () {
  const token = localStorage.getItem("jwt_token");

  const API_BASE = "/api";
  const API = `${API_BASE}/estatisticas`;
  const API_MEMBROS = `${API_BASE}/membros`; // futuro endpoint real

  let charts = {};
  let cacheEstatisticas = null;
  let listaMembros = [];
  let selecionados = new Set();

  // ================================
  // UTILITÁRIOS
  // ================================
  function safeArray(v) {
    return Array.isArray(v) ? v : [];
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

  async function fetchEstatisticas() {
    if (cacheEstatisticas) return cacheEstatisticas;

    const res = await fetch(`${API}/geral`, {
      headers: { Authorization: `Bearer ${token}` }
    });

    cacheEstatisticas = await res.json();
    return cacheEstatisticas;
  }

  // ================================
  // ABA: MEMBROS (KPIs)
  // ================================
  async function carregarMembros() {
    const data = await fetchEstatisticas();
    const m = data.membros || {};

    setText("membrosTotal", m.total?.total);
    setText("membrosHomens", m.genero?.homens);
    setText("membrosMulheres", m.genero?.mulheres);
  }

  // ================================
  // 📋 LISTA DE MEMBROS
  // ================================
  async function carregarListaMembros() {
    // 🔹 MOCK TEMPORÁRIO (até ligar no backend)
    listaMembros = [
      { id: 1, nome: "João Silva", telefone: "48999990001", estado_civil: "Casado", cidade: "Florianópolis" },
      { id: 2, nome: "Maria Souza", telefone: "48999990002", estado_civil: "Solteira", cidade: "São José" },
      { id: 3, nome: "Carlos Lima", telefone: "48999990003", estado_civil: "Casado", cidade: "Palhoça" }
    ];

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
        <td>${m.telefone}</td>
        <td>${m.estado_civil}</td>
        <td>${m.cidade}</td>
      `;

      tbody.appendChild(tr);
    });

    tbody.querySelectorAll("input[type=checkbox]").forEach(cb => {
      cb.addEventListener("change", () => {
        const id = cb.dataset.id;
        cb.checked ? selecionados.add(id) : selecionados.delete(id);
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

  // ================================
  // EVENTOS LISTA
  // ================================
  function setupListaMembros() {
    const btnAbrir = document.getElementById("btnAbrirListaMembros");
    const painel = document.getElementById("painelListaMembros");
    const busca = document.getElementById("buscaMembro");
    const btnTodos = document.getElementById("btnSelecionarTodos");

    if (!btnAbrir || !painel) return;

    btnAbrir.addEventListener("click", async () => {
      painel.style.display = painel.style.display === "none" ? "block" : "none";

      if (painel.style.display === "block" && listaMembros.length === 0) {
        await carregarListaMembros();
      }
    });

    busca?.addEventListener("input", () => {
      const termo = busca.value.toLowerCase();
      const filtrados = listaMembros.filter(m =>
        m.nome.toLowerCase().includes(termo) ||
        m.telefone.includes(termo)
      );
      renderTabela(filtrados);
    });

    btnTodos?.addEventListener("click", () => {
      document
        .querySelectorAll("#tabelaMembros input[type=checkbox]")
        .forEach(cb => {
          cb.checked = true;
          selecionados.add(cb.dataset.id);
        });
      atualizarBotaoEnvio();
    });

    document.getElementById("btnEnviarMensagem")?.addEventListener("click", () => {
      alert(`Enviar mensagem para ${selecionados.size} membros`);
      // aqui entra WhatsApp / Integra+
    });
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
        const target = document.getElementById(btn.dataset.tab);
        if (target) target.classList.add("active");

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
    setupListaMembros();
    await carregarMembros();
  });
})();
