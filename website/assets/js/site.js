(() => {
  const menuButton = document.querySelector("[data-menu-button]");
  const navigation = document.querySelector("[data-navigation]");

  if (menuButton && navigation) {
    const closeMenu = () => {
      navigation.dataset.open = "false";
      menuButton.setAttribute("aria-expanded", "false");
    };

    menuButton.addEventListener("click", () => {
      const open = navigation.dataset.open !== "true";
      navigation.dataset.open = String(open);
      menuButton.setAttribute("aria-expanded", String(open));
    });

    navigation.addEventListener("click", (event) => {
      if (event.target.closest("a")) closeMenu();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeMenu();
    });
  }

  const dialog = document.querySelector("[data-lightbox]");
  const lightboxImage = dialog?.querySelector("[data-lightbox-image]");
  const lightboxCaption = dialog?.querySelector("[data-lightbox-caption]");
  const closeButton = dialog?.querySelector("[data-lightbox-close]");
  let opener = null;

  if (dialog && lightboxImage && lightboxCaption && closeButton) {
    document.querySelectorAll("[data-gallery-image]").forEach((button) => {
      button.addEventListener("click", () => {
        const image = button.querySelector("img");
        if (!image) return;
        opener = button;
        lightboxImage.src = image.src;
        lightboxImage.alt = image.alt;
        lightboxCaption.textContent = button.dataset.caption || image.alt;
        dialog.showModal();
      });
    });

    const closeDialog = () => dialog.close();
    closeButton.addEventListener("click", closeDialog);
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) closeDialog();
    });
    dialog.addEventListener("close", () => {
      lightboxImage.removeAttribute("src");
      opener?.focus();
    });
  }
})();
