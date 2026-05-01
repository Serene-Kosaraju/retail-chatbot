const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("composer");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");

const history = [];

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Linkify bare http(s) URLs.
function linkify(text) {
  const escaped = escapeHtml(text);
  return escaped.replace(
    /(https?:\/\/[^\s<]+)/g,
    '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
  );
}

function addMessage(role, content, { paymentUrl } = {}) {
  const div = document.createElement("div");
  div.className = `msg msg--${role}`;
  div.innerHTML = linkify(content || "");
  if (paymentUrl) {
    const a = document.createElement("a");
    a.href = paymentUrl;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.className = "pay-btn";
    a.textContent = "Pay securely with Stripe →";
    div.appendChild(document.createElement("br"));
    div.appendChild(a);
  }
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function addTyping() {
  const div = document.createElement("div");
  div.className = "msg msg--bot";
  div.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

async function sendMessage(text) {
  history.push({ role: "user", content: text });
  addMessage("user", text);

  const typingEl = addTyping();
  sendBtn.disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });
    const data = await res.json();
    typingEl.remove();

    if (!res.ok) {
      addMessage("sys", data.detail || "Something went wrong.");
      return;
    }

    const reply = data.reply || "";
    history.push({ role: "assistant", content: reply });
    addMessage("bot", reply, { paymentUrl: data.payment_url });
  } catch (err) {
    typingEl.remove();
    addMessage("sys", "Network error. Please try again.");
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = "";
  sendMessage(text);
});

// URL flags from Stripe redirect
const params = new URLSearchParams(location.search);
if (params.get("paid") === "1") {
  addMessage("sys", "Payment received. Your order is confirmed — check your email for the receipt.");
  history.length && history.push({
    role: "user",
    content: "(System: my payment just succeeded.)",
  });
} else if (params.get("canceled") === "1") {
  addMessage("sys", "Payment canceled. You can pick another product or try again any time.");
}

// Greeting
addMessage(
  "bot",
  "Hi! I'm your brand assistant. Ask me about shipping, returns, sizing — or tell me what you'd like to order and I'll set up a secure checkout for you."
);
