(function () {
  const loadingSelector = [
    "button[hx-get]",
    "button[hx-post]",
    "button[hx-put]",
    "button[hx-delete]",
    "a.btn[hx-get]",
    "a.btn[hx-post]",
    "a.btn[hx-put]",
    "a.btn[hx-delete]",
    "form button[type='submit']",
    "form .btn[type='submit']",
    "form input[type='submit']",
    "a.btn[href]:not([href^='#']):not([data-bs-toggle])"
  ].join(",");

  function isRequestForm(form) {
    return Boolean(
      form &&
        form.matches(
          "form[action], form[hx-get], form[hx-post], form[hx-put], form[hx-delete]"
        )
    );
  }

  function findButton(source) {
    if (!source) return null;
    if (source.matches && source.matches(".btn, button, input[type='submit']")) return source;
    if (source.matches && source.matches("form")) {
      const active = source.ownerDocument.activeElement;
      if (active && source.contains(active) && active.matches(".btn, button, input[type='submit']")) {
        return active;
      }
      return source.querySelector("button[type='submit'], .btn[type='submit'], input[type='submit']");
    }
    return source.closest ? source.closest(".btn, button, input[type='submit']") : null;
  }

  function loadingText(button) {
    if (!button) return "Loading";
    return (
      button.getAttribute("data-loading-text") ||
      button.getAttribute("aria-label") ||
      button.textContent.trim() ||
      "Loading"
    );
  }

  function setLoading(button) {
    if (!button || button.dataset.adminLoading === "true") return;
    button.dataset.adminLoading = "true";
    button.dataset.adminOriginalHtml = button.innerHTML;
    button.dataset.adminOriginalWidth = button.style.width || "";
    if (button.offsetWidth) button.style.width = `${button.offsetWidth}px`;
    button.setAttribute("aria-busy", "true");
    if (button.tagName === "BUTTON" || button.tagName === "INPUT") button.disabled = true;
    if (button.tagName === "A") {
      button.classList.add("disabled");
      button.setAttribute("aria-disabled", "true");
    }
    button.classList.add("admin-request-loading");
    if (button.tagName === "INPUT") {
      button.dataset.adminOriginalValue = button.value;
      button.value = loadingText(button);
      return;
    }
    button.innerHTML = `<span class="spinner-border spinner-border-sm me-2 admin-request-loader" role="status" aria-hidden="true"></span><span>${loadingText(button)}</span>`;
  }

  function clearLoading(button) {
    if (!button || button.dataset.adminLoading !== "true") return;
    if (button.tagName === "INPUT") {
      button.value = button.dataset.adminOriginalValue || button.value;
    } else {
      button.innerHTML = button.dataset.adminOriginalHtml || button.innerHTML;
    }
    button.style.width = button.dataset.adminOriginalWidth || "";
    button.removeAttribute("aria-busy");
    button.classList.remove("admin-request-loading", "disabled");
    button.removeAttribute("aria-disabled");
    if (button.tagName === "BUTTON" || button.tagName === "INPUT") button.disabled = false;
    delete button.dataset.adminLoading;
    delete button.dataset.adminOriginalHtml;
    delete button.dataset.adminOriginalWidth;
    delete button.dataset.adminOriginalValue;
  }

  function scheduleToastDismiss(toast) {
    const duration = Number(toast.getAttribute("data-duration") || "0");
    if (!duration || toast.dataset.adminToastReady === "true") return;
    toast.dataset.adminToastReady = "true";
    window.setTimeout(() => {
      toast.classList.add("admin-modern-toast-leaving");
      window.setTimeout(() => toast.remove(), 220);
    }, duration);
  }

  function hydrateToasts(root) {
    (root || document).querySelectorAll("[data-fs-modern-toast]").forEach(scheduleToastDismiss);
  }

  const tableMedia = window.matchMedia("(min-width: 992px)");

  function syncResponsiveTablesA11y(root) {
    const scope = root || document;
    const desktopVisible = tableMedia.matches;
    scope.querySelectorAll(".admin-responsive-table-desktop").forEach((node) => {
      node.setAttribute("aria-hidden", desktopVisible ? "false" : "true");
    });
    scope.querySelectorAll(".admin-responsive-table-mobile").forEach((node) => {
      node.setAttribute("aria-hidden", desktopVisible ? "true" : "false");
    });
  }

  document.addEventListener(
    "click",
    (event) => {
      const trigger = event.target.closest(loadingSelector);
      if (!trigger) return;
      const form = trigger.form || trigger.closest("form");
      if (form && form.matches("[hx-get], [hx-post], [hx-put], [hx-delete]")) return;
      if (trigger.matches("[hx-get], [hx-post], [hx-put], [hx-delete]")) return;
      window.setTimeout(() => setLoading(trigger), 0);
    },
    true
  );

  document.addEventListener(
    "submit",
    (event) => {
      if (!isRequestForm(event.target)) return;
      if (event.target.matches("[hx-get], [hx-post], [hx-put], [hx-delete]")) return;
      const button = findButton(event.submitter || event.target);
      window.setTimeout(() => setLoading(button), 0);
    },
    true
  );

  /* ── Top Page Process Loader ────────────────────────────────────────── */
  function getLoadingBar() {
    return document.getElementById("admin-loading-bar");
  }

  function startTopLoader() {
    const bar = getLoadingBar();
    if (!bar) return;
    bar.classList.add("is-loading");
    bar.classList.remove("is-settling");
  }

  function stopTopLoader() {
    const bar = getLoadingBar();
    if (!bar) return;
    bar.classList.remove("is-loading");
    bar.classList.add("is-settling");
    window.setTimeout(() => bar.classList.remove("is-settling"), 400);
  }

  /* ── Sidebar Link Tap / Feedback ─────────────────────────────────────── */
  function initSidebarFeedback() {
    document.addEventListener("click", (e) => {
      const link = e.target.closest(".sidebar-link, a.nav-link");
      if (!link) return;
      // Mark as navigating
      document.querySelectorAll(".sidebar-link.is-navigating").forEach((el) => el.classList.remove("is-navigating"));
      link.classList.add("is-navigating");
      startTopLoader();
    });
  }

  /* ── Instant Theme Toggle ───────────────────────────────────────────── */
  function initThemeToggle() {
    function applyTheme(theme) {
      document.documentElement.setAttribute("data-bs-theme", theme);
      document.body.setAttribute("data-bs-theme", theme);
      try {
        localStorage.setItem("dclm-admin-theme", theme);
        document.cookie = `theme=${theme}; path=/; max-age=31536000; samesite=lax`;
      } catch (err) {}
      document.querySelectorAll("#theme-toggle, input[role='switch'].fs-theme-toggle").forEach((sw) => {
        sw.checked = theme === "dark";
      });
    }

    // Initialize from cookie, localStorage, or system preference
    let saved = "light";
    try {
      const match = document.cookie.match(/theme=(dark|light)/);
      saved = match ? match[1] : (localStorage.getItem("dclm-admin-theme") || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
    } catch (err) {}
    applyTheme(saved);

    document.addEventListener("change", (e) => {
      const target = e.target;
      if (target && (target.id === "theme-toggle" || target.closest(".fs-theme-toggle") || target.name === "theme")) {
        const newTheme = target.checked ? "dark" : "light";
        applyTheme(newTheme);
      }
    });

    document.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-theme-toggle]");
      if (!btn) return;
      const current = document.documentElement.getAttribute("data-bs-theme") || "light";
      const nextTheme = current === "dark" ? "light" : "dark";
      applyTheme(nextTheme);
    });
  }

  /* ── PWA Install Prompt ─────────────────────────────────────────────── */
  let deferredPrompt = null;

  function initPwaInstall() {
    window.addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault();
      deferredPrompt = e;
      document.querySelectorAll("[data-install-trigger]").forEach((btn) => {
        btn.classList.remove("d-none");
      });
    });

    document.addEventListener("click", async (e) => {
      const trigger = e.target.closest("[data-install-trigger]");
      if (!trigger) return;
      e.preventDefault();
      if (deferredPrompt) {
        deferredPrompt.prompt();
        const choice = await deferredPrompt.userChoice.catch(() => null);
        if (choice && choice.outcome === "accepted") {
          document.querySelectorAll("[data-install-trigger]").forEach((btn) => btn.classList.add("d-none"));
        }
        deferredPrompt = null;
      } else {
        alert("To install DCLM Admin:\n• On Chrome/Edge: Click 'Install' in your browser address bar.\n• On iOS/Safari: Tap 'Share' and choose 'Add to Home Screen'.");
      }
    });
  }

  /* ── HTMX Event Wiring ──────────────────────────────────────────────── */
  document.body.addEventListener("htmx:beforeRequest", (event) => {
    setLoading(findButton(event.detail.elt));
    startTopLoader();
  });

  ["htmx:afterRequest", "htmx:responseError", "htmx:sendError", "htmx:timeout"].forEach((name) => {
    document.body.addEventListener(name, (event) => {
      clearLoading(findButton(event.detail.elt));
      stopTopLoader();
      document.querySelectorAll(".sidebar-link.is-navigating").forEach((el) => el.classList.remove("is-navigating"));
    });
  });

  document.body.addEventListener("htmx:oobAfterSwap", (event) => hydrateToasts(event.detail.elt));
  document.body.addEventListener("htmx:afterSettle", (event) => {
    const root = event.detail.elt || document;
    hydrateToasts(root);
    syncResponsiveTablesA11y(root);
    stopTopLoader();
  });

  tableMedia.addEventListener("change", () => syncResponsiveTablesA11y(document));

  function initAll() {
    hydrateToasts(document);
    syncResponsiveTablesA11y(document);
    initSidebarFeedback();
    initThemeToggle();
    initPwaInstall();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})();

