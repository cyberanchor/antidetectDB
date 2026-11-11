#!/usr/bin/env bash
# Build the antidetectDB site into site/public/.
#
# Sources: config/ (settings), content/ (home text; one page per product), layouts/ (templates),
# assets/ (adb.css, adb.js, the logo mark), static/ (icons). No theme: the templates are all in layouts/.
# Data: ../data/products/<id>.yaml, one file per product, and ../data/upstream.yaml. Rebuild after editing
# them and commit public/.
# Only Hugo extended (0.146 or newer) is needed; Hugo's cache stays outside the repository ($ADB_CACHE, default
# ~/.cache/antidetectdb-site).
#
#   ./build.sh            build the site into public/
#   ./build.sh --serve    live preview at http://localhost:1313/
#
# HUGO=/path/to/hugo ./build.sh uses another Hugo binary.
set -euo pipefail
cd "$(dirname "$0")"
HUGO=${HUGO:-hugo}
CACHE=${ADB_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/antidetectdb-site}
export HUGO_RESOURCEDIR="$CACHE/resources"
mkdir -p "$CACHE"

if [ "${1:-}" = "--serve" ]; then
  exec "$HUGO" server --noBuildLock --disableFastRender --baseURL http://localhost:1313/
fi

"$HUGO" version
# Build into a fresh folder and replace public/ only when Hugo succeeded: a broken data file stops the build
# with its message and leaves the last good site in place.
tmp=$(mktemp -d "$CACHE/public.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
"$HUGO" --noBuildLock --minify --gc --logLevel warn --destination "$tmp"
chmod 755 "$tmp"
rm -rf public
mv "$tmp" public
echo "built: public/ ($(find public -name '*.html' | wc -l) pages)"
