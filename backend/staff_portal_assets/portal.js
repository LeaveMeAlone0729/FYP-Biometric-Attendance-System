"use strict";
(() => {
    const status = document.getElementById("action-status");
    let pending = false;
    let pinTimer;
    let deadlineTimer;
    let registerDirty = false;
    let activeFilter = "All";
    let searchValue = "";

    function showStatus(message, error = false) {
        status.textContent = message;
        status.hidden = false;
        status.classList.toggle("error", error);
        status.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
    function updateCsrf(token) {
        document.querySelectorAll('input[name="csrf"]').forEach(input => { input.value = token; input.defaultValue = token; });
    }
    function filterRoster() {
        let shown = 0;
        const rows = document.querySelectorAll("[data-roster-row]");
        rows.forEach(row => {
            const matchesStatus = activeFilter === "All" || row.dataset.status === activeFilter ||
                (activeFilter === "Present" && row.dataset.status === "Late");
            row.hidden = !matchesStatus || !row.querySelector("td").textContent.toLowerCase().includes(searchValue);
            if (!row.hidden) shown++;
        });
        const count = document.getElementById("visible-count");
        if (count) count.textContent = `${shown} of ${rows.length} students`;
        const empty = document.getElementById("roster-empty");
        if (empty) empty.hidden = shown > 0;
    }
    function restoreFilters() {
        const input = document.getElementById("roster-search");
        if (input) input.value = searchValue;
        document.querySelectorAll("[data-filter]").forEach(button => {
            const active = button.dataset.filter === activeFilter;
            button.classList.toggle("active", active);
            button.setAttribute("aria-pressed", String(active));
        });
        filterRoster();
    }
    function updateRegisterSelection() {
        const form = document.getElementById("register-form");
        if (!form) return;
        const boxes = [...form.querySelectorAll("[data-present-check]")];
        const selected = boxes.filter(box => box.checked).length;
        const count = document.getElementById("selected-count");
        if (count) count.textContent = `${selected} ticked present · ${boxes.length - selected} unticked absent on save`;
        registerDirty = boxes.some(box => !box.disabled && box.checked !== box.defaultChecked) ||
            Boolean(form.elements.namedItem("reason")?.value.trim());
        form.querySelectorAll("[data-register-tools]").forEach(tools => { tools.hidden = false; });
    }
    function applyRegisterDeadline() {
        clearTimeout(deadlineTimer);
        const form = document.getElementById("register-form");
        if (!form || !form.querySelector('button[type="submit"]')) return;
        const remaining = Date.parse(form.dataset.editDeadline) - Date.now();
        if (!Number.isFinite(remaining)) return;
        if (remaining <= 0) {
            form.querySelectorAll('[data-present-check], input[name="reason"], button[type="submit"], [data-tick-visible]').forEach(control => { control.disabled = true; });
            const notice = document.getElementById("register-deadline");
            if (notice) notice.textContent = "The two-hour correction window has ended. This register is now read-only.";
        } else {
            deadlineTimer = setTimeout(applyRegisterDeadline, Math.min(remaining, 2147483647));
        }
    }
    async function refreshContent() {
        const response = await fetch(location.href, { credentials: "same-origin", redirect: "error", signal: AbortSignal.timeout(15000) });
        if (!response.ok) throw new Error("Could not refresh");
        const doc = new DOMParser().parseFromString(await response.text(), "text/html");
        const id = document.getElementById("register-content") ? "register-content" :
            document.getElementById("policy-content") ? "policy-content" : "session-list";
        const content = doc.getElementById(id);
        if (!content) throw new Error("Content unavailable");
        document.getElementById(id).replaceWith(content);
        restoreFilters();
        updateRegisterSelection();
        applyRegisterDeadline();
    }
    function clearPin() {
        clearTimeout(pinTimer);
        const notice = document.getElementById("pin-notice");
        if (!notice) return;
        notice.hidden = true;
        document.getElementById("pin-value").textContent = "";
        document.getElementById("pin-meta").textContent = "";
        document.getElementById("copy-status").textContent = "";
    }
    function showPin(pin) {
        const remaining = Date.parse(pin.expires_at) - Date.now();
        if (!(remaining > 0)) return;
        document.getElementById("pin-value").textContent = pin.pin;
        document.getElementById("pin-meta").textContent = `Session #${pin.session_id} · Expires ${new Date(pin.expires_at).toLocaleString("en-MY", { timeZone: "Asia/Kuala_Lumpur" })}`;
        document.getElementById("pin-notice").hidden = false;
        pinTimer = setTimeout(clearPin, remaining);
    }
    document.addEventListener("input", event => {
        if (event.target.id === "roster-search") {
            searchValue = event.target.value.toLowerCase().trim();
            filterRoster();
        }
        if (event.target.matches('[data-present-check], #register-form input[name="reason"]')) updateRegisterSelection();
    });
    document.addEventListener("change", event => {
        if (event.target.matches("[data-present-check]")) updateRegisterSelection();
    });
    document.addEventListener("click", async event => {
        const tick = event.target.closest("[data-tick-visible]");
        if (tick && !pending) {
            document.querySelectorAll('[data-roster-row]:not([hidden]) [data-present-check]:not(:disabled)').forEach(box => {
                box.checked = tick.dataset.tickVisible === "true";
            });
            updateRegisterSelection();
        }
        const filter = event.target.closest("[data-filter]");
        if (filter) { activeFilter = filter.dataset.filter; restoreFilters(); }
        if (event.target.closest("#copy-pin")) {
            try {
                await navigator.clipboard.writeText(document.getElementById("pin-value").textContent);
                document.getElementById("copy-status").textContent = "PIN copied.";
            } catch {
                document.getElementById("copy-status").textContent = "Select and copy the PIN manually; clipboard access is unavailable.";
            }
        }
    });
    document.addEventListener("submit", async event => {
        const form = event.target;
        if (!form.matches("[data-portal-action]")) return;
        event.preventDefault();
        if (pending) return;
        if (event.submitter?.dataset.confirm && !window.confirm(event.submitter.dataset.confirm)) return;
        const body = new URLSearchParams(new FormData(form));
        if (event.submitter?.name) body.set(event.submitter.name, event.submitter.value);
        pending = true;
        const buttons = [...document.querySelectorAll("button:not(:disabled)")];
        buttons.forEach(button => { button.disabled = true; });
        const registerInputs = form.id === "register-form" ? [...form.querySelectorAll("input:not(:disabled)")] : [];
        registerInputs.forEach(input => { input.disabled = true; });
        clearPin(); showStatus("Saving…");
        try {
            const response = await fetch(form.action, { method: "POST", body, credentials: "same-origin", redirect: "error",
                headers: { Accept: "application/json" }, signal: AbortSignal.timeout(20000) });
            const result = response.headers.get("content-type")?.startsWith("application/json") ? await response.json() : {};
            if (result.csrf) updateCsrf(result.csrf);
            if (!response.ok) {
                const message = result.message || `Request rejected (${response.status}). Reload before retrying.`;
                showStatus(message, true);
                if (response.status === 401) showStatus("Your staff session expired. Sign in again.", true);
                return;
            }
            if (form.id === "register-form") registerDirty = false;
            if (result.pin) showPin(result.pin);
            showStatus(result.message);
            try {
                await refreshContent();
                if (result.csrf) updateCsrf(result.csrf);
            } catch { showStatus(result.message + " Reload to see the latest register; the page could not refresh.", true); }
        } catch {
            const message = "The result could not be confirmed. Reload and review the record before trying again.";
            showStatus(message, true);
        } finally {
            buttons.forEach(button => { button.disabled = false; });
            registerInputs.forEach(input => { input.disabled = false; });
            applyRegisterDeadline();
            pending = false;
        }
    });
    filterRoster();
    updateRegisterSelection();
    applyRegisterDeadline();
    window.addEventListener("beforeunload", event => {
        if (registerDirty) { event.preventDefault(); event.returnValue = ""; }
    });
    window.addEventListener("pagehide", clearPin);
})();
