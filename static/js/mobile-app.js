(() => {
  const MOBILE_QUERY = "(max-width: 768px)";

  function setupMobileNavigation() {
    const tabs = document.querySelector(".tabs");
    if (!tabs || tabs.dataset.mobileNavReady === "true") return;

    const getOriginalTab = (name) =>
      tabs.querySelector(`.tab[onclick*="'${name}'"]`);

    const accountsTab = getOriginalTab("accounts");
    const subusersTab = getOriginalTab("subusers");
    const mainTabs = ["dashboard", "search", "inbox", "events"]
      .map(getOriginalTab)
      .filter(Boolean);

    const moreButton = document.createElement("button");
    moreButton.type = "button";
    moreButton.className = "mobile-nav-more";
    moreButton.setAttribute("aria-label", "Mostrar mas secciones");
    moreButton.setAttribute("aria-expanded", "false");
    moreButton.textContent = "Más";

    const backdrop = document.createElement("div");
    backdrop.className = "mobile-more-backdrop";

    const menu = document.createElement("div");
    menu.className = "mobile-more-menu";
    menu.setAttribute("role", "dialog");
    menu.setAttribute("aria-label", "Mas secciones");
    menu.innerHTML = '<div class="mobile-more-title">Más secciones</div>';

    function closeMenu() {
      menu.classList.remove("open");
      backdrop.classList.remove("open");
      moreButton.setAttribute("aria-expanded", "false");
    }

    function setMoreActive(active) {
      moreButton.classList.toggle("active", active);
    }

    function addMenuItem(name, label, originalTab, belongsToMore = false) {
      if (!originalTab || originalTab.style.display === "none") return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "mobile-more-item";
      button.dataset.tab = name;
      button.textContent = label;
      button.addEventListener("click", () => {
        if (typeof window.switchTab === "function") window.switchTab(name);
        setMoreActive(belongsToMore);
        closeMenu();
      });
      menu.appendChild(button);
    }

    addMenuItem("dashboard", "Dashboard", getOriginalTab("dashboard"));
    addMenuItem("search", "Buscar código", getOriginalTab("search"));
    addMenuItem("inbox", "Bandeja", getOriginalTab("inbox"));
    addMenuItem("accounts", "Cuentas", accountsTab, true);
    addMenuItem("events", "Eventos", getOriginalTab("events"));
    addMenuItem("subusers", "Sub-usuarios", subusersTab, true);

    moreButton.addEventListener("click", () => {
      const open = !menu.classList.contains("open");
      menu.classList.toggle("open", open);
      backdrop.classList.toggle("open", open);
      moreButton.setAttribute("aria-expanded", String(open));
    });

    mainTabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        setMoreActive(false);
        closeMenu();
      });
    });

    backdrop.addEventListener("click", closeMenu);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeMenu();
    });

    tabs.appendChild(moreButton);
    document.body.append(backdrop, menu);
    tabs.dataset.mobileNavReady = "true";

    const syncViewport = () => {
      const mobile = window.matchMedia(MOBILE_QUERY).matches;
      moreButton.hidden = !mobile;
      if (!mobile) closeMenu();
    };
    window.matchMedia(MOBILE_QUERY).addEventListener("change", syncViewport);
    syncViewport();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupMobileNavigation, { once: true });
  } else {
    setupMobileNavigation();
  }
})();
