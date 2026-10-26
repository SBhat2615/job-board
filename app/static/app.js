const state = {
  vocab: null,
  profile: null,
  rules: [],
  status: "feed",
  defaultsApplied: false,
  discardId: null,
  packet: null,
  message: null,
  welcomeResumeSkipped: false,
  forceWelcome: null,
  resumeReady: false,
};

const SAVE_BOOKMARKLET = `javascript:(async()=>{try{const selected=(window.getSelection&&String(window.getSelection()))||'';const box=document.querySelector('.jobs-description__content,.jobs-box__html-content,.jobs-description');const description=(selected.trim().length>40?selected.trim():(box?box.innerText:'')).trim();const heading=document.querySelector('h1');const title=((heading&&heading.innerText)||document.title||'').trim();const companyEl=document.querySelector('.job-details-jobs-unified-top-card__company-name,.jobs-unified-top-card__company-name,a[href*="/company/"]');const company=(companyEl&&companyEl.innerText||'').trim();const locEl=document.querySelector('.job-details-jobs-unified-top-card__primary-description-container,.jobs-unified-top-card__bullet');const place=((locEl&&locEl.innerText)||'').split('·')[0].trim();if(!title||!company||description.length<40){alert('Could not read the title, company, and description. Paste them with Add posting on the job board.');return;}const res=await fetch('http://127.0.0.1:8765/api/import/posting',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,company,location:place,url:window.location.href,description,source:'linkedin'})});const body=await res.json();if(!res.ok){alert(body.detail||'Could not save this posting.');return;}alert('Saved on your job board. Refresh 127.0.0.1:8765.');}catch(e){alert('This page blocked the save. Use Add posting on the job board and paste the description.');}})();`;

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
  if (!state.profile || state.defaultsApplied) return;
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
  $("profile-name").value = profile.full_name || "";
  $("profile-email").value = profile.email || "";
  $("profile-phone").value = profile.phone || "";
  $("profile-city").value = profile.city || "";
  $("profile-title").value = profile.current_title || "";
  $("profile-linkedin").value = profile.linkedin_url || "";
  $("profile-github").value = profile.github_url || "";
  $("profile-portfolio").value = profile.portfolio_url || "";
  $("profile-notice").value = profile.notice_period || "";
  $("profile-note").value = profile.cover_note || "";
  $("profile-yoe-min").value = profile.yoe_min ?? "";
  $("profile-yoe-max").value = profile.yoe_max ?? "";
  $("profile-prefer").value = profile.prefer_text || "";
  $("profile-avoid").value = profile.avoid_text || "";
  const status = $("resume-status");
  status.textContent = profile.has_resume
    ? `Using ${profile.resume_filename || "your resume"}. ${(profile.skills || []).length} skills will be highlighted when a job mentions them.`
    : "No resume yet. Overlapping skills stay hidden until you upload a text-based PDF.";
}

