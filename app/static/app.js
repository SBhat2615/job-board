const state = {
  vocab: null,
  profile: null,
  companies: [],
  rules: [],
  status: "feed",
  defaultsApplied: false,
  discardId: null,
};

const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  let body = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { detail: text };
    }
  }
  if (!response.ok) {
    const detail = body && body.detail;
    throw new Error(typeof detail === "string" ? detail : "Request failed.");
  }
  return body;
}

function showBanner(message, isError = false) {
  const banner = $("banner");
  banner.hidden = !message;
  banner.textContent = message || "";
  banner.classList.toggle("error", Boolean(isError));
}

function label(group, value) {
  if (!value || value === "unknown") return "";
  return state.vocab.labels[group]?.[value] || value;
}

function fillSelect(select, values, labels, anyLabel) {
  const current = select.value;
  select.replaceChildren();
  if (anyLabel != null) select.append(el("option", { value: "" }, anyLabel));
  for (const value of values) {
    select.append(el("option", { value }, labels?.[value] || value));
  }
  if ([...select.options].some((option) => option.value === current)) select.value = current;
}

function fillVocab() {
  const { vocab } = state;
  fillSelect($("source"), vocab.sources, vocab.labels.source, "All platforms");
  fillSelect($("work_mode"), vocab.work_modes, vocab.labels.work_mode, "Any");
  fillSelect($("seniority"), vocab.seniority, vocab.labels.seniority, "Any");
  fillSelect($("employment"), vocab.employment, vocab.labels.employment, "Any");
  fillSelect($("team_size"), vocab.team_sizes, vocab.labels.team_size, "Any team size");
  fillSelect($("work_auth"), vocab.work_auth, vocab.labels.work_auth, "Any");
  fillSelect($("posted_within"), vocab.posted_within, vocab.labels.posted_within, "Any time");
  fillSelect($("salary_currency"), vocab.currencies, null, null);
  fillSelect($("profile-currency"), vocab.currencies, null, null);
  fillSelect($("company-type"), ["greenhouse", "lever", "ashby"], vocab.labels.source, null);
  fillSelect($("discard-reason"), vocab.discard_reasons, vocab.labels.discard_reason, null);

  const pref = (select, values, labels) => {
    select.replaceChildren(el("option", { value: "any" }, "Any"));
    for (const value of values) {
      if (value === "unknown") continue;
      select.append(el("option", { value }, labels[value] || value));
    }
  };
  pref($("profile-work-mode"), vocab.work_modes, vocab.labels.work_mode);
  pref($("profile-seniority"), vocab.seniority, vocab.labels.seniority);
  fillRoleLocation();
}

function fillRoleLocation() {
  const profile = state.profile || { roles: [], locations: [] };
  const role = $("role");
  const roleValue = role.value;
  role.replaceChildren(el("option", { value: "" }, "All roles"));
  for (const item of profile.roles || []) role.append(el("option", { value: item }, item));
  if ([...role.options].some((option) => option.value === roleValue)) role.value = roleValue;

  const location = $("location");
  const locationValue = location.value;
  location.replaceChildren(el("option", { value: "" }, "Any location"));
  if ((profile.locations || []).length) {
    location.append(el("option", { value: "__preferred__" }, "Preferred locations"));
  }
  for (const item of profile.locations || []) location.append(el("option", { value: item }, item));
  if ([...location.options].some((option) => option.value === locationValue)) {
    location.value = locationValue;
  }
}

function applyDefaults() {
  const profile = state.profile;
  if (!profile || state.defaultsApplied) return;
  $("work_mode").value = profile.work_mode && profile.work_mode !== "any" ? profile.work_mode : "";
  $("seniority").value = profile.seniority && profile.seniority !== "any" ? profile.seniority : "";
  $("salary_min").value = profile.salary_min ?? "";
  $("salary_currency").value = profile.salary_currency || "USD";
  $("hide_unknown_salary").checked = Boolean(profile.hide_unknown_salary);
  if ((profile.locations || []).length) $("location").value = "__preferred__";
  state.defaultsApplied = true;
  fillProfileForm();
}

