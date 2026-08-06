# Published Documents

Documents published from the ITSD converter appear here.

Use the **Converter** item in the site navigation to publish a new document directly into this site.

## Available Documents

- [Promotion Forecast Power App _2_](promotion-forecast-power-app-2/index.md) — `promotion-forecast-power-app-2` <button type="button" class="delete-published-document" data-site-path="promotion-forecast-power-app-2">Delete</button>
- [Service Desk Publish Smoke](user-manuals/service-desk-publish-smoke/index.md) — `user-manuals/service-desk-publish-smoke` <button type="button" class="delete-published-document" data-site-path="user-manuals/service-desk-publish-smoke">Delete</button>

<script>
document.addEventListener('click', async function (event) {
  const button = event.target.closest('.delete-published-document');
  if (!button) return;
  const sitePath = button.dataset.sitePath;
  if (!window.confirm('Delete ' + sitePath + '? This cannot be undone.')) return;
  const publishSecret = window.prompt('Enter the publish secret to delete this document:');
  if (publishSecret === null) return;
  button.disabled = true;
  const form = new FormData();
  form.append('site_path', sitePath);
  form.append('publish_secret', publishSecret);
  const response = await fetch('/api/delete-published', { method: 'POST', body: form });
  const result = await response.json().catch(function () { return {}; });
  if (!response.ok) {
    window.alert(result.detail || 'Unable to delete the document.');
    button.disabled = false;
    return;
  }
  window.location.reload();
});
</script>