function filtersQuery() {
  const params = new URLSearchParams();
  params.set("status", state.status);
  const fields = ["q", "role", "source", "work_mode", "seniority", "employment", "team_size", "work_auth", "posted_within", "salary_min", "salary_currency", "location", "market", "sort"];
  for (const id of fields) {
    const value = $(id).value.trim();
    if (value) params.set(id, value);
  }
  if ($("hide_unknown_salary").checked) params.set("hide_unknown_salary", "1");
  if (state.status === "feed" && !$("q").value.trim()) params.set("curated", "1");
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
  if (job.contact_count) tags.push(tag(`${job.contact_count} contact${job.contact_count === 1 ? "" : "s"}`, "blue"));
  if (job.followups_due) tags.push(tag("Follow-up due", "amber"));
  for (const flag of job.flags || []) {
    const tone = flag.kind === "open" ? "green" : (flag.kind === "years" || flag.kind === "years-low" ? "slate" : "amber");
    tags.push(tag(flag.label, tone));
  }
  for (const phrase of job.prefer_hits || []) tags.push(tag(`Prefers: ${phrase}`, "green"));
  for (const phrase of job.avoid_hits || []) tags.push(tag(`Poor fit: ${phrase}`, "amber"));

  const actions = [];
  actions.push(el("button", { type: "button", class: "btn", "data-action": "expand", "data-panel": "description", "data-id": job.id }, "Description"));
  actions.push(el("button", { type: "button", class: "btn", "data-action": "expand", "data-panel": "referral", "data-id": job.id }, "Referral"));
  if (state.status !== "discarded") {
    actions.push(el("button", { type: "button", class: "btn", "data-action": "discard", "data-id": job.id }, "Discard"));
  } else {
    actions.push(el("button", { type: "button", class: "btn", "data-action": "restore", "data-id": job.id }, "Restore"));
  }
  const applyLinks = (job.links || []).filter((link) => link.apply_url);
  if (!applyLinks.length && job.apply_url) applyLinks.push({ apply_url: job.apply_url, source: job.source });
  for (const link of applyLinks) {
    const source = label("source", link.source) || link.source;
    const text = applyLinks.length > 1 && source ? `Apply External · ${source}` : "Apply External";
    actions.push(el("a", { class: "btn primary", href: link.apply_url, target: "_blank", rel: "noopener noreferrer" }, text));
  }
  if (state.status === "outreach") {
    actions.push(el("button", { type: "button", class: "btn", "data-action": "referred", "data-id": job.id }, "Got referred"));
  }
  if (state.status !== "applied") {
    actions.push(el("button", { type: "button", class: "btn", "data-action": "applied", "data-id": job.id }, "Mark applied"));
  }
  if (state.status === "applied" || state.status === "outreach") {
    actions.push(el("button", { type: "button", class: "btn", "data-action": "restore", "data-id": job.id }, "Return to feed"));
  }

  const children = [
    el("h2", {}, job.title),
    el("p", { class: "meta" }, bits.join(" · ")),
    tags.length ? el("div", { class: "tags" }, tags) : null,
    el("h3", { class: "card-label" }, "Expectations"),
    el("p", { class: "excerpt" }, job.excerpt || "This posting does not split out a requirements section."),
    el("h3", { class: "card-label" }, "What's missing"),
  ];
  if ((job.missing_skills || []).length) {
    const names = job.missing_skills.join(", ");
    children.push(el("p", {}, `${names} ${job.missing_skills.length === 1 ? "is" : "are"} in this posting's requirements and not on your resume.`));
  } else if (state.profile?.has_resume) {
    children.push(el("p", {}, "The requirement skills read from this posting are already on your resume."));
  } else {
    children.push(el("p", {}, "Upload a resume to compare this posting with your skills."));
  }
  if ((job.overlapping_skills || []).length) {
    children.push(el("div", { class: "skills" }, [
      "On your resume",
      ...job.overlapping_skills.map((skill) => el("span", { class: "skill" }, skill)),
    ]));
  }
  if (state.status === "discarded" && job.discard_reason) {
    const reason = state.vocab.labels.discard_reason[job.discard_reason] || job.discard_reason;
    const note = job.discard_note ? ` — ${job.discard_note}` : "";
    children.push(el("p", { class: "note" }, `Discarded: ${reason}${note}`));
  }
  if (state.status === "outreach") {
    children.push(el("p", { class: "note" }, "Referral sent. It stays here until someone refers you, or you apply yourself."));
  }
  if (state.status === "applied" && job.applied_at) {
    const how = job.referred ? "With referral" : "Without referral";
    children.push(el("p", { class: "note" }, `${how} · applied ${job.applied_at}`));
  }
  children.push(el("div", { class: "actions" }, actions));
  children.push(el("div", { class: "detail", hidden: "hidden" }));
  return el("article", { class: "card", "data-id": job.id }, children);
}

function renderJobs(payload) {
  $("count").textContent = payload.truncated
    ? `${payload.jobs.length} of ${payload.matched} matching jobs`
    : `${payload.matched} of ${payload.total} jobs`;
  $("count-feed").textContent = `(${state.status === "feed" ? payload.matched : payload.counts.feed})`;
  $("count-outreach").textContent = `(${payload.counts.outreach || 0})`;
  $("count-applied").textContent = `(${payload.counts.applied})`;
  $("count-discarded").textContent = `(${payload.counts.discarded})`;
  const host = $("jobs");
  host.replaceChildren();
  if (!payload.jobs.length) {
    let message = "Nothing matches these filters.";
    if (state.status === "feed" && !$("q").value.trim() && !(state.profile?.roles || []).length) {
      message = "Choose the roles you want. The feed shows those roles, not every collected job.";
    } else if (state.status === "feed" && !$("q").value.trim() && (state.profile?.roles || []).length) {
      message = "No collected job matches these roles inside your years window. Search to look through every job, or edit the roles.";
    } else if (state.status === "feed" && payload.total === 0 && payload.hidden > 0) {
      message = "Hide rules are keeping every remaining feed job out of view. Restore a company from Discarded, or delete a rule in Settings.";
    } else if (state.status === "feed" && payload.total > 0 && $("market").value !== "any") {
      message = "Nothing in this market matches. Anywhere shows every saved job.";
    } else if (state.status === "feed" && payload.total === 0) {
      message = "No jobs yet. Fetch reads the company boards and the public feeds. Add posting saves one you paste.";
    } else if (state.status === "outreach" && payload.total === 0) {
      message = "No referral is out yet. Mark a referral sent and the job moves here until someone refers you.";
    } else if (state.status === "applied") {
      message = "You have not marked anything applied.";
    } else if (state.status === "discarded") {
      message = "Nothing is discarded.";
    }
    host.append(el("div", { class: "empty" }, message));
    return;
  }
  if (state.status === "outreach") {
    host.append(el("p", { class: "hint" }, "A job moves here when a referral is marked sent. Got referred files it under Applied, with the referral. Mark applied files it without one."));
  }
  if (state.status === "applied") {
    const referred = payload.jobs.filter((job) => job.referred);
    const direct = payload.jobs.filter((job) => !job.referred);
    host.append(jobGroup("With referral", referred, "Jobs move here from Outreach after someone refers you."));
    host.append(jobGroup("Without referral", direct, "Jobs you applied to directly."));
    return;
  }
  for (const job of payload.jobs) host.append(renderCard(job));
}

