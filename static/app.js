(() => {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const body = document.body;

    const themeBtn = document.getElementById("themeBtn");
    const menuBtn = document.getElementById("menuBtn");
    const sidebar = document.getElementById("sidebar");

    // =========================
    // THEME (Clean SaaS) - body.light
    // =========================
    const applyTheme = (mode) => {
      const isLight = mode === "light";
      body.classList.toggle("light", isLight);

      if (themeBtn) {
        themeBtn.textContent = isLight ? "🌙 Dark" : "☀️ Light";
      }

      localStorage.setItem("theme", mode);
    };

    const savedTheme = localStorage.getItem("theme");
    applyTheme(savedTheme === "light" ? "light" : "dark");

    themeBtn?.addEventListener("click", () => {
      const isLight = body.classList.contains("light");
      applyTheme(isLight ? "dark" : "light");
    });

    // =========================
    // MENU (Sidebar)
    // =========================
    menuBtn?.addEventListener("click", (e) => {
      e.stopPropagation(); // ajuda a não fechar imediatamente no listener global
      sidebar?.classList.toggle("open");
    });

    // fecha sidebar ao clicar fora (mobile)
    document.addEventListener("click", (e) => {
      if (!sidebar || !sidebar.classList.contains("open")) return;
      const target = e.target;
      const clickedInsideSidebar = sidebar.contains(target);
      const clickedMenuBtn = menuBtn ? menuBtn.contains(target) : false;

      if (!clickedInsideSidebar && !clickedMenuBtn) {
        sidebar.classList.remove("open");
      }
    });

    // =========================
    // FORMS: valida required + evita clique duplo
    // =========================
    document.querySelectorAll("form").forEach((form) => {
      form.addEventListener("submit", (e) => {
        // 1) valida required primeiro
        const required = form.querySelectorAll("[required]");
        for (const field of required) {
          const val = (field.value || "").trim();
          if (!val) {
            e.preventDefault();
            alert("Preencha todos os campos obrigatórios.");
            return; // importante: não desabilita botões se falhar
          }
        }

        // 2) passou na validação: desabilita botões para evitar duplo clique
        const buttons = form.querySelectorAll("button, input[type='submit']");
        buttons.forEach((btn) => {
          const isButton = btn.tagName.toLowerCase() === "button";

          // guarda texto original (se precisar reverter)
          btn.dataset.originalText = isButton ? (btn.innerText || "") : (btn.value || "");

          btn.disabled = true;

          if (isButton) {
            btn.innerText = "Salvando...";
          } else {
            btn.value = "Salvando...";
          }
        });
      });
    });

    // =========================
    // Toast/Flash: fechar + auto-sumir
    // =========================
    document.querySelectorAll(".alert").forEach((a) => {
      const closeBtn = a.querySelector(".alert-close");
      const close = () => {
        a.classList.add("hide");
        setTimeout(() => a.remove(), 220);
      };

      closeBtn?.addEventListener("click", close);

      if (a.dataset.autohide === "true") {
        setTimeout(close, 3500);
      }
    });

    // =========================
    // Busca instantânea - pedidos
    // =========================
    const input = document.getElementById("pedidoSearch");
    const count = document.getElementById("pedidoCount");
    const rows = Array.from(document.querySelectorAll("tr.pedido-row"));

    if (input && count && rows.length > 0) {
      const total = rows.length;

      const applyFilter = () => {
        const q = (input.value || "").trim().toLowerCase();
        let visible = 0;

        rows.forEach((row) => {
          const hay = (row.dataset.search || "").toLowerCase();
          const match = hay.includes(q);
          row.style.display = match ? "" : "none";
          if (match) visible += 1;
        });

        count.textContent = `${visible} de ${total} pedido(s)`;
      };

      input.addEventListener("input", applyFilter);

      input.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          input.value = "";
          applyFilter();
        }
      });
    }
  });
})()
