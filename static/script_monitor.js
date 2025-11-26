// ===============================
// script_monitor.js — CRM Church
// Monitor de Conversas (Integra+)
// ===============================

// ========= CARREGAR VISITANTES =========
async function carregarVisitantes() {
  const area = document.getElementById("chatArea");
  const select = document.getElementById("visitanteSelect");

  area.innerHTML =
    '<p style="text-align:center; color:#888;">⏳ Carregando lista de visitantes...</p>';
  select.innerHTML = "";

  try {
    const res = await fetch("/api/monitor/visitantes");
    const data = await res.json();

    if (data.status !== "success" || !Array.isArray(data.visitantes)) {
      select.innerHTML = "<option>Erro ao carregar visitantes</option>";
      area.innerHTML =
        "<p style='text-align:center; color:#c00;'>Erro ao carregar visitantes.</p>";
      return;
    }

    // Preenche select (somente nome, telefone armazenado)
    data.visitantes.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = String(v.id);
      opt.textContent = v.nome || "Sem nome";
      opt.dataset.telefone = v.telefone || "Sem telefone";
      select.appendChild(opt);
    });

    // Se tiver visitante na URL ?visitante=ID
    const urlParams = new URLSearchParams(window.location.search);
    const visitanteId = urlParams.get("visitante");

    if (visitanteId && select.querySelector(`option[value="${visitanteId}"]`)) {
      select.value = String(visitanteId);
      await carregarConversas();
    } else {
      area.innerHTML =
        '<p style="text-align:center; color:#888;">Selecione um visitante para visualizar as mensagens.</p>';
    }
  } catch (err) {
    console.error("Erro ao carregar visitantes:", err);
    area.innerHTML =
      "<p style='text-align:center; color:#c00;'>Erro ao carregar visitantes.</p>";
  }
}

// ========= CARREGAR CONVERSAS =========
async function carregarConversas() {
  const visitanteSelect = document.getElementById("visitanteSelect");
  const visitanteId = visitanteSelect.value;
  const visitanteNome =
    visitanteSelect.options[visitanteSelect.selectedIndex]?.text || "Visitante";

  const area = document.getElementById("chatArea");
  const title = document.getElementById("chatTitle");

  if (!visitanteId) {
    title.textContent = "Monitor de Conversas do Integra+";
    area.innerHTML =
      '<p style="text-align:center; color:#888;">Selecione um visitante para visualizar as mensagens.</p>';
    return;
  }

  title.textContent = `💬 Conversas com ${visitanteNome}`;
  area.innerHTML = `
    <p style="text-align:center; color:#000;">
      ⏳ Buscando mensagens de ${visitanteNome}...
    </p>
  `;

  try {
    const res = await fetch(`/api/monitor/conversas/${visitanteId}`);
    const data = await res.json();

    area.innerHTML = "";

    if (data.status === "success" && data.conversas?.length > 0) {
      data.conversas.forEach((c) => {
        const msg = document.createElement("div");
        msg.classList.add("msg", c.tipo === "enviada" ? "bot" : "user");
        msg.innerHTML = `
          <p>${c.mensagem}</p>
          <small>${c.autor} • ${new Date(
          c.data_hora
        ).toLocaleString("pt-BR")}</small>
        `;
        area.appendChild(msg);
      });

      area.scrollTo({ top: area.scrollHeight, behavior: "smooth" });
    } else {
      area.innerHTML = `
        <p style="text-align:center; color:#888;">
          Nenhuma conversa encontrada para este visitante.
        </p>
      `;
    }
  } catch (err) {
    console.error("Erro ao carregar conversas:", err);
    area.innerHTML =
      "<p style='text-align:center; color:#c00;'>Erro ao carregar conversas.</p>";
  }
}

// ========= ENVIAR MENSAGEM =========
async function enviarMensagemManual(e) {
  e.preventDefault();

  const visitanteSelect = document.getElementById("visitanteSelect");
  const numero = visitanteSelect.options[visitanteSelect.selectedIndex]?.dataset
    .telefone;

  const mensagem = document.getElementById("mensagemInput").value.trim();

  if (!mensagem) return alert("Digite uma mensagem antes de enviar.");
  if (!numero) return alert("Número do visitante não encontrado.");

  try {
    const res = await fetch("/api/send-message-manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ numero, mensagem }),
    });

    const data = await res.json();

    if (data.success) {
      document.getElementById("mensagemInput").value = "";
      carregarConversas();
    } else {
      alert("Erro ao enviar: " + data.error);
    }
  } catch (err) {
    alert("Erro de comunicação com o servidor.");
    console.error(err);
  }
}

// ========= INICIALIZAÇÃO =========
document.addEventListener("DOMContentLoaded", () => {
  carregarVisitantes();
  document
    .getElementById("btnReload")
    ?.addEventListener("click", carregarConversas);
});
