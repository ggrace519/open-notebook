#!/usr/bin/env bash
# Remove open-notebook-image.tar from branch history so push succeeds (file > 100MB).
# Requires: git-filter-repo (pip install git-filter-repo). Run in WSL or Git Bash from repo root:
#   bash scripts/remove-tar-from-history.sh
# Or pass your branch name:
#   bash scripts/remove-tar-from-history.sh "fix/bug-in-ask-and-search"

set -e
# Default: current branch (use $1 if provided)
BRANCH="${1:-$(git branch --show-current)}"

REMOTE_URL=$(git config --get remote.origin.url 2>/dev/null || true)

echo "Stashing uncommitted changes..."
git stash push -u -m "before remove-tar-from-history" || true

echo "Removing large tar file from history on branch: $BRANCH..."
# Match any path ending with open-notebook-image.tar (covers repo root and Windows-mangled paths)
git filter-repo \
  --path-glob '*open-notebook-image.tar' \
  --invert-paths \
  --refs "refs/heads/$BRANCH" \
  --force

echo "Re-adding origin if needed (filter-repo removes remotes by default)..."
if [ -n "$REMOTE_URL" ] && ! git config --get remote.origin.url >/dev/null 2>&1; then
  git remote add origin "$REMOTE_URL"
elif [ -z "$REMOTE_URL" ]; then
  echo "Could not restore origin. Add it manually: git remote add origin <url>"
fi

echo "Restoring working tree..."
git stash pop || true

echo "Done. Push with: git push --force-with-lease origin $BRANCH"
