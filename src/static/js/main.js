// src/js/main.js

document.addEventListener("DOMContentLoaded", () => {
  // Плавный скролл по якорям
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      e.preventDefault();
      const targetId = this.getAttribute("href");
      const targetElement = document.querySelector(targetId);
      
      if (targetElement) {
        targetElement.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }
    });
  });

  // Глобальный обработчик событий HTMX
  document.body.addEventListener('htmx:afterSwap', function(event) {
    // 1. Инициализация GLightbox после загрузки модального окна
    initLightbox();

    // 2. Логика закрытия модалки после успешной отправки формы
    const target = event.detail.target;
    if (target.querySelector('.quote-success')) {
      setTimeout(() => {
        const modal = document.querySelector('.modal-overlay');
        if (modal) {
          modal.remove();
        }
      }, 3000);
    }
  });
});

// Функция для инициализации GLightbox
function initLightbox() {
  const lightbox = GLightbox({
    selector: '.lightbox', // Ищем все ссылки с этим классом
    touchNavigation: true,
    loop: true,
    zoomable: true,
    draggable: true,
  });
}