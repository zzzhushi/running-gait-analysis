import * as api from "../api.js";
import { el } from "../format.js";

export default async function upload(app) {
  // ---------------------------------------------------------------- user section
  let users = [];
  try { users = await api.listUsers(); } catch { /* server may not have users yet */ }
  let activeUser = api.getActiveUser();
  if (!activeUser || !users.find((u) => u.id === activeUser.id)) {
    activeUser = users[0] || null;
    if (activeUser) api.setActiveUser(activeUser);
  }

  const userSel = el("select", { style: "flex:1" },
    users.map((u) => el("option", { value: u.id }, u.name)));
  if (activeUser) userSel.value = activeUser.id;

  const newUserToggle = el("button", { class: "btn btn-sm", type: "button" }, "+ New user");
  const newUserForm = el("div", { style: "display:none;margin-top:12px;padding:12px;background:var(--panel2);border:1px solid var(--line);border-radius:10px" });

  // new-user form fields
  const nuName    = el("input", { type: "text", placeholder: "Name" });
  const nuSex     = el("select", {}, [["", "Sex — optional"], ["female", "Female"], ["male", "Male"]].map(([v, t]) => el("option", { value: v }, t)));
  const nuHeight  = el("input", { type: "number", placeholder: "Height cm", min: "100", max: "230" });
  const nuLeg     = el("input", { type: "number", placeholder: "Leg cm", min: "50", max: "120" });
  const nuSave    = el("button", { class: "btn btn-accent btn-sm", type: "button" }, "Create");
  const nuCancel  = el("button", { class: "btn btn-sm", type: "button" }, "Cancel");
  const nuStatus  = el("span", { style: "font-size:12px;color:var(--muted);margin-left:8px" }, "");
  newUserForm.append(
    el("div", { style: "display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px" }, [
      el("div", { class: "field", style: "margin:0;grid-column:1/-1" }, [el("label", {}, "Name"), nuName]),
      el("div", { class: "field", style: "margin:0" }, [el("label", {}, "Sex — optional"), nuSex]),
      el("div", { class: "field", style: "margin:0" }, [el("label", {}, "Height (cm) — optional"), nuHeight]),
      el("div", { class: "field", style: "margin:0" }, [el("label", {}, "Leg length (cm) — optional"), nuLeg]),
    ]),
    el("div", { style: "display:flex;align-items:center;gap:8px" }, [nuSave, nuCancel, nuStatus]),
  );

  newUserToggle.addEventListener("click", () => {
    newUserForm.style.display = newUserForm.style.display === "none" ? "block" : "none";
    if (newUserForm.style.display === "block") nuName.focus();
  });
  nuCancel.addEventListener("click", () => { newUserForm.style.display = "none"; });
  nuSave.addEventListener("click", async () => {
    const name = nuName.value.trim();
    if (!name) { nuStatus.textContent = "Name is required."; nuStatus.style.color = "var(--bad)"; return; }
    nuSave.disabled = true;
    try {
      const created = await api.createUser({
        name,
        sex: nuSex.value || null,
        height_cm: nuHeight.value ? parseFloat(nuHeight.value) : null,
        leg_length_cm: nuLeg.value ? parseFloat(nuLeg.value) : null,
      });
      users.push(created);
      userSel.append(el("option", { value: created.id }, created.name));
      userSel.value = created.id;
      activeUser = created;
      api.setActiveUser(created);
      newUserForm.style.display = "none";
      nuName.value = ""; nuSex.value = ""; nuHeight.value = ""; nuLeg.value = "";
      nuStatus.textContent = "";
      prefillProfile(created);
      // refresh topbar user switcher
      location.reload();
    } catch (e) {
      nuStatus.textContent = "Failed: " + e.message;
      nuStatus.style.color = "var(--bad)";
      nuSave.disabled = false;
    }
  });

  // ---------------------------------------------------------------- run fields
  const labelInput   = el("input", { type: "text", placeholder: "e.g. Tuesday tempo — side" });
  const videoSel     = el("select", {}, [el("option", { value: "" }, "— pick a video —")]);
  const viewSel      = el("select", {}, ["side-left", "side-right", "rear", "front"]
    .map((v) => el("option", { value: v }, v)));
  const speedInput   = el("input", { type: "number", placeholder: "optional, e.g. 12.5", step: "0.1", min: "0" });
  const sexSel       = el("select", {}, [["", "—"], ["female", "Female"], ["male", "Male"]].map(([v, t]) => el("option", { value: v }, t)));
  const heightInput  = el("input", { type: "number", placeholder: "optional, e.g. 178", min: "100", max: "230" });
  const legInput     = el("input", { type: "number", placeholder: "optional, e.g. 82", min: "50", max: "120" });
  const forceCheck   = el("input", { type: "checkbox" });
  const analyzeBtn   = el("button", { class: "btn btn-accent", disabled: true }, "Extract & Analyze");
  const statusEl     = el("div", { style: "font-size:13px;margin-top:10px;min-height:18px" }, "");
  const logPre       = el("pre", {
    style: "display:none;margin-top:12px;font-size:11px;line-height:1.5;background:#0b0f14;border:1px solid var(--line);border-radius:8px;padding:10px 12px;overflow:auto;max-height:220px;white-space:pre-wrap;color:var(--muted)",
  }, "");

  function prefillProfile(user) {
    if (!user) return;
    sexSel.value = user.sex || "";
    heightInput.value = user.height_cm || "";
    legInput.value = user.leg_length_cm || "";
  }
  prefillProfile(activeUser);

  userSel.addEventListener("change", () => {
    activeUser = users.find((u) => u.id === userSel.value) || null;
    if (activeUser) api.setActiveUser(activeUser);
    prefillProfile(activeUser);
  });

  // populate video dropdown
  function fmtMtime(iso) {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  }
  api.listVideos().then((videos) => {
    for (const v of videos) {
      const text = v.filename + "  ·  " + fmtMtime(v.mtime) + (v.cached ? "  · cached" : "");
      videoSel.append(el("option", { value: v.stem }, text));
    }
    if (!videos.length) videoSel.append(el("option", { value: "", disabled: true }, "No videos found in data/video/"));
  }).catch(() => {
    videoSel.append(el("option", { value: "", disabled: true }, "Could not load video list"));
  });

  function updateBtn() {
    analyzeBtn.disabled = !videoSel.value || !viewSel.value || !labelInput.value.trim();
  }
  labelInput.addEventListener("input", updateBtn);
  videoSel.addEventListener("change", updateBtn);
  viewSel.addEventListener("change", updateBtn);

  analyzeBtn.addEventListener("click", async () => {
    const stem  = videoSel.value;
    const view  = viewSel.value;
    const label = labelInput.value.trim();
    if (!stem || !view || !label) return;
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = "Extracting…";
    statusEl.textContent = "Running pose extraction — this may take a minute or two…";
    statusEl.style.color = "var(--muted)";
    logPre.style.display = "none";
    logPre.textContent = "";
    try {
      const profile = {};
      if (sexSel.value)      profile.sex = sexSel.value;
      if (heightInput.value) profile.height_cm = parseFloat(heightInput.value);
      if (legInput.value)    profile.leg_length_cm = parseFloat(legInput.value);
      if (speedInput.value)  profile.speed_kmh = parseFloat(speedInput.value);
      const res = await api.ingest(stem, view, {
        force:   forceCheck.checked,
        label,
        profile: Object.keys(profile).length ? profile : null,
        user_id: activeUser ? activeUser.id : null,
      });
      api.setVideoUrl(res.id, "/api/video/" + stem);
      statusEl.textContent = (res.cached ? "✓ Cached pose reused" : "✓ Fresh extraction complete") + "  ·  navigating…";
      statusEl.style.color = "var(--accent, #4caf50)";
      if (res.extractor_log) { logPre.textContent = res.extractor_log; logPre.style.display = "block"; }
      location.hash = "#/report/" + res.id;
    } catch (e) {
      statusEl.textContent = "Extraction failed: " + e.message;
      statusEl.style.color = "var(--red, #e57373)";
      analyzeBtn.disabled = false;
      analyzeBtn.textContent = "Extract & Analyze";
      try {
        const body = JSON.parse(e.message.replace(/^HTTP \d+ /, "") || "{}");
        if (body.extractor_log) { logPre.textContent = body.extractor_log; logPre.style.display = "block"; }
      } catch (_) { /* ignore */ }
    }
  });

  // ---------------------------------------------------------------- layout
  app.append(
    el("div", { class: "crumb" }, [el("a", { "data-nav": "#/library" }, "← Library")]),
    el("div", { class: "page-head" }, [el("div", {}, [
      el("h1", {}, "New analysis"),
      el("p", {}, "Everything runs locally — your video never leaves this machine."),
    ])]),
    el("div", { style: "display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px" }, [
      // user picker row (full-width)
      el("div", { class: "field", style: "grid-column:1/-1" }, [
        el("label", {}, "User"),
        el("div", { style: "display:flex;gap:8px;align-items:center" }, [userSel, newUserToggle]),
        newUserForm,
      ]),
      // label (full-width)
      el("div", { class: "field", style: "grid-column:1/-1" }, [el("label", {}, "Label"), labelInput]),
      // video + view
      el("div", { class: "field" }, [el("label", {}, "Video"), videoSel]),
      el("div", { class: "field" }, [el("label", {}, "View"), viewSel]),
      // force re-extract (full-width)
      el("div", { class: "field", style: "grid-column:1/-1" }, [
        el("label", { style: "display:flex;align-items:center;gap:8px;font-weight:normal;cursor:pointer" }, [
          forceCheck,
          el("span", { style: "font-size:13px;color:var(--muted)" }, "Force re-extract even if cached"),
        ]),
      ]),
      // per-run: speed
      el("div", { class: "field" }, [el("label", {}, "Treadmill speed (km/h) — optional, enables stride length"), speedInput]),
      el("div", {}), // spacer
      // profile (pre-filled from user, per-run override)
      el("div", { class: "field" }, [el("label", {}, "Sex — optional, personalizes injury-risk norms"), sexSel]),
      el("div", { class: "field" }, [el("label", {}, "Your height (cm) — optional, enables cm & vertical ratio"), heightInput]),
      el("div", { class: "field" }, [el("label", {}, "Leg length (cm) — optional, personalizes cadence & scale"), legInput]),
    ]),
    el("div", { style: "margin:14px 0 6px" }, [analyzeBtn]),
    statusEl,
    logPre,
  );
}
