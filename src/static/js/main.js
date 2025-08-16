document.addEventListener("alpine:init", () => {
  Alpine.data("stats", () => ({
    projects: 0,
    days: 0,
    clients: 0,
    warranty: 0,
    animateCounter(ref, target, suffix = '') {
      const el = this.$refs[ref];
      if (!el) return;
      
      let start = 0;
      const duration = 2000;
      const frameDuration = 1000 / 60;
      const totalFrames = Math.round(duration / frameDuration);
      let frame = 0;

      const counter = setInterval(() => {
        frame++;
        const progress = frame / totalFrames;
        const current = Math.round(target * progress);
        
        el.innerText = current + suffix;

        if (frame === totalFrames) {
          clearInterval(counter);
          el.innerText = target + suffix; // Убедимся, что в конце точное значение
        }
      }, frameDuration);
    }
  }));
});

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

  // Автоматическое закрытие модального окна после успеха
  document.body.addEventListener('htmx:afterSwap', function(event) {
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