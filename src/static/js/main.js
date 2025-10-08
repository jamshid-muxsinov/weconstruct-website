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

    // 2. Блокируем скролл фона, если появился оверлей
    if (event.detail.target.querySelector('.modal-overlay')) {
      document.body.classList.add('body-no-scroll');
    }

    // 3. Логика закрытия модалки после успешной отправки формы
    if (event.detail.target.querySelector('.quote-success')) {
      setTimeout(() => {
        const modal = document.querySelector('.modal-overlay');
        if (modal) {
          modal.remove();
          // При удалении модалки, возвращаем скролл
          document.body.classList.remove('body-no-scroll');
        }
      }, 3000);
    }
  });

  // Добавляем слушатель на удаление модалки для возврата скролла
  // (на случай, если пользователь закроет ее крестиком или кликом по фону)
  document.body.addEventListener('htmx:beforeCleanupElement', function(event) {
    if (event.detail.elt.classList.contains('modal-overlay')) {
      document.body.classList.remove('body-no-scroll');
    }
  });
});

// Функция для инициализации GLightbox
function initLightbox() {
  const lightbox = GLightbox({
    selector: '.lightbox',
    touchNavigation: true,
    loop: true,
    zoomable: true,
    draggable: true,
  });
}