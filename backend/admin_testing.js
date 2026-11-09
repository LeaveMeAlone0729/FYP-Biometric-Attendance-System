"use strict";

const management = document.getElementById("management");
if (management) {
    const status = document.getElementById("action-status");
    const pinNotice = document.getElementById("action-pin");
    const pinValue = document.getElementById("pin-value");
    const pinMeta = document.getElementById("pin-meta");
    const copyStatus = document.getElementById("copy-status");
    const dialog = document.getElementById("confirmation");
    let pending = false;
    let pinTimer;
    let confirmationForm;

    function showStatus(message, error = false) {
        status.textContent = message;
        status.classList.toggle("error", error);
        status.scrollIntoView({ block: "nearest" });
    }

    function clearPin() {
        if (!pinNotice) return;
        clearTimeout(pinTimer);
        pinValue.textContent = "";
        pinMeta.textContent = "";
        copyStatus.textContent = "";
        pinNotice.hidden = true;
    }

    function showPin({ session_id, pin, expires_at }) {
        const remaining = Date.parse(expires_at) - Date.now();
        if (!(remaining > 0)) return;
        pinValue.textContent = pin;
        pinMeta.textContent = `Session #${session_id} · Expires ${new Date(expires_at).toLocaleString()}`;
        pinNotice.hidden = false;
        pinTimer = setTimeout(clearPin, remaining);
    }

    document.getElementById("copy-pin")?.addEventListener("click", async () => {
        if (!pinValue.textContent) return;
        try {
            await navigator.clipboard.writeText(pinValue.textContent);
            copyStatus.textContent = "PIN copied.";
        } catch {
            copyStatus.textContent = "Clipboard unavailable. Select and copy the PIN manually.";
        }
    });

    function updateCsrf(token) {
        document.querySelectorAll('input[name="csrf"]').forEach(input => { input.value = token; });
    }

    async function refreshTable() {
        const response = await fetch(location.pathname, {
            credentials: "same-origin", redirect: "error", signal: AbortSignal.timeout(15000),
        });
        if (!response.ok) throw new Error("Table refresh failed");
        const page = new DOMParser().parseFromString(await response.text(), "text/html");
        const table = page.getElementById("management-table");
        if (!table) throw new Error("Table unavailable");
        document.getElementById("management-table").replaceWith(table);
    }

    async function submitAction(form) {
        const action = form.getAttribute("action");
        pending = true;
        clearPin();
        const body = new URLSearchParams(new FormData(form));
        if (body.get("action") === "regenerate") body.set("confirm", "yes");
        const buttons = [...management.querySelectorAll('button[type="submit"]')];
        buttons.forEach(button => { button.disabled = true; });
        showStatus("Saving…");
        try {
            const response = await fetch(action, {
                method: "POST", body, credentials: "same-origin", redirect: "error",
                headers: { Accept: "application/json" }, signal: AbortSignal.timeout(15000),
            });
            const result = response.headers.get("Content-Type")?.startsWith("application/json")
                ? await response.json() : {};
            if (result.csrf) updateCsrf(result.csrf);
            if (!response.ok) {
                showStatus(result.message || `Request rejected (${response.status}). Reload before retrying.`, true);
                return;
            }
            if (result.pin) showPin(result.pin);
            showStatus(result.message);
            try {
                await refreshTable();
                if (result.csrf) updateCsrf(result.csrf);
            } catch {
                showStatus(result.message + " The table could not refresh. Reload when ready.", true);
            }
        } catch {
            showStatus("The result could not be confirmed. Reload to check the current state before retrying.", true);
        } finally {
            buttons.forEach(button => { button.disabled = false; });
            pending = false;
        }
    }

    window.addEventListener("pagehide", clearPin);
    management.addEventListener("submit", event => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) ||
            form.getAttribute("action") !== "/actions" + location.pathname) return;
        event.preventDefault();
        if (pending || dialog.open) return;
        const title = form.dataset.confirmTitle;
        if (!title) {
            submitAction(form);
            return;
        }
        confirmationForm = form;
        document.getElementById("confirm-title").textContent = title;
        document.getElementById("confirm-detail").textContent = form.dataset.confirmDetail;
        document.getElementById("confirm-button").textContent = title;
        dialog.returnValue = "";
        dialog.showModal();
    });
    dialog.addEventListener("close", () => {
        const form = confirmationForm;
        confirmationForm = null;
        if (dialog.returnValue === "confirm" && form && !pending) submitAction(form);
    });
}
