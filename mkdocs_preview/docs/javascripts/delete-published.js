const repositoryUrl = "https://github.com/dgooding/pdf-to-markdown";

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
