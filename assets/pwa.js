(function () {
  if (!("serviceWorker" in navigator)) return;
  var base = window.SPINOZA_BASE_PATH || "";
  window.addEventListener("load", function () {
    navigator.serviceWorker.register(base + "/sw.js").catch(function () {});
  });
})();
