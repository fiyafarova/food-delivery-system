(() => {
    const root = document.querySelector("[data-order-tracking]");
    if (!root) return;
    const status = root.querySelector("[data-tracking-label]");
    const description = root.querySelector("[data-tracking-description]");
    const courier = root.querySelector("[data-tracking-courier]");
    const error = root.querySelector("[data-tracking-error]");
    let terminal = root.dataset.terminal === "true";
    let timer;
    let pending = false;

    function render(state) {
        if (status) status.textContent = state.label;
        if (description) description.textContent = state.description;
        if (courier) {
            courier.textContent = state.courier;
            courier.parentElement.hidden = !state.courier;
        }
        const steps = root.querySelectorAll("[data-tracking-step]");
        for (const [index, step] of Array.from(steps).entries()) {
            step.classList.toggle("is-done", state.steps[index].done);
            step.classList.toggle("is-current", state.steps[index].current);
            if (state.steps[index].current) step.setAttribute("aria-current", "step");
            else step.removeAttribute("aria-current");
        }
        const cancel = root.querySelector("[data-tracking-cancel]");
        if (cancel) cancel.hidden = !state.can_cancel;
        terminal = state.terminal;
        if (terminal && root.dataset.widget === "true") root.hidden = true;
    }

    async function refresh() {
        if (document.hidden || pending || terminal) return;
        pending = true;
        try {
            const response = await fetch(root.dataset.trackingUrl, {
                headers: {"Accept": "application/json"},
                cache: "no-store"
            });
            if (response.status === 403 || response.status === 404 || response.redirected) {
                terminal = true;
                if (root.dataset.widget === "true") root.hidden = true;
                throw new Error("access");
            }
            if (!response.ok) throw new Error("request");
            render(await response.json());
            if (error) error.hidden = true;
        } catch {
            if (error) error.hidden = false;
        } finally {
            pending = false;
            if (!terminal && !document.hidden) timer = window.setTimeout(refresh, 10000);
        }
    }

    document.addEventListener("visibilitychange", () => {
        window.clearTimeout(timer);
        if (!document.hidden && !pending) refresh();
    });
    window.addEventListener("pagehide", () => window.clearTimeout(timer));
    if (!terminal) refresh();
})();
