#!/usr/bin/env bash
# Update the course repo. Run this instead of `git pull`.
#
#     bash update.sh
#
# WHY THIS EXISTS
# ---------------
# The repo was reorganised into one folder per session. Git records that as 51 file
# RENAMES, and a plain `git pull` refuses to run if you have uncommitted edits to a
# file that moved:
#
#     error: Your local changes to the following files would be overwritten by merge:
#             my_handoffs7.py
#
# Nothing is lost when that happens -- the pull just stops. But almost everyone has
# edited my_handoffs7.py, so almost everyone would hit it.
#
# The fix is to commit your work first. Git then merges the rename with your edit and
# your file reappears, with your changes in it, at its new path. This script does that
# and nothing else. It never uses --force and it never discards anything.
set -u
cd "$(dirname "$0")"

echo "== 1. saving your local work =============================================="
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git -c user.name="${USER:-student}" -c user.email="${USER:-student}@local" \
      commit -qm "my work, before the session-folder reorganisation" \
    && echo "   committed your local changes so the merge can keep them"
else
  echo "   nothing local to save"
fi

echo "== 2. pulling ============================================================="
if git pull --no-rebase; then
  echo
  echo "== 3. where your files went ==============================================="
  echo "   Your session-7 homework:  session-07/my_handoffs7.py"
  echo "   Today:                    session-08/   (notebook + my_attack8.py)"
  echo "   Shared code:              shared/  and  plant/"
  echo
  echo "   Run things from INSIDE the session folder:"
  echo "       cd session-08"
  echo "       python doctor8.py"
  echo
  echo "DONE."
else
  echo
  echo "!! The pull did not finish. Nothing is lost. Two lines to fix it:"
  echo
  echo "     git merge --abort"
  echo "     git status"
  echo
  echo "   Then send me the output of 'git status'. Do NOT run git checkout ."
  echo "   or git reset --hard -- those are the commands that lose work."
  exit 1
fi
