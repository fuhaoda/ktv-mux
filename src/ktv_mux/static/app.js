(function () {
  document.querySelectorAll("[data-sync-target]").forEach(function (slider) {
    var target = document.querySelector(slider.getAttribute("data-sync-target"));
    if (!target) return;
    slider.addEventListener("input", function () {
      target.value = slider.value;
    });
    target.addEventListener("input", function () {
      slider.value = target.value || 0;
    });
  });

  document.querySelectorAll("[data-draft-key]").forEach(function (field) {
    var key = "ktv-draft:" + field.getAttribute("data-draft-key");
    var saved = window.localStorage.getItem(key);
    if (saved && !field.value.trim()) field.value = saved;
    field.addEventListener("input", function () {
      window.localStorage.setItem(key, field.value);
    });
    if (field.form) {
      field.form.addEventListener("submit", function () {
        window.localStorage.removeItem(key);
      });
    }
  });
})();
