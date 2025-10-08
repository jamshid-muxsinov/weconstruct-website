console.log("ШАГ 3: Запускаем тест GLightbox.");

window.addEventListener('load', () => {
  console.log("ШАГ 3: Событие 'load' сработало.");
  
  try {
    if (typeof GLightbox === 'function') {
      console.log("ШАГ 3: Функция GLightbox НАЙДЕНА. Попытка инициализации...");
      GLightbox({ selector: '.lightbox' });
      console.log("ШАГ 3: GLightbox УСПЕШНО инициализирован!");
    } else {
      console.error("ШАГ 3: КРИТИЧЕСКАЯ ОШИБКА! Функция GLightbox НЕ НАЙДЕНА!");
    }
  } catch (e) {
    console.error("ШАГ 3: КРИТИЧЕСКАЯ ОШИБКА! Произошла ошибка при вызове GLightbox:", e);
  }
});