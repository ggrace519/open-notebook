#!/usr/bin/env bash
# Prepare a branch with ONLY the modal clipping fix (#541) for a clean PR.
# Excludes: .gitignore, tool-created files (SUBMISSION_GUIDE, PULL_REQUEST_TEMPLATE_filled, etc.)
# Run from repo root, in WSL: bash scripts/prepare-modal-fix-pr.sh
#
# What this does: resets fix/modal-display-clipping-541 to main, then stages and commits
# only the 5 modal-fix files. Your other local changes stay in the working tree (unstaged).

set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "fix/modal-display-clipping-541" ]; then
  echo "Checking out fix/modal-display-clipping-541..."
  git checkout fix/modal-display-clipping-541 2>/dev/null || {
    echo "Branch fix/modal-display-clipping-541 not found. Create it from main first."
    exit 1
  }
fi

# Files that are the actual modal fix (Add Source + Write Note modals, no clipping)
MODAL_FIX_FILES=(
  "frontend/src/components/ui/dialog.tsx"
  "frontend/src/components/sources/AddSourceDialog.tsx"
  "frontend/src/app/(dashboard)/notebooks/components/NoteEditorDialog.tsx"
  "frontend/src/app/globals.css"
  "frontend/src/components/providers/ModalProvider.tsx"
)

echo "=== Resetting branch to main (keeps your working tree unchanged) ==="
git reset --soft main

echo "=== Unstaging everything, then staging only modal-fix files ==="
git reset HEAD

git add "${MODAL_FIX_FILES[@]}"
echo "=== Files that will be in the commit ==="
git status

echo ""
echo "=== Next: create the commit (run in WSL to avoid PowerShell trailer issues) ==="
echo 'git commit -m "fix: prevent Add Source and Write Note modals from clipping content

- Adjust dialog/modal layout and overflow so content is fully visible
- Fixes #541"'
echo ""
echo "Then push: git push --force-with-lease origin fix/modal-display-clipping-541"
echo "Open PR: ggrace519/open-notebook fix/modal-display-clipping-541 -> lfnovo/open-notebook main."
echo ""
echo "Your other local changes are still in the working tree (unstaged)."
