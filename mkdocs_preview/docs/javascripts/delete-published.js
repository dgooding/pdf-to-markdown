const repositoryUrl = "https://github.com/dgooding/pdf-to-markdown";
const pagesRoot = "/pdf-to-markdown/";

function createAdminControls() {
  if (document.getElementById("admin-access-button")) return null;
  const control = document.createElement("div");
  control.className = "admin-access-control";
  const adminLink = document.createElement("a");
  adminLink.id = "admin-access-button";
  adminLink.href = pagesRoot + "converter/";
  adminLink.textContent = "Admin";
  adminLink.title = "Open GitHub document administration";
  control.appendChild(adminLink);
  document.body.appendChild(control);
  return adminLink;
}

function configureGitHubControls() {
  createAdminControls();
  document.querySelectorAll(".delete-published-document").forEach(function (button) {
    button.hidden = false;
    button.disabled = false;
    button.title = "Request deletion through GitHub";
  });
}

document.addEventListener("DOMContentLoaded", configureGitHubControls);

document.addEventListener("click", function (event) {
  const button = event.target.closest(".delete-published-document");
  if (!button || button.disabled) return;
  event.preventDefault();
  const sitePath = button.dataset.sitePath;
  const issueUrl = new URL(repositoryUrl + "/issues/new");
  issueUrl.searchParams.set("title", "[delete-published] " + sitePath);
  issueUrl.searchParams.set(
    "body",
    "Delete the published document at `" + sitePath + "`.\n\n" +
      "The GitHub Actions workflow will verify repository write permission before making changes."
  );
  window.location.href = issueUrl.toString();
});
