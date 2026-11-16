"use strict";

(() => {
  let modo = "nova";
  try { const g = localStorage.getItem("aranduBIS.interface"); if (g === "nova" || g === "classica") modo = g; } catch (e) {  }
  document.documentElement.dataset.interface = modo;
})();
