window.addEventListener("load", () => {
  // Функция для инициализации GLightbox
  function initLightbox() {
    try {
      if (typeof GLightbox === 'function') {
        GLightbox({ selector: '.lightbox' });
      } else {
        console.error("  [ОШИБКА] GLightbox не определен!");
      }
    } catch (e) {
      console.error("  [ОШИБКА] Произошла ошибка при инициализации GLightbox:", e);
    }
  }

  // Первоначальный запуск для контента, который уже есть на странице
  initLightbox();

  // Плавный скролл по якорям
  try {
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
      anchor.addEventListener("click", function (e) {
        e.preventDefault();
        const targetElement = document.querySelector(this.getAttribute("href"));
        if (targetElement) {
          targetElement.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });
  } catch(e) {
    console.error("[ОШИБКА] Не удалось настроить плавный скролл:", e);
  }

  // Глобальный обработчик событий HTMX
  document.body.addEventListener('htmx:afterSwap', function(event) {
    initLightbox();

    try {
      const modalOverlay = event.detail.target.querySelector('.modal-overlay');
      if (modalOverlay) {
        document.body.classList.add('body-no-scroll');
      }
    } catch (e) {
      console.error("  [HTMX ОШИБКА] Ошибка при блокировке скролла:", e);
    }

    try {
      const quoteSuccess = event.detail.target.querySelector('.quote-success');
      if (quoteSuccess) {
        setTimeout(() => {
          const modal = document.querySelector('.modal-overlay');
          if (modal) {
            modal.remove();
            document.body.classList.remove('body-no-scroll');
          } else {
            console.warn("        [HTMX TIMER ПРЕДУПРЕЖДЕНИЕ] Модальное окно для закрытия не найдено.");
          }
        }, 3000);
      }
    } catch(e) {
      console.error("  [HTMX ОШИБКА] Ошибка при настройке таймера:", e);
    }
  });

  document.body.addEventListener('htmx:beforeCleanupElement', function(event) {
    try {
      if (event.detail.elt.classList.contains('modal-overlay')) {
        document.body.classList.remove('body-no-scroll');
      }
    } catch(e) {
      console.error("  [HTMX ОШИБКА] Ошибка при разблокировке скролла:", e);
    }
  });

});