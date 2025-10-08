// Используем событие 'load', чтобы гарантировать, что все библиотеки (GLightbox, Alpine, etc.) уже загружены и выполнены
window.addEventListener("load", () => {

  // Функция для инициализации GLightbox
  function initLightbox() {
    // Проверяем, существует ли функция GLightbox, прежде чем ее вызвать. Это делает код более надежным.
    if (typeof GLightbox === 'function') {
      const lightbox = GLightbox({
        selector: '.lightbox',
        touchNavigation: true,
        loop: true,
        zoomable: true,
        draggable: true,
      });
    } else {
      // Это сообщение появится в консоли, если GLightbox по какой-то причине не загрузился
      console.error("Библиотека GLightbox не загружена.");
    }
  }

  // === НАЧАЛЬНЫЙ ЗАПУСК ПРИ ЗАГРУЗКЕ СТРАНИЦЫ ===
  // Вызываем функцию один раз, чтобы обработать изображения, которые уже есть на странице
  initLightbox();

  // === ОБРАБОТЧИКИ СОБЫТИЙ ===

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
    // 1. ПОВТОРНАЯ ИНИЦИАЛИЗАЦИЯ GLightbox после того, как HTMX добавил новый контент (модальное окно)
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
          document.body.classList.remove('body-no-scroll');
        }
      }, 3000);
    }
  });

  // Слушатель для возврата скролла при закрытии модалки (крестиком или кликом по фону)
  document.body.addEventListener('htmx:beforeCleanupElement', function(event) {
    if (event.detail.elt.classList.contains('modal-overlay')) {
      document.body.classList.remove('body-no-scroll');
    }
  });

});