function fillProfileForm() {
  const profile = state.profile;
  if (!profile) return;
  $("profile-roles").value = (profile.roles || []).join(", ");
  $("profile-locations").value = (profile.locations || []).join(", ");
  $("profile-work-mode").value = profile.work_mode || "any";
  $("profile-seniority").value = profile.seniority || "any";
  $("profile-salary").value = profile.salary_min ?? "";
  $("profile-currency").value = profile.salary_currency || "USD";
  $("profile-hide-salary").checked = Boolean(profile.hide_unknown_salary);
  $("profile-skills").value = (profile.skills || []).join(", ");
  const status = $("resume-status");
  status.textContent = profile.has_resume
    ? `Using ${profile.resume_filename || "your resume"}. ${(profile.skills || []).length} skills will be highlighted when a job mentions them.`
    : "No resume yet. Overlapping skills stay hidden until you upload a text-based PDF.";
}

function filtersQuery() {
  const params = new URLSearchParams();
  params.set("status", state.status);
  const fields = ["q", "role", "source", "work_mode", "seniority", "employment", "team_size", "work_auth", "posted_within", "salary_min", "salary_currency", "location"];
  for (const id of fields) {
    const value = $(id).value.trim();
    if (value) params.set(id, value);
  }
  if ($("hide_unknown_salary").checked) params.set("hide_unknown_salary", "1");
  return params;
}

function splitList(value) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function tag(text, kind) {
  return el("span", { class: `tag tag-${kind}` }, text);
}

function renderCard(job) {
  const bits = [job.company, job.location, (job.sources || [job.source]).join(" + ")].filter(Boolean);
  if (job.posted_at) bits.push(`posted ${job.posted_at}`);
  const tags = [];
  if (job.team_size) tags.push(tag(`team: ${Number(job.team_size).toLocaleString()} people`, "green"));
  const auth = label("work_auth", job.work_auth);
  if (auth) tags.push(tag(auth, "amber"));
  if (job.salary_label) tags.push(tag(job.salary_label, "green"));
  const mode = label("work_mode", job.work_mode);
  if (mode) tags.push(tag(mode, "slate"));
  const seniority = label("seniority", job.seniority);
  if (seniority) tags.push(tag(seniority, "slate"));
  const employment = label("employment", job.employment);
  if (employment) tags.push(tag(employment, "slate"));
  if (job.industry) tags.push(tag(job.industry, "blue"));

  const actions = [];
  actions.push(el("button", { type: "button", class: "btn", "data-action": "expand", "data-id": job.id }, "Description"));
  if (state.status !== "applied") {
    actions.push(el("button", { type: "button", class: "btn", "data-action": "applied", "data-id": job.id }, "Mark applied"));
  }
  if (state.status !== "discarded") {
    actions.push(el("button", { type: "button", class: "btn", "data-action": "discard", "data-id": job.id }, "Discard"));
  } else {
    actions.push(el("button", { type: "button", class: "btn", "data-action": "restore", "data-id": job.id }, "Restore"));
  }
  if (state.status === "applied") {
    actions.push(el("button", { type: "button", class: "btn", "data-action": "restore", "data-id": job.id }, "Return to feed"));
  }
  for (const link of job.links || []) {
    if (!link.apply_url) continue;
    const text = (job.links || []).length > 1 ? `Apply on ${label("source", link.source) || link.source}` : "Apply";
    actions.push(el("a", { class: "link", href: link.apply_url, target: "_blank", rel: "noopener noreferrer" }, text));
  }

  const children = [
    el("h2", {}, job.title),
    el("p", { class: "meta" }, bits.join(" · ")),
    tags.length ? el("div", { class: "tags" }, tags) : null,
  ];
  if ((job.overlapping_skills || []).length) {
    children.push(el("div", { class: "skills" }, [
      "Resume match",
      ...job.overlapping_skills.map((skill) => el("span", { class: "skill" }, skill)),
    ]));
  }
  if (state.status === "discarded" && job.discard_reason) {
    const reason = state.vocab.labels.discard_reason[job.discard_reason] || job.discard_reason;
    const note = job.discard_note ? ` — ${job.discard_note}` : "";
    children.push(el("p", { class: "note" }, `Discarded: ${reason}${note}`));
  }
  if (state.status === "applied" && job.applied_at) {
    children.push(el("p", { class: "note" }, `Applied ${job.applied_at}`));
  }
  children.push(el("div", { class: "actions" }, actions));
  children.push(el("div", { class: "detail", hidden: "hidden" }));
  return el("article", { class: "card", "data-id": job.id }, children);
}

