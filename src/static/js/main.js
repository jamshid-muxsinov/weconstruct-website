document.addEventListener("DOMContentLoaded", () => {
  const heroSection = document.querySelector('.hero');
  if (heroSection) {
    const skipAnimation = () => {
      document.body.classList.add('animation-skipped');
      // Удаляем обработчики после первого срабатывания для оптимизации
      window.removeEventListener('scroll', skipAnimation);
      window.removeEventListener('mousemove', skipAnimation);
    };

    window.addEventListener('scroll', skipAnimation, { once: true });
    window.addEventListener('mousemove', skipAnimation, { once: true });
  }
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
    // Эта функция найдет все ссылки с классом .lightbox и объединит их в галерею
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
    selector: '.lightbox',
    touchNavigation: true,
    loop: true,
    zoomable: true,
    draggable: true,
  });
}