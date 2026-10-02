// ===============================
// script_monitor.js — CRM Church
// Monitor detalhado de Conversas (Integra+)
// ===============================

let visitanteAtual = null;
let telefoneAtual = "";

function normalizarVisitanteId(value) {
  if (!value) return "";
  const s = String(value).trim();
  if (s.toLowerCase().startsWith("id:")) {
    const partes = s.split(":");
    return partes[1] ? partes[1].trim() : "";
  }
  return s;
}

function formatarDataHora(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString("pt-BR");
}

function formatarDia(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric"
  });
}

function chaveDiaLocal(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  const ano = d.getFullYear();
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${ano}-${mes}-${dia}`;
}

function escapeHtml(texto) {
  return String(texto ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

async function carregarResumo() {
  const lista = document.getElementById("conversationList");
  const dataFiltro = document.getElementById("dataFiltro")?.value || "";
  const busca = document.getElementById("buscaFiltro")?.value.trim() || "";

  lista.innerHTML = '<div class="empty">⏳ Carregando conversas...</div>';

  const params = new URLSearchParams();
  if (dataFiltro) params.set("date", dataFiltro);
  if (busca) params.set("q", busca);

  try {
    const res = await fetch(`/api/monitor/resumo?${params.toString()}`);
    const data = await res.json();

    if (!res.ok || data.status !== "success") {
      lista.innerHTML = '<div class="empty">Erro ao carregar o resumo das conversas.</div>';
      return;
    }

    const conversas = Array.isArray(data.conversas) ? data.conversas : [];
    renderizarResumo(conversas, dataFiltro);
  } catch (err) {
    console.error("Erro ao carregar resumo:", err);
    lista.innerHTML = '<div class="empty">Erro ao carregar o resumo das conversas.</div>';
  }
}

function renderizarResumo(conversas, dataFiltro) {
  const lista = document.getElementById("conversationList");
  const periodo = document.getElementById("resumoPeriodo");

  const totalMensagens = conversas.reduce((s, c) => s + Number(c.total_mensagens || 0), 0);
  const totalRecebidas = conversas.reduce((s, c) => s + Number(c.recebidas || 0), 0);
  const totalEnviadas = conversas.reduce((s, c) => s + Number(c.enviadas || 0), 0);

  document.getElementById("mConversas").textContent = conversas.length;
  document.getElementById("mMensagens").textContent = totalMensagens;
  document.getElementById("mRecebidas").textContent = totalRecebidas;
  document.getElementById("mEnviadas").textContent = totalEnviadas;

  periodo.textContent = dataFiltro
    ? new Date(`${dataFiltro}T12:00:00`).toLocaleDateString("pt-BR")
    : "Todas as datas";

  if (!conversas.length) {
    lista.innerHTML = '<div class="empty">Nenhuma conversa encontrada para os filtros informados.</div>';
    return;
  }

  lista.innerHTML = "";
  conversas.forEach((c) => {
    const item = document.createElement("div");
    item.className = "conversation-item";
    item.dataset.visitanteId = String(c.visitante_id);

    item.innerHTML = `
      <div class="conversation-title">
        <span>${escapeHtml(c.visitante_nome || "Sem nome")}</span>
        <span class="badge">${Number(c.total_mensagens || 0)} msg</span>
      </div>
      <div class="conversation-meta">
        ${escapeHtml(c.telefone || "Sem telefone")} • ${formatarDataHora(c.ultima_mensagem)}
      </div>
      <div class="conversation-preview">
        ${escapeHtml(c.ultima_mensagem_texto || "Sem prévia")}
      </div>
    `;

    item.addEventListener("click", () => {
      document.querySelectorAll(".conversation-item").forEach(el => el.classList.remove("active"));
      item.classList.add("active");
      carregarConversas(c.visitante_id, c.visitante_nome, c.telefone);
    });

    lista.appendChild(item);
  });

  const urlParams = new URLSearchParams(window.location.search);
  const visitanteIdUrl = normalizarVisitanteId(urlParams.get("visitante"));
  if (visitanteIdUrl) {
    const alvo = Array.from(document.querySelectorAll(".conversation-item"))
      .find(el => el.dataset.visitanteId === visitanteIdUrl);
    if (alvo) alvo.click();
  }
}

async function carregarConversas(visitanteId, visitanteNome = "Visitante", telefone = "") {
  visitanteAtual = normalizarVisitanteId(visitanteId);
  telefoneAtual = telefone || "";

  const area = document.getElementById("chatArea");
  const title = document.getElementById("chatTitle");
  const subtitle = document.getElementById("chatSubtitle");

  title.textContent = `💬 ${visitanteNome || "Visitante"}`;
  subtitle.textContent = telefone || "";
  area.innerHTML = '<div class="empty">⏳ Buscando histórico completo...</div>';

  try {
    const res = await fetch(`/api/monitor/conversas/${visitanteAtual}`);
    const data = await res.json();

    if (!res.ok || data.status !== "success") {
      area.innerHTML = '<div class="empty">Erro ao buscar as mensagens deste visitante.</div>';
      return;
    }

    const conversas = Array.isArray(data.conversas) ? data.conversas : [];
    area.innerHTML = "";

    if (!conversas.length) {
      area.innerHTML = '<div class="empty">Nenhuma mensagem encontrada.</div>';
      return;
    }

    let ultimoDia = "";
    conversas.forEach((c) => {
      const chaveDia = chaveDiaLocal(c.data_hora);

      if (chaveDia !== ultimoDia) {
        const sep = document.createElement("div");
        sep.className = "day-separator";
        sep.innerHTML = `<span>${escapeHtml(formatarDia(c.data_hora))}</span>`;
        area.appendChild(sep);
        ultimoDia = chaveDia;
      }

      const msg = document.createElement("div");
      msg.classList.add("msg", String(c.tipo).toLowerCase() === "enviada" ? "bot" : "user");
      msg.innerHTML = `
        <div>${escapeHtml(c.mensagem).replace(/\n/g, "<br>")}</div>
        <small>${escapeHtml(c.autor || "")} • ${formatarDataHora(c.data_hora)}</small>
      `;
      area.appendChild(msg);
    });

    area.scrollTo({ top: area.scrollHeight, behavior: "smooth" });
  } catch (err) {
    console.error("Erro ao carregar conversas:", err);
    area.innerHTML = '<div class="empty">Erro ao carregar as mensagens.</div>';
  }
}

async function enviarMensagemManual(e) {
  e.preventDefault();

  const mensagem = document.getElementById("mensagemInput").value.trim();
  if (!visitanteAtual) return alert("Selecione uma conversa antes de enviar.");
  if (!mensagem) return alert("Digite uma mensagem antes de enviar.");
  if (!telefoneAtual) return alert("Número do visitante não encontrado.");

  try {
    const res = await fetch("/api/send-message-manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        visitante_id: visitanteAtual,
        numero: telefoneAtual,
        mensagem
      })
    });

    const data = await res.json();
    if (data.success) {
      document.getElementById("mensagemInput").value = "";
      setTimeout(async () => {
        await carregarConversas(visitanteAtual, document.getElementById("chatTitle").textContent.replace("💬 ", ""), telefoneAtual);
        carregarResumo();
      }, 1500);
    } else {
      alert("Erro ao enviar: " + (data.error || "Falha desconhecida"));
    }
  } catch (err) {
    console.error(err);
    alert("Falha na comunicação com o servidor.");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btnFiltrar")?.addEventListener("click", carregarResumo);
  document.getElementById("btnReload")?.addEventListener("click", carregarResumo);
  document.getElementById("buscaFiltro")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") carregarResumo();
  });
  carregarResumo();
});
