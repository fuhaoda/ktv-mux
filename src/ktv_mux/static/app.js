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

  document.querySelectorAll(".drop-zone input[type=file]").forEach(function (input) {
    var zone = input.closest(".drop-zone");
    if (!zone) return;
    zone.addEventListener("dragover", function (event) {
      event.preventDefault();
      zone.classList.add("dragging");
    });
    zone.addEventListener("dragleave", function () {
      zone.classList.remove("dragging");
    });
    zone.addEventListener("drop", function (event) {
      event.preventDefault();
      zone.classList.remove("dragging");
      if (event.dataTransfer && event.dataTransfer.files.length) {
        input.files = event.dataTransfer.files;
      }
    });
  });

  var lastTimeInput = null;
  document.querySelectorAll("input[type=number][name$='_start'], input[type=number][name$='_end'], input[name=target_start], input[name=target_end]").forEach(function (input) {
    input.addEventListener("focus", function () {
      lastTimeInput = input;
    });
  });
  document.querySelectorAll(".waveform[data-duration]").forEach(function (waveform) {
    waveform.addEventListener("click", function (event) {
      if (!lastTimeInput) return;
      var duration = parseFloat(waveform.getAttribute("data-duration") || "0");
      if (!duration) return;
      var rect = waveform.getBoundingClientRect();
      var ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
      lastTimeInput.value = (ratio * duration).toFixed(2);
      lastTimeInput.dispatchEvent(new Event("input"));
    });
  });
})();
