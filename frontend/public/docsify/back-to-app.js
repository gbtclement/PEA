// Plugin Docsify commun : lien de retour vers l'application en haut de la barre latérale
(function () {
  window.$docsify = window.$docsify || {};
  window.$docsify.plugins = (window.$docsify.plugins || []).concat(function (hook) {
    hook.doneEach(function () {
      var sidebar = document.querySelector(".sidebar-nav");
      if (sidebar && !sidebar.querySelector(".back-to-app")) {
        var link = document.createElement("a");
        link.className = "back-to-app";
        link.href = "/";
        link.textContent = "← Retour à l'application";
        sidebar.prepend(link);
      }
    });
  });
})();
