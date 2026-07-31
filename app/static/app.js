// Chat intake for The Draft Desk.
const log = document.getElementById("log");
const opts = document.getElementById("opts");
const input = document.getElementById("input");
const send = document.getElementById("send");

let finished = false;
let pendingSubmission = null;

function bubble(text, who) {
  const el = document.createElement("div");
  el.className = `bubble ${who}`;
  el.textContent = text;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
}

function renderOptions(list) {
  opts.innerHTML = "";
  (list || []).forEach((label) => {
    const b = document.createElement("button");
    b.className = "opt";
    b.textContent = label;
    b.onclick = () => submitAnswer(label);
    opts.appendChild(b);
  });
}

async function start() {
  const res = await fetch("/api/agent/start", { method: "POST" });
  const data = await res.json();
  bubble(data.message, "bot");
  renderOptions(data.options);
}

async function submitAnswer(text) {
  if (finished || !text.trim()) return;
  bubble(text, "me");
  input.value = "";
  opts.innerHTML = "";

  const res = await fetch("/api/agent/message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text }),
  });
  const data = await res.json();
  bubble(data.message, "bot");
  renderOptions(data.options);

  if (data.done && data.submission) {
    pendingSubmission = data.submission;
    finished = true;
    await fileSubmission();
  }
}

async function fileSubmission() {
  const res = await fetch("/api/submissions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(pendingSubmission),
  });
  const note = document.createElement("div");
  note.className = "done-note";
  if (res.ok) {
    note.textContent = "✓ Filed as Pending. Track your rank on the Draft Board.";
  } else {
    note.textContent = "Something went wrong filing this. Try again.";
  }
  log.appendChild(note);
  log.scrollTop = log.scrollHeight;
  input.disabled = true;
  send.disabled = true;
}

send.onclick = () => submitAnswer(input.value);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") submitAnswer(input.value);
});

start();
