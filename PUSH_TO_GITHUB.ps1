# PUSH_TO_GITHUB.ps1
# Run this ONCE after you've created an empty repo on github.com
#
# Step 1: Go to https://github.com/new
#         Name it whatever you like (e.g. pdf-to-markdown)
#         Leave it EMPTY (no README, no .gitignore) — click "Create repository"
#
# Step 2: Copy the repo URL shown on screen (looks like https://github.com/YourName/repo-name.git)
#
# Step 3: Open PowerShell in this folder and run:
#         .\PUSH_TO_GITHUB.ps1 -RepoUrl https://github.com/YourName/repo-name.git

param(
    [Parameter(Mandatory=$true)]
    [string]$RepoUrl
)

Set-Location $PSScriptRoot

Write-Host "Adding remote origin: $RepoUrl" -ForegroundColor Cyan
git remote add origin $RepoUrl

Write-Host "Setting branch to main..." -ForegroundColor Cyan
git branch -M main

Write-Host "Pushing to GitHub (you may be prompted to log in)..." -ForegroundColor Cyan
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "DONE! Your app is on GitHub at: $($RepoUrl -replace '\.git$','')" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next step — Deploy on Render.com:" -ForegroundColor Yellow
    Write-Host "  1. Go to https://render.com -> New -> Web Service"
    Write-Host "  2. Connect your GitHub repo"
    Write-Host "  3. Render auto-detects render.yaml — click Deploy"
    Write-Host "  4. In Render dashboard -> Environment, add: PUBLISH_SECRET = <your-secret>"
    Write-Host "  5. Visit <your-render-url>/editor to confirm it works"
} else {
    Write-Host "Push failed. Check the error above." -ForegroundColor Red
    Write-Host "Common fix: GitHub may ask you to authenticate — use a Personal Access Token as the password."
    Write-Host "Create one at: https://github.com/settings/tokens -> Generate new token (classic) -> check 'repo'"
}
