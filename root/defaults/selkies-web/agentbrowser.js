(function () {
  "use strict";

  var REPO = "https://github.com/aitorroma/agentbrowser";

  var HIDE_ICON =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" width="18" height="18">' +
    '<polyline points="15 18 9 12 15 6"></polyline>' +
    '<line x1="4" y1="5" x2="4" y2="19"></line></svg>';

  function brand() {
    if (document.title !== "AgentBrowser") document.title = "AgentBrowser";

    var header = document.querySelector(".sidebar-header");
    if (!header) return;

    // 1. Point the brand links at the AgentBrowser repository.
    header.querySelectorAll("a").forEach(function (a) {
      if (a.getAttribute("href") !== REPO) {
        a.setAttribute("href", REPO);
        a.setAttribute("target", "_blank");
        a.setAttribute("rel", "noopener noreferrer");
        a.setAttribute("title", "AgentBrowser · GitHub");
      }
    });

    // 2. Replace the "Selkies" wordmark with "AgentBrowser" (CSS also covers the
    //    visual, this keeps the accessible name correct).
    var h2 = header.querySelector("h2");
    if (h2) {
      if (h2.textContent.trim() !== "AgentBrowser") h2.textContent = "AgentBrowser";
      h2.setAttribute("aria-label", "AgentBrowser");
    }

    var controls = header.querySelector(".header-controls");
    if (!controls) return;

    // 3. Make sure the native fullscreen button is present and labelled.
    var fs = controls.querySelector(".fullscreen-button");
    if (fs && !fs.getAttribute("title")) fs.setAttribute("title", "Pantalla completa");

    // 4. Add a "hide panel" button that collapses the dashboard sidebar.
    if (!controls.querySelector(".ab-hide-button")) {
      var hide = document.createElement("button");
      hide.type = "button";
      hide.className = "header-action-button ab-hide-button";
      hide.title = "Ocultar panel";
      hide.setAttribute("aria-label", "Ocultar panel");
      hide.innerHTML = HIDE_ICON;
      hide.addEventListener("click", function (e) {
        e.preventDefault();
        var handle = document.querySelector(".toggle-handle");
        if (handle) handle.click();
      });
      controls.appendChild(hide);
    }
  }

  function run() {
    try {
      brand();
    } catch (e) {
      /* never break the app over branding */
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }

  // The Selkies UI re-renders its header; re-apply branding whenever it does.
  var observer = new MutationObserver(run);
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
