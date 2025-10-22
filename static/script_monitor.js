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

    if (data.status !== "success") {
      select.innerHTML = "<option>Erro ao carregar visitantes</option>";
      area.innerHTML =
        "<p style='text-align:center; color:#c00;'>Erro ao carregar visitantes.</p>";
      return;
    }

    // ✅ Popula o select com nome + telefone
    data.visitantes.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = String(v.id); // força valor como string
      opt.textContent = `${v.nome} (${v.telefone})`;
      select.appendChild(opt);
    });

    // ✅ Verifica se há visitante na URL (/app/monitor?visitante=123)
    const urlParams = new URLSearchParams(window.location.search);
    const visitanteId = urlParams.get("visitante");

    if (visitanteId && select.options.length > 0) {
      // mostra mensagem temporária enquanto carrega a conversa
      area.innerHTML = `
        <p style="text-align:center; color:#1E4D8F;">
          🔍 Carregando conversa do visitante #${visitanteId}...
        </p>
      `;

      // tenta definir o visitante inicial
      const exists = Array.from(select.options).some(
        (opt) => opt.value == visitanteId // comparação flexível (string/number)
      );

      if (exists) {
        select.value = String(visitanteId);
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
  const visitanteId = visitanteSelect.value;
  const visitanteNome =
    visitanteSelect.options[visitanteSelect.selectedIndex]?.text || "";
  const area = document.getElementById("chatArea");
  const title = document.getElementById("chatTitle");

  if (!visitanteId) {
    title.textContent = "Monitor de Conversas do Integra+";
    area.innerHTML =
      '<p style="text-align:center; color:#888;">Selecione um visitante para visualizar as mensagens.</p>';
    return;
  }

  // Atualiza título e exibe mensagem de carregamento
  title.textContent = `💬 Conversas com ${visitanteNome.split("(")[0].trim()}`;
  area.innerHTML = `
    <p style="text-align:center; color:#1E4D8F;">
      ⏳ Buscando mensagens de ${visitanteNome.split("(")[0].trim()}...
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

      // rola suavemente até o final
      area.scrollTo({ top: area.scrollHeight, behavior: "smooth" });
    } else if (data.status === "error") {
      area.innerHTML = `<p style="text-align:center; color:#c00;">Erro: ${data.message}</p>`;
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
  const numeroMatch = visitanteSelect.options[
    visitanteSelect.selectedIndex
  ].text.match(/\((.*?)\)/);
  const numero = numeroMatch ? numeroMatch[1] : null;

  const mensagem = document.getElementById("mensagemInput").value.trim();
  if (!mensagem) return alert("Digite uma mensagem antes de enviar.");
  if (!numero) return alert("Telefone do visitante não encontrado.");

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