function renderJobs(payload) {
  $("count").textContent = payload.truncated
    ? `${payload.jobs.length} of ${payload.matched} matching jobs`
    : `${payload.matched} of ${payload.total} jobs`;
  $("count-feed").textContent = `(${payload.counts.feed})`;
  $("count-applied").textContent = `(${payload.counts.applied})`;
  $("count-discarded").textContent = `(${payload.counts.discarded})`;
  const host = $("jobs");
  host.replaceChildren();
  if (!payload.jobs.length) {
    let message = "Nothing matches these filters.";
    if (state.status === "feed" && payload.total === 0 && payload.hidden > 0) {
      message = "Hide rules are keeping every remaining feed job out of view. Restore a company from Discarded, or delete a rule in Settings.";
    } else if (state.status === "feed" && payload.total === 0) {
      const names = state.companies.map((company) => company.name).join(", ");
      message = names
        ? `No jobs yet. Fetch pulls ${names}. You can also add a company or import a file in Settings.`
        : "No jobs yet. Add a company in Settings, then fetch.";
    } else if (state.status === "applied") {
      message = "You have not marked anything applied.";
    } else if (state.status === "discarded") {
      message = "Nothing is discarded.";
    }
    host.append(el("div", { class: "empty" }, message));
    return;
  }
  for (const job of payload.jobs) host.append(renderCard(job));
}

let loadToken = 0;

async function loadJobs() {
  const token = ++loadToken;
  const payload = await api(`/api/jobs?${filtersQuery()}`);
  if (token !== loadToken) return;
  renderJobs(payload);
}

function renderCompanies() {
  const host = $("company-list");
  host.replaceChildren();
  if (!state.companies.length) {
    host.append(el("p", { class: "hint" }, "No companies yet."));
    return;
  }
  for (const company of state.companies) {
    const title = el("strong", {}, company.name);
    const meta = [
      label("source", company.board_type) || company.board_type || "Import",
      company.board_token || "imported",
      company.job_count ? `${company.job_count} jobs` : "no jobs yet",
      company.is_sample ? "sample" : "",
    ].filter(Boolean).join(" · ");
    host.append(el("div", { class: "record" }, [
      el("div", {}, [title, el("p", {}, meta)]),
      el("button", { type: "button", class: "btn", "data-action": "delete-company", "data-id": company.id }, "Delete"),
    ]));
  }
}

function renderRules() {
  const host = $("rule-list");
  host.replaceChildren();
  if (!state.rules.length) {
    host.append(el("p", { class: "hint" }, "No hide rules yet."));
    return;
  }
  for (const rule of state.rules) {
    const kind = rule.kind === "company" ? "Company" : "Title contains";
    host.append(el("div", { class: "record" }, [
      el("div", {}, [el("strong", {}, rule.value), el("p", {}, kind)]),
      el("button", { type: "button", class: "btn", "data-action": "delete-rule", "data-id": rule.id }, "Delete"),
    ]));
  }
}

async function refreshSideData() {
  state.companies = await api("/api/companies");
  state.rules = await api("/api/rules");
  renderCompanies();
  renderRules();
}

function signalList(signals) {
  if (!signals?.length) return null;
  return el("ul", { class: "signals" }, signals.map((signal) => {
    const bits = [signal.source ? `${signal.source}: ` : "", signal.text || ""];
    const item = el("li", {}, bits.join(""));
    if (signal.url) item.append(" ", el("a", { href: signal.url, target: "_blank", rel: "noopener noreferrer" }, "Source"));
    return item;
  }));
}

