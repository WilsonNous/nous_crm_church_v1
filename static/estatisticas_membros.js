(() => {
  const token = localStorage.getItem("jwt_token");
  const API_MEMBROS = "/api/membros";

  let listaMembros = [];
  let selecionados = new Set();

  // ===============================
  // UTILITÁRIOS
  // ===============================
  function setText(id, value) {
    const el = document.querySelector(`#${id} p`);
    if (el) el.textContent = value ?? "—";
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

  // ===============================
  // 📊 KPIs DE MEMBROS
  // ===============================
  async function carregarKPIsMembros() {
    const data = await fetchJSON(API_MEMBROS);

    const membros = data.membros || [];

    setText("membrosTotal", membros.length);

    const homens = membros.filter(m => m.genero === "Masculino").length;
    const mulheres = membros.filter(m => m.genero === "Feminino").length;

    setText("membrosHomens", homens);
    setText("membrosMulheres", mulheres);
  }

  // ===============================
  // 📋 LISTA DE MEMBROS
  // ===============================
  async function carregarListaMembros(termo = "") {
    const url = termo
      ? `${API_MEMBROS}?q=${encodeURIComponent(termo)}`
      : API_MEMBROS;

    const data = await fetchJSON(url);

    listaMembros = data.membros || [];
    renderTabela(listaMembros);
  }

  function renderTabela(lista) {
    const tbody = document.querySelector("#tabelaMembros tbody");
    if (!tbody) return;

    tbody.innerHTML = "";
    selecionados.clear();
    atualizarBotaoEnvio();

    lista.forEach(m => {
      const tr = document.createElement("tr");

      tr.innerHTML = `
        <td>
          <input type="checkbox" data-id="${m.id}">
        </td>
        <td>${m.nome || "-"}</td>
        <td>${m.telefone || "-"}</td>
        <td>${m.estado_civil || "-"}</td>
        <td>${m.cidade || "-"}</td>
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

  // ===============================
  // EVENTOS
  // ===============================
  function setupEventos() {
    const btnAbrir = document.getElementById("btnAbrirListaMembros");
    const painel = document.getElementById("painelListaMembros");
    const busca = document.getElementById("buscaMembro");
    const btnTodos = document.getElementById("btnSelecionarTodos");
    const btnEnviar = document.getElementById("btnEnviarMensagem");

    // Abrir / fechar painel
    btnAbrir?.addEventListener("click", async () => {
      const aberto = painel.style.display === "block";
      painel.style.display = aberto ? "none" : "block";

      if (!aberto && listaMembros.length === 0) {
        await carregarListaMembros();
      }
    });

    // Busca
    busca?.addEventListener("input", async () => {
      const termo = busca.value.trim();
      await carregarListaMembros(termo);
    });

    // Selecionar todos
    btnTodos?.addEventListener("click", () => {
      document
        .querySelectorAll("#tabelaMembros input[type=checkbox]")
        .forEach(cb => {
          cb.checked = true;
          selecionados.add(cb.dataset.id);
        });

      atualizarBotaoEnvio();
    });

    // Enviar mensagem (placeholder)
    btnEnviar?.addEventListener("click", () => {
      alert(`Enviar mensagem para ${selecionados.size} membros`);
      // 🔜 Integração WhatsApp / Integra+
    });
  }

  // ===============================
  // INIT
  // ===============================
  document.addEventListener("DOMContentLoaded", async () => {
    if (!token) {
      window.location = "/app/login";
      return;
    }

    await carregarKPIsMembros();
    setupEventos();
  });
})();
