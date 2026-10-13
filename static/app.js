document.addEventListener("DOMContentLoaded", () => {
  const input = document.querySelector('input[type="file"]');
  const label = document.querySelector(".file-name");

  if (!input || !label) return;

  input.addEventListener("change", () => {
    label.textContent = input.files?.[0]?.name || "Belum ada berkas dipilih";
  });
});