function jobGroup(title, jobs, empty) {
  const block = el("section", {}, [el("h2", { class: "group-label" }, `${title} (${jobs.length})`)]);
  if (!jobs.length) block.append(el("p", { class: "hint" }, empty));
  for (const job of jobs) block.append(renderCard(job));
  return block;
}

let loadToken = 0;

async function loadJobs() {
  const token = ++loadToken;
  const payload = await api(`/api/jobs?${filtersQuery()}`);
  if (token !== loadToken) return;
  renderJobs(payload);
  renderSearchSummary();
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
  state.rules = await api("/api/rules");
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

function kindLabel(kind) {
  return { referral: "Referral", follow_up: "Follow-up", cover: "Cover note", answers: "Form answers" }[kind] || "Note";
}

function checkedEvidence(root) {
  return [...root.querySelectorAll('input[name="evidence"]:checked')].map((box) => box.value);
}

function matchBlock(job) {
  const children = [el("h3", {}, "Application draft")];
  if (!(job.evidence || []).length) {
    children.push(el("p", { class: "hint" }, state.profile?.has_resume
      ? "No resume line shares a skill with the requirements section. You can still ask about the posting if a model key is set."
      : "Upload a resume to draft from your own lines."));
  } else {
    children.push(el("p", { class: "hint" }, "These lines are quoted from your resume because they share a skill with the requirements. Uncheck any line that does not belong in the note."));
    const boxes = job.evidence.map((sentence) => el("label", { class: "check" }, [
      el("input", { type: "checkbox", name: "evidence", value: sentence, checked: "checked" }),
      sentence,
    ]));
    children.push(el("div", { class: "stack", "data-evidence": job.id }, boxes));
    children.push(el("button", {
      type: "button",
      class: "btn",
      "data-action": "draft-application",
      "data-job": job.id,
    }, "Draft from checked lines"));
  }
  if (state.profile?.ask_enabled) {
    children.push(el("form", { class: "stack", "data-action": "ask-job", "data-job": job.id }, [
      el("label", { class: "field" }, ["Ask about this job", el("textarea", { name: "question", rows: "2", placeholder: "Should I apply if I will not relocate?" })]),
      el("button", { type: "submit", class: "btn" }, "Ask"),
    ]));
  }
  for (const answer of job.answers || []) {
    children.push(el("div", { class: "record" }, [
      el("div", {}, [
        el("strong", {}, answer.question),
        el("p", {}, answer.answer),
      ]),
    ]));
  }
  return el("div", {}, children);
}

function referralBlock(job) {
  const contacts = job.contacts || [];
  const messages = job.messages || [];
  const children = [
    el("h3", {}, "Referral"),
    el("p", { class: "hint" }, contacts.length
      ? "Draft a note from a contact on the posting, edit it, then open it in your mail app."
      : "No email or LinkedIn profile was published on this posting. Add someone if you want to ask for a referral first."),
  ];
  for (const contact of contacts) children.push(contactRow(contact));
  children.push(el("form", { class: "stack", "data-action": "add-contact", "data-job": job.id }, [
    el("div", { class: "split" }, [
      el("label", { class: "field" }, ["Name", el("input", { name: "name", placeholder: "Ada Lovelace" })]),
      el("label", { class: "field" }, ["Email", el("input", { name: "email", placeholder: "ada@company.com" })]),
    ]),
    el("label", { class: "field" }, ["Profile link", el("input", { name: "link", placeholder: "https://" })]),
    el("button", { type: "submit", class: "btn" }, "Add referral"),
  ]));
  if (messages.length) {
    children.push(el("h3", {}, "Messages"));
    for (const message of messages) children.push(messageRow(message));
  }
  return el("div", {}, children);
}

function contactRow(contact) {
  const meta = [contact.role, contact.email].filter(Boolean).join(" · ");
  return el("div", { class: "record" }, [
    el("div", {}, [
      el("strong", {}, contact.name || contact.email || "Contact"),
      meta ? el("p", {}, meta) : null,
      contact.link ? el("a", { class: "link", href: contact.link, target: "_blank", rel: "noopener noreferrer" }, "Profile") : null,
    ]),
    el("div", { class: "row" }, [
      el("button", {
        type: "button",
        class: "btn",
        "data-action": "draft-referral",
        "data-job": contact.job_id,
        "data-contact": contact.id,
      }, "Draft referral"),
      el("button", { type: "button", class: "btn", "data-action": "delete-contact", "data-id": contact.id, "data-job": contact.job_id }, "Remove"),
    ]),
  ]);
}

function messageRow(message) {
  const when = message.follow_up_on ? `Follow up ${message.follow_up_on}` : message.status;
  const buttons = [
    el("button", { type: "button", class: "btn", "data-action": "edit-message", "data-message": message.id }, "Open"),
  ];
  if (message.status === "sent" && (message.kind === "referral" || message.kind === "follow_up")) {
    buttons.push(el("button", {
      type: "button",
      class: "btn",
      "data-action": "draft-followup",
      "data-job": message.job_id,
      "data-message": message.id,
      "data-contact": message.contact_id || "",
    }, "Write follow-up"));
  }
  return el("div", { class: "record" }, [
    el("div", {}, [
      el("strong", {}, message.subject),
      el("p", {}, `${kindLabel(message.kind)} · ${message.status} · ${when}`),
    ]),
    el("div", { class: "row" }, buttons),
  ]);
}

function setPanelButtons(card, open) {
  const description = card.querySelector('[data-panel="description"]');
  const referral = card.querySelector('[data-panel="referral"]');
  if (description) description.textContent = open === "description" ? "Hide description" : "Description";
  if (referral) referral.textContent = open === "referral" ? "Hide referral" : "Referral";
}

async function toggleDetail(card, panelName = "description") {
  const panel = card.querySelector(".detail");
  if (panel.dataset.open === panelName && !panel.hidden) {
    panel.hidden = true;
    panel.dataset.open = "";
    setPanelButtons(card, "");
    return;
  }
  if (!panel.dataset.loaded) {
    const job = await api(`/api/jobs/${card.getAttribute("data-id")}`);
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
    rememberMessages(job.messages || []);
    panel.append(
      el("div", { class: "panel-description" }, [description, facts]),
      el("div", { class: "panel-referral" }, [referralBlock(job)]),
    );
    panel.dataset.loaded = "1";
  }
  panel.querySelector(".panel-description").hidden = panelName !== "description";
  panel.querySelector(".panel-referral").hidden = panelName !== "referral";
  panel.hidden = false;
  panel.dataset.open = panelName;
  setPanelButtons(card, panelName);
}

async function reopenPanel(jobId, panelName) {
  const card = document.querySelector(`.card[data-id="${jobId}"]`);
  if (card) await toggleDetail(card, panelName);
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
  $("settings-toggle").textContent = open ? "Back to board" : "Settings";
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  const id = target.dataset.id;
  try {
    if (action === "expand") {
      await toggleDetail(target.closest(".card"), target.dataset.panel || "description");
    } else if (action === "draft-application") {
      const saved = await api(`/api/jobs/${target.dataset.job}/drafts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ evidence: checkedEvidence(target.closest(".detail")) }),
      });
      rememberMessages([saved.cover, saved.answers]);
      openMessage(saved.cover);
      await loadCurrent();
    } else if (action === "draft-referral") {
      const message = await api(`/api/jobs/${target.dataset.job}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: "referral", contact_id: Number(target.dataset.contact) }),
      });
      rememberMessages([message]);
      openMessage(message);
      await loadCurrent();
    } else if (action === "draft-followup") {
      const message = await api(`/api/jobs/${target.dataset.job}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind: "follow_up",
          parent_id: Number(target.dataset.message),
          contact_id: target.dataset.contact ? Number(target.dataset.contact) : null,
        }),
      });
      rememberMessages([message]);
      openMessage(message);
      await loadCurrent();
    } else if (action === "edit-message") {
      const message = (state.messages || {})[target.dataset.message];
      if (message) openMessage(message);
    } else if (action === "delete-contact") {
      const jobId = target.dataset.job;
      await api(`/api/contacts/${id}`, { method: "DELETE" });
      showBanner("Contact removed.");
      await loadCurrent();
      await reopenPanel(jobId, "referral");
    } else if (action === "referred") {
      await api(`/api/jobs/${id}/referred`, { method: "POST" });
      showBanner("Filed under Applied, with the referral.");
      await loadCurrent();
    } else if (action === "applied") {
      await api(`/api/jobs/${id}/applied`, { method: "POST" });
      await loadCurrent();
    } else if (action === "discard") {
      openDiscard(id);
    } else if (action === "restore") {
      await api(`/api/jobs/${id}/restore`, { method: "POST" });
      await refreshSideData();
      await loadCurrent();
    } else if (action === "delete-rule") {
      await api(`/api/rules/${id}`, { method: "DELETE" });
      await refreshSideData();
      await loadCurrent();
    } else if (action === "enrich") {
      target.disabled = true;
      const jobId = target.closest(".card").getAttribute("data-id");
      await api(`/api/companies/${id}/enrich`, { method: "POST" });
      await loadCurrent();
      await reopenPanel(jobId, "description");
    }
  } catch (error) {
    showBanner(error.message, true);
  } finally {
    if (action === "enrich") target.disabled = false;
  }
});

$("jobs").addEventListener("submit", async (event) => {
  const askForm = event.target.closest("[data-action='ask-job']");
  if (askForm) {
    event.preventDefault();
    try {
      await api(`/api/jobs/${askForm.dataset.job}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: askForm.question.value,
          evidence: checkedEvidence(askForm.closest(".detail")),
        }),
      });
      showBanner("Answer saved on this job.");
      const jobId = askForm.dataset.job;
      await loadCurrent();
      await reopenPanel(jobId, "description");
    } catch (error) {
      showBanner(error.message, true);
    }
    return;
  }
  const contactForm = event.target.closest("[data-action='add-contact']");
  if (contactForm) {
    event.preventDefault();
    try {
      await api(`/api/jobs/${contactForm.dataset.job}/contacts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: contactForm.name.value,
          email: contactForm.email.value,
          link: contactForm.link.value,
        }),
      });
      showBanner("Referral added.");
      const jobId = contactForm.dataset.job;
      await loadCurrent();
      await reopenPanel(jobId, "referral");
    } catch (error) {
      showBanner(error.message, true);
    }
    return;
  }
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
    const jobId = form.closest(".card").getAttribute("data-id");
    await loadCurrent();
    await reopenPanel(jobId, "description");
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
    await loadCurrent();
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
  if (event.key !== "Escape") return;
  if (!$("modal").hidden) closeDiscard();
  if (!$("message-modal").hidden) closeMessage();
  if (!$("posting-modal").hidden) closePosting();
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", async () => {
    state.status = tab.dataset.status;
    document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item === tab));
    try {
      await loadCurrent();
    } catch (error) {
      showBanner(error.message, true);
    }
  });
});

let searchTimer = 0;
$("filters").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    loadCurrent().catch((error) => showBanner(error.message, true));
  }, 200);
});
$("filters").addEventListener("change", () => {
  loadCurrent().catch((error) => showBanner(error.message, true));
});
$("reset-filters").addEventListener("click", () => {
  $("filters").reset();
  $("salary_currency").value = state.profile?.salary_currency || "USD";
  loadCurrent().catch((error) => showBanner(error.message, true));
});

$("settings-toggle").addEventListener("click", () => {
  setSettings($("settings-view").hidden);
});

$("fetch").addEventListener("click", async () => {
  const button = $("fetch");
  button.disabled = true;
  button.textContent = "Fetching…";
  showBanner("Fetching company boards and remote feeds. A first pull can take a few minutes.");
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
    await loadCurrent();
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
        full_name: $("profile-name").value,
        email: $("profile-email").value,
        phone: $("profile-phone").value,
        city: $("profile-city").value,
        current_title: $("profile-title").value,
        linkedin_url: $("profile-linkedin").value,
        github_url: $("profile-github").value,
        portfolio_url: $("profile-portfolio").value,
        notice_period: $("profile-notice").value,
        cover_note: $("profile-note").value,
        prefer_text: $("profile-prefer").value,
        avoid_text: $("profile-avoid").value,
        yoe_min: numberOrNull($("profile-yoe-min").value),
        yoe_max: numberOrNull($("profile-yoe-max").value),
      }),
    });
    fillRoleLocation();
    fillProfileForm();
    await loadRoleReview();
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
    state.resumeReady = true;
    state.forceWelcome = "roles";
    await loadRoleReview();
    showWelcome();
    showBanner("Resume replaced. Choose the roles to look for.");
  } catch (error) {
    showBanner(error.message, true);
  }
});

$("message-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("message-error").hidden = true;
  try {
    await saveMessage("draft");
    showBanner("Draft saved.");
  } catch (error) {
    $("message-error").hidden = false;
    $("message-error").textContent = error.message;
  }
});
$("message-sent").addEventListener("click", async () => {
  try {
    const saved = await saveMessage("sent");
    const application = saved.kind === "cover" || saved.kind === "answers";
    if (application) {
      showBanner("Marked used. Nothing was sent.");
    } else if (saved.follow_up_on) {
      showBanner(`Marked sent. This job is under Outreach. Follow up on ${saved.follow_up_on}.`);
    } else {
      showBanner("Marked sent. This job is under Outreach.");
    }
  } catch (error) {
    showBanner(error.message, true);
  }
});
$("message-replied").addEventListener("click", async () => {
  try {
    await saveMessage("replied");
    showBanner("Marked replied.");
  } catch (error) {
    showBanner(error.message, true);
  }
});
$("message-mail").addEventListener("click", async () => {
  try {
    const saved = await saveMessage(state.message.status === "sent" ? "sent" : "draft");
    const email = saved.contact_email || "";
    const href = `mailto:${email}?subject=${encodeURIComponent(saved.subject)}&body=${encodeURIComponent(saved.body)}`;
    if (href.length > 1800) {
      await copyText(`${saved.subject}\n\n${saved.body}`);
      showBanner("This note is too long for a mailto link. The subject and body are copied; paste them into your mail app.", true);
      return;
    }
    window.location.href = href;
  } catch (error) {
    showBanner(error.message, true);
  }
});
$("message-followup").addEventListener("click", async () => {
  if (!state.message) return;
  try {
    const message = await api(`/api/jobs/${state.message.job_id}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: "follow_up",
        parent_id: state.message.id,
        contact_id: state.message.contact_id,
      }),
    });
    openMessage(message);
    await loadCurrent();
  } catch (error) {
    showBanner(error.message, true);
  }
});
$("message-close").addEventListener("click", closeMessage);
$("message-modal").addEventListener("click", (event) => {
  if (event.target === $("message-modal")) closeMessage();
});

