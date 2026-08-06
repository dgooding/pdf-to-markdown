async function configureDeleteControls() {
  const buttons = document.querySelectorAll(".delete-published-document");
  if (!buttons.length) return;
  try {
    const response = await fetch("/api/site-capabilities");
    const capabilities = await response.json();
    if (capabilities.mutations_enabled) return;
    buttons.forEach(function (button) {
      button.disabled = true;
      button.textContent = "Delete unavailable";
      button.title = "Administrator setup is required before hosted documents can be deleted.";
    });
  } catch (error) {
    buttons.forEach(function (button) {
      button.disabled = true;
      button.title = "Unable to verify deletion availability.";
    });
  }
}

document.addEventListener("DOMContentLoaded", configureDeleteControls);

document.addEventListener("click", async function (event) {
  const button = event.target.closest(".delete-published-document");
  if (!button || button.disabled) return;
  const sitePath = button.dataset.sitePath;
  if (!window.confirm("Delete " + sitePath + "? This cannot be undone.")) return;
  const publishSecret = window.prompt("Enter the publish secret to delete this document:");
  if (publishSecret === null) return;
  button.disabled = true;
  const form = new FormData();
  form.append("site_path", sitePath);
  form.append("publish_secret", publishSecret);
  const response = await fetch("/api/delete-published", { method: "POST", body: form });
  const result = await response.json().catch(function () { return {}; });
  if (!response.ok) {
    window.alert(result.detail || "Unable to delete the document.");
    button.disabled = false;
    return;
  }
  window.location.reload();
});
