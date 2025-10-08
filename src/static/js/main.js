window.addEventListener("load", () => {
  console.log("[OK] Событие 'load' сработало. Начинаем настройку.");

  // Функция для инициализации GLightbox
  function initLightbox() {
    try {
      if (typeof GLightbox === 'function') {
        console.log("  [INFO] Функция GLightbox найдена. Выполняется инициализация...");
        GLightbox({ selector: '.lightbox' });
        console.log("  [OK] GLightbox успешно инициализирован.");
      } else {
        console.error("  [ОШИБКА] GLightbox не определен!");
      }
    } catch (e) {
      console.error("  [ОШИБКА] Произошла ошибка при инициализации GLightbox:", e);
    }
  }

  // Первоначальный запуск для контента, который уже есть на странице
  console.log("[INFO] Выполняется первоначальная инициализация Lightbox...");
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
    console.log("[OK] Плавный скролл по якорям настроен.");
  } catch(e) {
    console.error("[ОШИБКА] Не удалось настроить плавный скролл:", e);
  }

  // Глобальный обработчик событий HTMX
  document.body.addEventListener('htmx:afterSwap', function(event) {
    console.log("%c[HTMX] Событие 'htmx:afterSwap' перехвачено.", "color: #8B5CF6; font-weight: bold;");

    console.log("  [HTMX INFO] Повторная инициализация Lightbox...");
    initLightbox();

    try {
      console.log("  [HTMX INFO] Проверка наличия .modal-overlay...");
      const modalOverlay = event.detail.target.querySelector('.modal-overlay');
      if (modalOverlay) {
        console.log("    [HTMX OK] .modal-overlay найден. Блокируем скролл.");
        document.body.classList.add('body-no-scroll');
      } else {
        console.log("    [HTMX INFO] .modal-overlay не найден в загруженном фрагменте.");
      }
    } catch (e) {
      console.error("  [HTMX ОШИБКА] Ошибка при блокировке скролла:", e);
    }

    try {
      console.log("  [HTMX INFO] Проверка наличия .quote-success...");
      const quoteSuccess = event.detail.target.querySelector('.quote-success');
      if (quoteSuccess) {
        console.log("    [HTMX OK] .quote-success найден. Запускаем таймер на закрытие модального окна.");
        setTimeout(() => {
          console.log("      [HTMX TIMER] Таймер сработал. Ищем .modal-overlay для закрытия...");
          const modal = document.querySelector('.modal-overlay');
          if (modal) {
            console.log("        [HTMX TIMER OK] Модальное окно найдено. Удаляем.");
            modal.remove();
            document.body.classList.remove('body-no-scroll');
          } else {
            console.warn("        [HTMX TIMER ПРЕДУПРЕЖДЕНИЕ] Модальное окно для закрытия не найдено.");
          }
        }, 3000);
      } else {
        console.log("    [HTMX INFO] .quote-success не найден.");
      }
    } catch(e) {
      console.error("  [HTMX ОШИБКА] Ошибка при настройке таймера:", e);
    }
  });
  console.log("[OK] Обработчик 'htmx:afterSwap' настроен.");


  document.body.addEventListener('htmx:beforeCleanupElement', function(event) {
    console.log("%c[HTMX] Событие 'htmx:beforeCleanupElement' перехвачено.", "color: #F59E0B;");
    try {
      if (event.detail.elt.classList.contains('modal-overlay')) {
        console.log("  [HTMX OK] Удаляется .modal-overlay. Разблокируем скролл.");
        document.body.classList.remove('body-no-scroll');
      }
    } catch(e) {
      console.error("  [HTMX ОШИБКА] Ошибка при разблокировке скролла:", e);
    }
  });
  console.log("[OK] Обработчик 'htmx:beforeCleanupElement' настроен.");

});