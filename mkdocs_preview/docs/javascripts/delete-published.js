let adminPublishSecret = "";

function setDeleteControlsUnlocked(unlocked) {
  const buttons = document.querySelectorAll(".delete-published-document");
  buttons.forEach(function (button) {
    button.hidden = !unlocked;
    button.disabled = !unlocked;
  });
}

function createAdminControls() {
  if (document.getElementById("admin-access-button")) return null;
  const control = document.createElement("div");
  control.className = "admin-access-control";
  const button = document.createElement("button");
  button.type = "button";
  button.id = "admin-access-button";
  button.textContent = "Admin";
  button.setAttribute("aria-pressed", "false");
  const publishLink = document.createElement("a");
  publishLink.href = "/editor";
  publishLink.id = "admin-publish-link";
  publishLink.textContent = "Publish";
  publishLink.title = "Open the converter to publish a document";
  publishLink.hidden = true;
  control.appendChild(publishLink);
  control.appendChild(button);
  document.body.appendChild(control);
  return { button: button, publishLink: publishLink };
}

async function configureDeleteControls() {
  setDeleteControlsUnlocked(false);
  const controls = createAdminControls();
  if (!controls) return;
  try {
    const response = await fetch("/api/site-capabilities");
    const capabilities = await response.json();
    if (capabilities.mutations_enabled) return;
    controls.button.textContent = "Admin unavailable";
    controls.button.title = "Administrator setup is required before hosted documents can be changed.";
    controls.button.disabled = true;
  } catch (error) {
    controls.button.textContent = "Admin unavailable";
    controls.button.title = "Unable to verify administrator access.";
    controls.button.disabled = true;
  }
}

document.addEventListener("DOMContentLoaded", configureDeleteControls);

document.addEventListener("click", async function (event) {
  const adminButton = event.target.closest("#admin-access-button");
  if (adminButton) {
    if (adminButton.disabled) return;
    const candidateSecret = window.prompt("Enter the admin passcode:");
    if (candidateSecret === null) return;
    const form = new FormData();
    form.append("publish_secret", candidateSecret);
    const response = await fetch("/api/admin-access", { method: "POST", body: form });
    const result = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      adminPublishSecret = "";
      setDeleteControlsUnlocked(false);
      const publishLink = document.getElementById("admin-publish-link");
      if (publishLink) publishLink.hidden = true;
      window.alert(result.detail || "Admin access denied.");
      return;
    }
    adminPublishSecret = candidateSecret;
    setDeleteControlsUnlocked(true);
    adminButton.textContent = "Admin active";
    adminButton.setAttribute("aria-pressed", "true");
    const publishLink = document.getElementById("admin-publish-link");
    if (publishLink) publishLink.hidden = false;
    return;
  }

  const button = event.target.closest(".delete-published-document");
  if (!button || button.disabled) return;
  const sitePath = button.dataset.sitePath;
  if (!window.confirm("Delete " + sitePath + "? This cannot be undone.")) return;
  button.disabled = true;
  const form = new FormData();
  form.append("site_path", sitePath);
  form.append("publish_secret", adminPublishSecret);
  const response = await fetch("/api/delete-published", { method: "POST", body: form });
  const result = await response.json().catch(function () { return {}; });
  if (!response.ok) {
    window.alert(result.detail || "Unable to delete the document.");
    if (response.status === 403 || response.status === 503) {
      adminPublishSecret = "";
      setDeleteControlsUnlocked(false);
      const adminButton = document.getElementById("admin-access-button");
      if (adminButton) {
        adminButton.textContent = "Admin";
        adminButton.setAttribute("aria-pressed", "false");
      }
      const publishLink = document.getElementById("admin-publish-link");
      if (publishLink) publishLink.hidden = true;
    } else {
      button.disabled = false;
    }
    return;
  }
  window.location.reload();
});
