(function () {
  const root = document.documentElement;
  const storedTheme = window.localStorage.getItem("stemma-theme");
  if (storedTheme === "dark" || storedTheme === "light") {
    root.dataset.theme = storedTheme;
  }

  const themeToggle = document.querySelector("[data-theme-toggle]");
  const updateThemeLabel = () => {
    const isDark = root.dataset.theme === "dark";
    if (!themeToggle) return;
    themeToggle.setAttribute("aria-pressed", String(isDark));
    themeToggle.setAttribute("aria-label", `Přepnout na ${isDark ? "světlý" : "tmavý"} motiv`);
    themeToggle.textContent = isDark ? "Světlý motiv" : "Tmavý motiv";
  };
  updateThemeLabel();

  themeToggle?.addEventListener("click", () => {
    const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = nextTheme;
    window.localStorage.setItem("stemma-theme", nextTheme);
    updateThemeLabel();
  });

  const peoplePanel = document.querySelector("#people-panel");
  const listToggle = document.querySelector("[data-person-list-open]");
  const setListOpen = (isOpen) => {
    peoplePanel?.classList.toggle("is-open", isOpen);
    listToggle?.setAttribute("aria-expanded", String(isOpen));
  };
  setListOpen(peoplePanel?.classList.contains("is-open") ?? false);
  listToggle?.addEventListener("click", () => setListOpen(!peoplePanel?.classList.contains("is-open")));
  document.querySelector("[data-person-list-close]")?.addEventListener("click", () => setListOpen(false));

  const selectCurrentPerson = () => {
    document.querySelectorAll(".person-list-item").forEach((link) => {
      const isCurrent = new URL(link.href).pathname === window.location.pathname;
      link.classList.toggle("is-selected", isCurrent);
      if (isCurrent) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  };
  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail.target.id !== "person-detail") return;
    selectCurrentPerson();
    setListOpen(false);
    event.detail.target.querySelector("[data-form-error-summary]")?.focus();
  });
  const resetSubmitButton = (form) => {
    const button = form?.querySelector("[data-person-submit]");
    if (!button) return;
    button.textContent = button.dataset.idleLabel;
    button.disabled = false;
  };
  const showRequestError = (event) => {
    const detail = event.detail.target;
    if (!(detail instanceof Element) || detail.id !== "person-detail") return;
    const form = detail.querySelector("[data-person-form]");
    if (form) {
      form.dataset.dirty = "true";
      form.dataset.submitting = "false";
      resetSubmitButton(form);
      form.querySelector("[data-request-error]")?.remove();
      form.insertAdjacentHTML("afterbegin", '<div class="form-errors" role="alert" data-request-error><strong>Změny se nepodařilo uložit.</strong> Zadané hodnoty zůstaly zachovány. Zkuste akci zopakovat.</div>');
      return;
    }
    if (event.type === "htmx:responseError" && event.detail.xhr.status === 404) {
      detail.innerHTML = event.detail.xhr.responseText;
      return;
    }
    detail.innerHTML = '<div class="detail-empty" role="alert"><h2>Detail se nepodařilo načíst.</h2><p>Zkuste akci zopakovat.</p></div>';
  };
  document.body.addEventListener("htmx:responseError", showRequestError);
  document.body.addEventListener("htmx:sendError", showRequestError);

  const dirtyPersonForm = () => document.querySelector('[data-person-form][data-dirty="true"]');
  const blockingPersonForm = () => document.querySelector('[data-person-form][data-dirty="true"]:not([data-submitting="true"])');
  document.body.addEventListener("input", (event) => {
    event.target.closest?.("[data-person-form]")?.setAttribute("data-dirty", "true");
  });
  document.body.addEventListener("change", (event) => {
    event.target.closest?.("[data-person-form]")?.setAttribute("data-dirty", "true");
  });
  document.body.addEventListener("submit", (event) => {
    event.target.closest?.("[data-person-form]")?.setAttribute("data-submitting", "true");
  });
  document.body.addEventListener("htmx:beforeRequest", (event) => {
    const form = event.detail.elt.closest?.("[data-person-form]");
    const button = form?.querySelector("[data-person-submit]");
    if (button) button.textContent = button.dataset.loadingLabel;
  });
  const confirmDiscard = () => new Promise((resolve) => {
    const dialog = document.querySelector("#unsaved-dialog");
    if (
      typeof HTMLDialogElement === "undefined"
      || !(dialog instanceof HTMLDialogElement)
    ) {
      resolve(window.confirm("Máte neuložené změny. Chcete je zahodit?"));
      return;
    }
    const finish = () => resolve(dialog.returnValue === "discard");
    dialog.addEventListener("close", finish, { once: true });
    dialog.showModal();
  });
  document.body.addEventListener("htmx:confirm", (event) => {
    const form = dirtyPersonForm();
    if (!form || event.detail.elt === form) return;
    event.preventDefault();
    confirmDiscard().then((discard) => {
      if (!discard) return;
      form.dataset.dirty = "false";
      event.detail.issueRequest(true);
    });
  });
  window.addEventListener("stemma:confirm-history-discard", (event) => {
    confirmDiscard().then((discard) => {
      if (!discard) return;
      const form = dirtyPersonForm();
      if (form) form.dataset.dirty = "false";
      window.location.assign(event.detail.targetUrl);
    });
  });
  window.addEventListener("beforeunload", (event) => {
    if (!blockingPersonForm()) return;
    event.preventDefault();
    event.returnValue = "";
  });
}());