async function toggleDetail(card) {
  const panel = card.querySelector(".detail");
  const button = card.querySelector('[data-action="expand"]');
  if (!panel.hidden) {
    panel.hidden = true;
    button.textContent = "Description";
    return;
  }
  const id = card.getAttribute("data-id");
  if (!panel.dataset.loaded) {
    const job = await api(`/api/jobs/${id}`);
    const description = el("div", { class: "description" });
    description.innerHTML = job.description_html || "<p>No description was published.</p>";
    const facts = el("form", { class: "stack", "data-action": "facts" }, [
      el("h3", {}, "Company facts"),
      job.summary ? el("p", { class: "summary" }, job.summary) : null,
      job.source_url ? el("p", {}, el("a", { href: job.source_url, target: "_blank", rel: "noopener noreferrer" }, "Public source")) : null,
      !job.summary && !(job.signals || []).length ? el("p", { class: "hint" }, "No public company record yet. You can fill these in yourself.") : null,
      signalList(job.signals),
      el("div", { class: "split" }, [
        el("label", { class: "field" }, ["Team size", el("input", { name: "team_size", type: "number", min: "0", value: job.team_size ?? "" })]),
        el("label", { class: "field" }, ["Industry", el("input", { name: "industry", value: job.industry || "" })]),
      ]),
      el("label", { class: "field" }, ["Summary", el("textarea", { name: "summary", rows: "3" }, job.summary || "")]),
      el("p", { class: "hint" }, "Refresh fills blank facts and updates public signals. Saved edits are kept."),
      el("div", { class: "row" }, [
        el("button", { type: "submit", class: "btn" }, "Save facts"),
        el("button", { type: "button", class: "btn", "data-action": "enrich", "data-id": job.company_id }, "Refresh public facts"),
      ]),
    ]);
    facts.dataset.companyId = job.company_id;
    panel.append(description, facts);
    panel.dataset.loaded = "1";
  }
  panel.hidden = false;
  button.textContent = "Hide description";
}

function openDiscard(id) {
  state.discardId = id;
  $("discard-form").reset();
  $("discard-reason").value = state.vocab.discard_reasons[0];
  $("discard-hide-company").checked = $("discard-reason").value === "company";
  $("discard-error").hidden = true;
  $("modal").hidden = false;
  $("discard-reason").focus();
}

function closeDiscard() {
  $("modal").hidden = true;
  state.discardId = null;
}

function setSettings(open) {
  $("settings-view").hidden = !open;
  $("board-view").hidden = open;
  $("sidebar").hidden = open;
  $("settings-toggle").textContent = open ? "Back to board" : "Settings";
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  const id = target.dataset.id;
  try {
    if (action === "expand") {
      await toggleDetail(target.closest(".card"));
    } else if (action === "applied") {
      await api(`/api/jobs/${id}/applied`, { method: "POST" });
      await loadJobs();
    } else if (action === "discard") {
      openDiscard(id);
    } else if (action === "restore") {
      await api(`/api/jobs/${id}/restore`, { method: "POST" });
      await refreshSideData();
      await loadJobs();
    } else if (action === "delete-company") {
      const company = state.companies.find((item) => String(item.id) === id);
      const name = company ? company.name : "this company";
      if (!confirm(`Delete ${name} and its jobs?`)) return;
      await api(`/api/companies/${id}`, { method: "DELETE" });
      await refreshSideData();
      await loadJobs();
    } else if (action === "delete-rule") {
      await api(`/api/rules/${id}`, { method: "DELETE" });
      await refreshSideData();
      await loadJobs();
    } else if (action === "enrich") {
      target.disabled = true;
      await api(`/api/companies/${id}/enrich`, { method: "POST" });
      const card = target.closest(".card");
      const panel = card.querySelector(".detail");
      panel.dataset.loaded = "";
      panel.replaceChildren();
      panel.hidden = true;
      await toggleDetail(card);
      await loadJobs();
    }
  } catch (error) {
    showBanner(error.message, true);
  } finally {
    if (action === "enrich") target.disabled = false;
  }
});

