#!/usr/bin/env bash
# Keep every old branch as a tag, then delete the branch — the last step of the
# 2026-09-23 consolidation (docs/BRANCHING.md). Run it from a clone that can
# push tags and delete branches on GitHub: the cloud session that built
# `develop` could push commits, but GitHub refused it both (HTTP 403).
#
#   bash scripts/archive_old_branches.sh            # tag, push, check — deletes nothing
#   bash scripts/archive_old_branches.sh --delete   # the same, then delete the branches
#
# Safe to run again. A branch is deleted only after its tag is confirmed on the
# remote at the branch's commit, and only if the branch has not moved since
# (a lease), so a commit pushed in the meantime is never lost. Deleting a
# branch closes any pull request opened from it; its page stays readable.
set -euo pipefail
set -f  # branch names are never globs

remote="${REMOTE:-origin}"
delete=no
case "${1:-}" in
  "") ;;
  --delete) delete=yes ;;
  *) echo "usage: $0 [--delete]" >&2; exit 2 ;;
esac

git fetch --quiet --prune "$remote"
for keep in main develop; do
  if ! git rev-parse --verify --quiet "refs/remotes/$remote/$keep" >/dev/null; then
    echo "Stopping: $remote has no '$keep' branch. Nothing was changed." >&2
    exit 1
  fi
done

branches=$(git for-each-ref --format='%(refname:strip=3)' "refs/remotes/$remote" | grep -vxE 'HEAD|main|develop' || true)
if [ -z "$branches" ]; then
  echo "Nothing to archive: only main and develop are left."
  exit 0
fi

tip() { git rev-parse "refs/remotes/$remote/$1"; }

count=0
tags=()
for branch in $branches; do
  tag="archive/$branch"
  existing=$(git rev-parse --verify --quiet "refs/tags/$tag^{commit}" || true)
  if [ -z "$existing" ]; then
    git tag "$tag" "$(tip "$branch")"
  elif [ "$existing" != "$(tip "$branch")" ]; then
    echo "Stopping: tag $tag already points at another commit than $branch. Nothing was deleted." >&2
    exit 1
  fi
  tags+=("refs/tags/$tag")
  count=$((count + 1))
done
git push --quiet "$remote" "${tags[@]}"

remote_tags=$(git ls-remote --tags "$remote" 'refs/tags/archive/*')
missing=0
for branch in $branches; do
  line="$(tip "$branch")"$'\t'"refs/tags/archive/$branch"
  if ! grep -qxF "$line" <<<"$remote_tags"; then
    echo "Not on $remote at the branch's commit: archive/$branch" >&2
    missing=$((missing + 1))
  fi
done
if [ "$missing" -ne 0 ]; then
  echo "Stopping: $missing tag(s) are not on $remote. Nothing was deleted." >&2
  exit 1
fi
echo "Kept $count branch(es) as tags archive/<branch> on $remote, each checked."

if [ "$delete" = no ]; then
  echo "Nothing deleted. Run again with --delete to delete these branches:"
  printf '  %s\n' $branches
  exit 0
fi

leases=()
refs=()
for branch in $branches; do
  leases+=("--force-with-lease=refs/heads/$branch:$(tip "$branch")")
  refs+=(":refs/heads/$branch")
done
# All or none: a branch that moved since the fetch refuses the whole push.
git push --atomic "${leases[@]}" "$remote" "${refs[@]}"
git fetch --quiet --prune "$remote"
echo "Done. Branches on $remote now:"
git ls-remote --heads "$remote" | sed 's#.*refs/heads/#  #'
