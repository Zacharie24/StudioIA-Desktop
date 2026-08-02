// Injecté par le shell (main.rs) quand le backend dépasse le délai de démarrage.
// Transforme le splash local en message d'erreur sans quitter le domaine local.
(function () {
  var b = document.querySelector(".box");
  if (!b) { document.body.innerHTML = ""; b = document.createElement("div"); b.className = "box"; document.body.appendChild(b); }
  b.innerHTML = [
    '<div style="text-align:center;color:#fff;font-family:Segoe UI,system-ui,sans-serif;">',
    '  <div style="font-size:22px;font-weight:700;">Le service StudioIA n\'a pas démarré</div>',
    '  <div style="margin-top:12px;font-size:14px;opacity:.85;line-height:1.6;">Le backend n\'a pas répondu dans le délai imparti.<br>',
    '  Vérifiez que rien ne bloque le port 8080, puis relancez l\'application.</div>',
    '  <button onclick="location.reload()" style="margin-top:22px;padding:10px 24px;background:#4f7cff;color:#fff;border:0;border-radius:8px;font-size:14px;cursor:pointer;">Réessayer</button>',
    '</div>'
  ].join("");
})();