$("jobs").addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-action='facts']");
  if (!form) return;
  event.preventDefault();
  const team = form.team_size.value.trim();
  try {
    await api(`/api/companies/${form.dataset.companyId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        team_size: team === "" ? null : Number(team),
        industry: form.industry.value,
        summary: form.summary.value,
      }),
    });
    showBanner("Saved company facts.");
    await loadJobs();
  } catch (error) {
    showBanner(error.message, true);
  }
});

$("discard-reason").addEventListener("change", () => {
  $("discard-hide-company").checked = $("discard-reason").value === "company";
});

$("discard-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("discard-error").hidden = true;
  try {
    await api(`/api/jobs/${state.discardId}/discard`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reason: $("discard-reason").value,
        note: $("discard-note").value,
        hide_company: $("discard-hide-company").checked,
        hide_phrase: $("discard-phrase").value,
      }),
    });
    closeDiscard();
    await refreshSideData();
    await loadJobs();
  } catch (error) {
    $("discard-error").hidden = false;
    $("discard-error").textContent = error.message;
  }
});

$("discard-cancel").addEventListener("click", closeDiscard);
$("modal").addEventListener("click", (event) => {
  if (event.target === $("modal")) closeDiscard();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !$("modal").hidden) closeDiscard();
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", async () => {
    state.status = tab.dataset.status;
    document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item === tab));
    try {
      await loadJobs();
    } catch (error) {
      showBanner(error.message, true);
    }
  });
});

let searchTimer = 0;
$("filters").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    loadJobs().catch((error) => showBanner(error.message, true));
  }, 200);
});
$("filters").addEventListener("change", () => {
  loadJobs().catch((error) => showBanner(error.message, true));
});
$("reset-filters").addEventListener("click", () => {
  $("filters").reset();
  $("salary_currency").value = state.profile?.salary_currency || "USD";
  loadJobs().catch((error) => showBanner(error.message, true));
});

$("settings-toggle").addEventListener("click", () => {
  setSettings($("settings-view").hidden);
});

$("fetch").addEventListener("click", async () => {
  const button = $("fetch");
  button.disabled = true;
  button.textContent = "Fetching…";
  showBanner("Fetching public boards and company facts. This can take a minute.");
  try {
    const result = await api("/api/fetch", { method: "POST" });
    const parts = [`Added ${result.added}`, `updated ${result.updated}`];
    if (result.merged) parts.push(`merged ${result.merged}`);
    const problems = [...(result.errors || []), ...(result.enrichment_errors || [])];
    if (problems.length) {
      parts.push(problems.map((item) => `${item.company}: ${item.message}`).join(" "));
    }
    showBanner(parts.join(". ") + ".");
    await refreshSideData();
    await loadJobs();
  } catch (error) {
    showBanner(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Fetch";
  }
});

$("profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const salary = $("profile-salary").value.trim();
    state.profile = await api("/api/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        roles: splitList($("profile-roles").value),
        locations: splitList($("profile-locations").value),
        work_mode: $("profile-work-mode").value,
        seniority: $("profile-seniority").value,
        salary_min: salary === "" ? null : Number(salary),
        salary_currency: $("profile-currency").value,
        skills: splitList($("profile-skills").value),
        hide_unknown_salary: $("profile-hide-salary").checked,
      }),
    });
    fillRoleLocation();
    fillProfileForm();
    showBanner("Saved profile.");
  } catch (error) {
    showBanner(error.message, true);
  }
});

$("resume-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("resume-file").files[0];
  if (!file) {
    showBanner("Choose a PDF first.", true);
    return;
  }
  const body = new FormData();
  body.append("file", file);
  try {
    state.profile = await api("/api/profile/resume", { method: "POST", body });
    fillProfileForm();
    showBanner("Resume uploaded.");
    await loadJobs();
  } catch (error) {
    showBanner(error.message, true);
  }
});

$("company-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/companies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: $("company-name").value,
        board_type: $("company-type").value,
        board_token: $("company-token").value,
      }),
    });
    $("company-form").reset();
    await refreshSideData();
    showBanner("Company added. Fetch to pull its jobs.");
  } catch (error) {
    showBanner(error.message, true);
  }
});

$("import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("import-file").files[0];
  if (!file) {
    showBanner("Choose a CSV or JSON file first.", true);
    return;
  }
  const body = new FormData();
  body.append("file", file);
  try {
    const result = await api("/api/import", { method: "POST", body });
    showBanner(`Imported ${result.imported}. Added ${result.added}, updated ${result.updated}.`);
    $("import-form").reset();
    await refreshSideData();
    setSettings(false);
    await loadJobs();
  } catch (error) {
    showBanner(error.message, true);
  }
});

async function init() {
  try {
    state.vocab = await api("/api/vocab");
    fillVocab();
    state.profile = await api("/api/profile");
    fillRoleLocation();
    applyDefaults();
    await refreshSideData();
    await loadJobs();
  } catch (error) {
    showBanner(error.message, true);
  }
}

init();