function rememberMessages(messages) {
  state.messages = state.messages || {};
  for (const message of messages) state.messages[message.id] = message;
}

async function copyText(text) {
  if (!text) {
    showBanner("Nothing to copy.", true);
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
}

function closeMessage() {
  $("message-modal").hidden = true;
}

function openMessage(message) {
  state.message = message;
  rememberMessages([message]);
  const who = message.contact_name || message.contact_email || "";
  const titles = {
    follow_up: "Follow-up draft",
    cover: "Cover note",
    answers: "Form answers",
  };
  const application = message.kind === "cover" || message.kind === "answers";
  $("message-title").textContent = titles[message.kind] || "Referral draft";
  $("message-meta").textContent = [message.company, message.job_title, who].filter(Boolean).join(" · ");
  $("message-subject").value = message.subject || "";
  $("message-body").value = message.body || "";
  $("message-follow").value = message.follow_up_on || "";
  $("message-follow").closest("label").hidden = application;
  $("message-followup").hidden = application;
  $("message-sent").textContent = application ? "Mark used" : "Mark sent";
  $("message-hint").textContent = application
    ? "This stays a draft until you mark it used. Nothing is emailed or submitted."
    : "Opening mail does not mark it sent. Mark sent after it leaves your inbox. A referral then comes due again in five days unless you pick another date.";
  $("message-error").hidden = true;
  $("message-modal").hidden = false;
  $("message-subject").focus();
}

async function saveMessage(status) {
  const saved = await api(`/api/messages/${state.message.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      subject: $("message-subject").value,
      body: $("message-body").value,
      status,
      follow_up_on: $("message-follow").value,
    }),
  });
  openMessage(saved);
  await loadCurrent();
  return saved;
}

async function loadCurrent() {
  await loadJobs();
}

async function init() {
  try {
    state.vocab = await api("/api/vocab");
    fillVocab();
    state.profile = await api("/api/profile");
    fillRoleLocation();
    applyDefaults();
    await loadRoleReview();
    showWelcome();
    await refreshSideData();
    await loadCurrent();
  } catch (error) {
    showBanner(error.message, true);
  }
}

function numberOrNull(value) {
  const text = String(value ?? "").trim();
  return text === "" ? null : Number(text);
}

function showWelcome() {
  const profile = state.profile;
  const force = state.forceWelcome;
  if (!force && (!profile || profile.welcome_done)) {
    $("welcome").hidden = true;
    renderSearchSummary();
    return;
  }
  $("welcome").hidden = false;
  const resumeStep = force === "resume" || (!profile?.welcome_done && !state.resumeReady && force !== "roles");
  $("welcome-resume").hidden = !resumeStep;
  $("welcome-roles").hidden = resumeStep;
  if (profile?.has_resume) {
    $("welcome-current").textContent = `Current file: ${profile.resume_filename || "your resume"}. Upload a new PDF to replace it, or read this one.`;
    $("welcome-read").hidden = false;
  } else {
    $("welcome-current").textContent = "No resume on file yet.";
    $("welcome-read").hidden = true;
  }
  if (resumeStep) return;
  const skills = (profile?.skills || []).slice(0, 12);
  $("welcome-skills").textContent = profile?.has_resume
    ? `Read from ${profile.resume_filename || "your resume"}${skills.length ? `. Skills found: ${skills.join(", ")}.` : "."}`
    : "No resume yet. Add the roles you want to look for.";
  $("welcome-yoe-min").value = profile?.yoe_min ?? "";
  $("welcome-yoe-max").value = profile?.yoe_max ?? "";
  renderWelcomeRoles();
  updateWelcomeWindow();
}

function roleCheck(role, checked, caption) {
  const box = el("input", { type: "checkbox", value: role });
  box.checked = checked;
  return el("label", { class: "check" }, [box, caption || role]);
}

function renderWelcomeRoles() {
  const host = $("welcome-role-choices");
  const latest = state.roleReview?.latest || "";
  const recs = state.roleReview?.recommendations || [];
  const saved = new Set((state.profile?.roles || []).map((role) => role.toLowerCase()));
  host.replaceChildren();
  if (!latest && !recs.length) {
    host.append(el("p", { class: "hint" }, "No role was found in the resume. Add the ones you want below."));
    return;
  }
  if (latest) {
    host.append(el("p", { class: "hint" }, "Latest role from the resume"));
    const checked = saved.size ? saved.has(latest.toLowerCase()) : true;
    host.append(roleCheck(latest, checked));
  }
  const extra = recs.filter((role) => role.toLowerCase() !== latest.toLowerCase());
  if (extra.length) {
    host.append(el("p", { class: "hint" }, "Similar roles"));
    for (const role of extra) host.append(roleCheck(role, saved.has(role.toLowerCase())));
  }
}

function updateWelcomeWindow() {
  const min = numberOrNull($("welcome-yoe-min").value);
  const max = numberOrNull($("welcome-yoe-max").value);
  const note = $("welcome-window");
  if (min == null && max == null) {
    note.textContent = "Add years of experience to filter. The search keeps one year below and one year above, and a posting whose range still overlaps that band.";
    return;
  }
  const low = Math.max(0, (min ?? max) - 1);
  const high = (max ?? min) + 1;
  note.textContent = `Jobs that ask for ${low}–${high} years are shown. A posting that says 3–7 years stays when that range overlaps. A posting with no years stated stays in the list.`;
}

function selectedWelcomeRoles() {
  const chosen = [...$("welcome-role-choices").querySelectorAll("input:checked")].map((box) => box.value);
  const extra = splitList($("welcome-role-extra").value);
  const roles = [];
  const seen = new Set();
  for (const role of [...chosen, ...extra]) {
    const key = role.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    roles.push(role);
  }
  return roles;
}

function welcomeProfile(overrides) {
  const profile = state.profile || {};
  return {
    roles: profile.roles || [],
    locations: profile.locations || [],
    work_mode: profile.work_mode || "any",
    seniority: profile.seniority || "any",
    salary_min: profile.salary_min ?? null,
    salary_currency: profile.salary_currency || "USD",
    skills: profile.skills || [],
    hide_unknown_salary: Boolean(profile.hide_unknown_salary),
    full_name: profile.full_name || "",
    email: profile.email || "",
    phone: profile.phone || "",
    city: profile.city || "",
    current_title: profile.current_title || "",
    linkedin_url: profile.linkedin_url || "",
    github_url: profile.github_url || "",
    portfolio_url: profile.portfolio_url || "",
    notice_period: profile.notice_period || "",
    cover_note: profile.cover_note || "",
    prefer_text: profile.prefer_text || "",
    avoid_text: profile.avoid_text || "",
    yoe_min: profile.yoe_min ?? null,
    yoe_max: profile.yoe_max ?? null,
    ...overrides,
  };
}

async function completeWelcome(profile) {
  state.profile = profile;
  state.defaultsApplied = false;
  fillRoleLocation();
  applyDefaults();
  fillProfileForm();
  state.forceWelcome = null;
  state.resumeReady = false;
  showWelcome();
  await loadRoleReview();
  await loadCurrent();
}

async function loadRoleReview() {
  try {
    state.roleReview = await api("/api/profile/roles");
  } catch (error) {
    state.roleReview = { latest: "", recommendations: [], roles: [], window: null };
    showBanner(error.message, true);
  }
  renderSearchSummary();
}

function renderSearchSummary() {
  const text = $("search-summary-text");
  if (!text) return;
  if ($("q").value.trim()) {
    text.textContent = "Search is looking through every collected job.";
    return;
  }
  const roles = state.profile?.roles || [];
  if (!roles.length) {
    text.textContent = "Upload a resume and choose roles. The feed shows those roles, not every collected job.";
    return;
  }
  const min = state.profile?.yoe_min;
  const max = state.profile?.yoe_max;
  const years = min != null || max != null ? `${min ?? max}–${max ?? min} years` : "any years";
  const window = state.roleReview?.window;
  const band = window
    ? ` Jobs asking for ${window[0]}–${window[1]} years are included, including a wider range that overlaps.`
    : "";
  text.textContent = `Showing ${roles.join(", ")} · ${years}.${band}`;
}

async function saveRoles(roles) {
  state.profile = await api("/api/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(welcomeProfile({ roles })),
  });
  fillRoleLocation();
  fillProfileForm();
  await loadRoleReview();
}

function closePosting() {
  $("posting-modal").hidden = true;
}

$("welcome-resume-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("welcome-resume-file").files[0];
  if (!file) {
    showBanner("Choose a PDF first.", true);
    return;
  }
  const body = new FormData();
  body.append("file", file);
  try {
    state.profile = await api("/api/profile/resume", { method: "POST", body });
    fillProfileForm();
    state.resumeReady = true;
    state.forceWelcome = "roles";
    await loadRoleReview();
    showWelcome();
    showBanner("Resume uploaded. Choose the roles to look for.");
  } catch (error) {
    showBanner(error.message, true);
  }
});

$("welcome-skip-resume").addEventListener("click", () => {
  state.resumeReady = true;
  state.forceWelcome = "roles";
  showWelcome();
});

$("welcome-read").addEventListener("click", async () => {
  state.resumeReady = true;
  state.forceWelcome = "roles";
  await loadRoleReview();
  showWelcome();
});

$("welcome-yoe-min").addEventListener("input", updateWelcomeWindow);
$("welcome-yoe-max").addEventListener("input", updateWelcomeWindow);

$("welcome-roles-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const saved = await api("/api/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(welcomeProfile({
        roles: selectedWelcomeRoles(),
        yoe_min: numberOrNull($("welcome-yoe-min").value),
        yoe_max: numberOrNull($("welcome-yoe-max").value),
      })),
    });
    state.profile = await api("/api/profile/welcome", { method: "POST" });
    state.profile = { ...state.profile, ...saved, welcome_done: true };
    await completeWelcome(state.profile);
    showBanner("Showing jobs for those roles and years. Search looks through every collected job.");
  } catch (error) {
    showBanner(error.message, true);
  }
});

$("welcome-skip-roles").addEventListener("click", async () => {
  try {
    state.forceWelcome = null;
    state.profile = await api("/api/profile/welcome", { method: "POST" });
    showWelcome();
    await loadCurrent();
  } catch (error) {
    showBanner(error.message, true);
  }
});

$("edit-roles").addEventListener("click", async () => {
  state.forceWelcome = "roles";
  await loadRoleReview();
  showWelcome();
});

$("reupload-resume").addEventListener("click", () => {
  state.forceWelcome = "resume";
  showWelcome();
});

$("add-posting").addEventListener("click", () => {
  $("posting-error").hidden = true;
  $("posting-modal").hidden = false;
  $("posting-title-input").focus();
});

$("posting-close").addEventListener("click", closePosting);
$("posting-modal").addEventListener("click", (event) => {
  if (event.target === $("posting-modal")) closePosting();
});

$("posting-bookmarklet").addEventListener("click", async () => {
  await copyText(SAVE_BOOKMARKLET);
  showBanner("Bookmarklet copied. Save it as a bookmark, then open it on a LinkedIn job.");
});

$("posting-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("posting-error").hidden = true;
  try {
    const result = await api("/api/import/posting", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: $("posting-title-input").value,
        company: $("posting-company").value,
        location: $("posting-location").value,
        url: $("posting-url").value,
        description: $("posting-description").value,
        source: $("posting-source").value,
      }),
    });
    closePosting();
    $("posting-form").reset();
    showBanner(`Saved. Added ${result.added}, updated ${result.updated}.`);
    await refreshSideData();
    await loadCurrent();
  } catch (error) {
    $("posting-error").hidden = false;
    $("posting-error").textContent = error.message;
  }
});

init();
