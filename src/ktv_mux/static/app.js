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

  document.querySelectorAll("[data-use-playhead]").forEach(function (button) {
    button.addEventListener("click", function () {
      var player = document.querySelector("[data-subtitle-player]");
      if (!player || !lastTimeInput) return;
      lastTimeInput.value = Number(player.currentTime || 0).toFixed(2);
      lastTimeInput.dispatchEvent(new Event("input"));
    });
  });

  document.querySelectorAll("[data-seek-time]").forEach(function (button) {
    button.addEventListener("click", function () {
      var player = document.querySelector("[data-subtitle-player]");
      if (!player) return;
      player.currentTime = parseFloat(button.getAttribute("data-seek-time") || "0");
      player.play().catch(function () {});
    });
  });

  document.querySelectorAll("[data-sync-review]").forEach(function (button) {
    button.addEventListener("click", function () {
      var players = Array.prototype.slice.call(document.querySelectorAll("[data-sync-player]"));
      if (!players.length) return;
      var source = players.find(function (player) { return !player.paused; }) || players[0];
      var current = Number(source.currentTime || 0);
      players.forEach(function (player) {
        if (player === source) return;
        try {
          player.currentTime = current;
        } catch (error) {}
      });
    });
  });

  document.addEventListener("keydown", function (event) {
    var active = document.activeElement;
    if (active && ["INPUT", "TEXTAREA", "SELECT"].indexOf(active.tagName) !== -1) return;
    var player = document.querySelector("[data-subtitle-player]");
    if (!player) return;
    if (event.key === "[") {
      player.currentTime = Math.max(0, Number(player.currentTime || 0) - 0.1);
    } else if (event.key === "]") {
      player.currentTime = Number(player.currentTime || 0) + 0.1;
    } else if (event.key.toLowerCase() === "s" && lastTimeInput) {
      lastTimeInput.value = Number(player.currentTime || 0).toFixed(2);
      lastTimeInput.dispatchEvent(new Event("input"));
    }
  });

  var live = document.querySelector("[data-live-status]");
  if (live && window.EventSource) {
    var source = new EventSource("/events");
    source.addEventListener("jobs", function (event) {
      try {
        var payload = JSON.parse(event.data);
        var active = (payload.jobs || []).filter(function (job) {
          return ["queued", "running", "canceling"].indexOf(job.state) !== -1;
        });
        live.textContent = active.length ? active.length + " active job(s). Refreshing status..." : "No active jobs.";
        if (!active.length) source.close();
      } catch (error) {
        live.textContent = "Live status update could not be parsed.";
      }
    });
  }
})();
