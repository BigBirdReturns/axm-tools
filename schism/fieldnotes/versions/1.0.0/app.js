"use strict";
const $ = (id) => document.getElementById(id);
const incoming = new URLSearchParams(location.hash.slice(1)).get("token");
if (incoming) { sessionStorage.setItem("fieldnotes-token", incoming); history.replaceState(null, "", location.pathname); }
const token = sessionStorage.getItem("fieldnotes-token");
let notes = [], current = null, dirty = false, pinning = false, saving = false;

async function request(path, value) {
  const headers = {Authorization: "Bearer " + token};
  const options = {headers, cache: "no-store"};
  if (value !== undefined) { headers["Content-Type"] = "application/json"; options.method = "POST"; options.body = JSON.stringify(value); }
  const response = await fetch(path, options);
  if (!response.ok) { const detail = await response.json(); throw new Error(detail.error || "The request failed."); }
  return response;
}
function say(text, error = false) { $("message").textContent = text; $("message").classList.toggle("error", error); }
function discarded() { if (saving) { say("Wait for this operation to finish before changing notes."); return false; } return !dirty || confirm("Leave this unsaved draft? Copy it or save first to keep your changes."); }
function changed() { dirty = true; $("state").textContent = "Unsaved changes"; say(""); }
function details() {
  $("state").textContent = dirty ? "Unsaved changes" : (current ? "Saved · revision " + current.revision : "New note");
  $("updated").textContent = current ? "Updated " + new Date(current.updated_at).toLocaleString() : "Saved as portable UTF-8 JSON";
  $("download").disabled = saving || !current; $("archive").disabled = saving || !current;
  $("archive").textContent = current?.archived ? "Restore note" : "Archive note";
  $("pin").hidden = !pinning; $("pin").disabled = saving || !current;
  $("pin").textContent = current?.pinned ? "Unpin note" : "Pin note";
}
function openNote(note) {
  current = note ? structuredClone(note) : null; dirty = false;
  $("title").value = note?.title || ""; $("tags").value = (note?.tags || []).join(", "); $("body").value = note?.body || "";
  details(); renderList(); say("");
}
function renderList() {
  const query = $("search").value.trim().toLocaleLowerCase();
  const shown = notes.filter((note) => ($("show-archived").checked || !note.archived) && [note.title, note.body, ...note.tags].join("\n").toLocaleLowerCase().includes(query));
  $("notes").replaceChildren(); $("count").textContent = shown.length + (shown.length === 1 ? " note" : " notes");
  if (!shown.length) { const empty = document.createElement("p"); empty.className = "empty"; empty.textContent = notes.length ? "No notes match this view." : "A place for work you want to keep. Write your first note, or import a text file."; $("notes").append(empty); }
  for (const note of shown) {
    const button = document.createElement("button"); button.className = "note-card" + (current?.id === note.id ? " selected" : ""); button.type = "button";
    const title = document.createElement("strong"); title.textContent = (pinning && note.pinned ? "◆ " : "") + note.title;
    const excerpt = document.createElement("span"); excerpt.className = "excerpt"; excerpt.textContent = note.body.replace(/\s+/g, " ").slice(0, 118) || "Empty note";
    const meta = document.createElement("span"); meta.className = "note-meta"; meta.textContent = (note.archived ? "Archived · " : "") + (note.tags.length ? note.tags.join(" · ") : new Date(note.updated_at).toLocaleDateString());
    button.append(title, excerpt, meta); button.addEventListener("click", () => { if (discarded()) { openNote(note); if (matchMedia("(max-width: 720px)").matches) $("title").scrollIntoView({behavior: "smooth", block: "center"}); } });
    $("notes").append(button);
  }
}
async function refresh() {
  const data = await (await request("/api/notebook")).json(); notes = data.notes; pinning = data.pinning;
  $("version").textContent = "v" + data.version; renderList(); details();
}
function setBusy(value) {
  saving = value;
  for (const id of ["save", "title", "tags", "body", "new", "import", "export", "import-file"]) $(id).disabled = value;
  details();
}
async function save(changes = {}) {
  if (saving) return;
  setBusy(true);
  try {
    const record = {id: current?.id || null, revision: current?.revision || 0, title: $("title").value, body: $("body").value,
      tags: $("tags").value.split(",").map((tag) => tag.trim()).filter(Boolean), archived: current?.archived || false, pinned: current?.pinned || false, ...changes};
    const data = await (await request("/api/notes", record)).json(); current = data.note; dirty = false;
    await refresh(); openNote(notes.find((note) => note.id === current.id)); say("Saved on this computer.");
  } catch (error) { say(error.message, true); } finally { setBusy(false); }
}
async function download(path, filename) {
  try { const response = await request(path); const url = URL.createObjectURL(await response.blob()); const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); say("Exported a copy. Your notebook is unchanged."); } catch (error) { say(error.message, true); }
}
$("new").addEventListener("click", () => { if (discarded()) { openNote(null); $("title").focus(); } });
$("save").addEventListener("click", () => save());
$("search").addEventListener("input", renderList); $("show-archived").addEventListener("change", renderList);
for (const id of ["title", "tags", "body"]) $(id).addEventListener("input", changed);
$("archive").addEventListener("click", () => save({archived: !current.archived}));
// Version 1.0 keeps the shared pinned field but has no pin action.
$("download").addEventListener("click", () => download("/api/text?id=" + current.id, "fieldnote-" + current.id + ".txt"));
$("export").addEventListener("click", () => download("/api/export", "fieldnotes-export.zip"));
$("import").addEventListener("click", () => { if (!saving) $("import-file").click(); });
$("import-file").addEventListener("change", async () => { const file = $("import-file").files[0]; $("import-file").value = ""; if (!file || !discarded()) return; if (file.size > 262144) { say("Import a text file of up to 256 KiB.", true); return; } setBusy(true); try { const raw = await file.arrayBuffer(); const body = new TextDecoder("utf-8", {fatal: true}).decode(raw); openNote(null); $("title").value = file.name.replace(/\.(txt|md)$/i, "").slice(0, 180); $("body").value = body; changed(); say("Imported as a draft. Save note to keep it."); } catch (_) { say("Use a UTF-8 text or Markdown file.", true); } finally { setBusy(false); } });
document.addEventListener("keydown", (event) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") { event.preventDefault(); save(); } });
window.addEventListener("beforeunload", (event) => { if (dirty) { event.preventDefault(); event.returnValue = ""; } });
async function start() {
  if (!token) { $("locked").hidden = false; return; }
  try { await refresh(); $("notebook").hidden = false; openNote(notes.find((note) => !note.archived) || null); }
  catch (_) { sessionStorage.removeItem("fieldnotes-token"); $("locked").hidden = false; }
}
start();
