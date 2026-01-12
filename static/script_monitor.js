// ===============================
// script_monitor.js — CRM Church
// Monitor de Conversas (Integra+)
// ===============================

// Helper para normalizar ID vindo da URL ou do select
function normalizarVisitanteId(value) {
  if (!value) return "";
  const s = String(value).trim();
  // Corrige formatos tipo "id:1"
  if (s.toLowerCase().startsWith("id:")) {
    const partes = s.split(":");
    return partes[1] ? partes[1].trim() : "";
  }
  return s;
}

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

    // Preenche select (nome visível, telefone no dataset)
    data.visitantes.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = String(v.id);
      opt.textContent = v.nome || "Sem nome";
      opt.dataset.telefone = v.telefone || "";
      select.appendChild(opt);
    });

    // Verifica se há ?visitante= na URL (ex: /app/monitor?visitante=id:1 ou ?visitante=1)
    const urlParams = new URLSearchParams(window.location.search);
    const visitanteBruto = urlParams.get("visitante");
    const visitanteId = normalizarVisitanteId(visitanteBruto);

    if (visitanteId && select.options.length > 0) {
      const exists = Array.from(select.options).some(
        (opt) => opt.value === visitanteId
      );

      if (exists) {
        select.value = visitanteId;
        area.innerHTML = `
          <p style="text-align:center; color:#000;">
            🔍 Carregando conversa do visitante #${visitanteId}...
          </p>
        `;
        await carregarConversas();
      } else {
        area.innerHTML =
          "<p style='text-align:center; color:#888;'>Visitante não encontrado na lista atual.</p>";
      }
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
  const visitanteIdRaw = visitanteSelect.value;
  const visitanteId = normalizarVisitanteId(visitanteIdRaw);

  const visitanteNome =
    visitanteSelect.options[visitanteSelect.selectedIndex]?.text ||
    "Visitante";

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

    if (!res.ok) {
      console.error(
        `Erro HTTP ao buscar conversas: ${res.status} ${res.statusText}`
      );
      area.innerHTML = `
        <p style="text-align:center; color:#c00;">
          Erro ao buscar conversas (HTTP ${res.status}).
        </p>
      `;
      return;
    }

    const data = await res.json();
    area.innerHTML = "";

    if (data.status === "success" && data.conversas?.length > 0) {
      data.conversas.forEach((c) => {
        const msg = document.createElement("div");
        msg.classList.add("msg", c.tipo === "enviada" ? "bot" : "user");
        msg.innerHTML = `
          <p>${c.mensagem}</p>
          <small>${c.autor} • ${new Date(c.data_hora).toLocaleString("pt-BR")}</small>
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
  const visitanteId = normalizarVisitanteId(visitanteSelect.value);

  const optionSel = visitanteSelect.options[visitanteSelect.selectedIndex];
  const numero = optionSel?.dataset.telefone;

  const mensagem = document.getElementById("mensagemInput").value.trim();

  if (!visitanteId) return alert("Selecione um visitante antes de enviar.");
  if (!mensagem) return alert("Digite uma mensagem antes de enviar.");
  if (!numero) return alert("Número do visitante não encontrado.");

  try {
    const res = await fetch("/api/send-message-manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // ✅ agora envia visitante_id junto (obrigatório no backend novo)
      body: JSON.stringify({ visitante_id: visitanteId, numero, mensagem }),
    });

    const data = await res.json();

    if (data.success) {
      document.getElementById("mensagemInput").value = "";
      // Obs: como agora é fila, pode demorar alguns segundos até aparecer como "enviada"
      // (vai aparecer depois do callback on_success salvar no banco)
      carregarConversas();
    } else {
      alert("Erro ao enviar: " + (data.error || "Falha desconhecida"));
    }
  } catch (err) {
    alert("Falha na comunicação com o servidor.");
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
