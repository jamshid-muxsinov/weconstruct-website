document.addEventListener("DOMContentLoaded", () => {
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