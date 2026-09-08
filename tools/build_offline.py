"""Build a standalone HTML copy of the documentation.

The result is a folder that works from a local disk: open `index.html` in a
browser, no web server, no network. Useful for reading on a machine that cannot
reach GitHub Pages, for attaching to a review, and for shipping the docs next
to an air-gapped deployment.

    python tools/build_offline.py                  # -> site-offline/
    python tools/build_offline.py --zip            # -> dist/opendxl-docs-offline-<date>.zip
    python tools/build_offline.py --out /tmp/docs  # somewhere else

Three things separate this from `mkdocs build`:

* `mkdocs.offline.yml` writes `page.html` instead of `page/index.html`, because
  a directory URL needs a server, and turns off the web font.
* Material's search works from `file://` only through the `iframe-worker` shim,
  which the theme loads from a CDN. This vendors it, so the folder makes no
  network request at all. Without network access the reference is removed
  rather than left pointing at the CDN: the build still succeeds, and search
  is the one thing that does not work.
* Afterwards every internal link is resolved against the output. A build that
  looks fine in a browser tab and 404s two clicks deeper is worse than no
  build, so a broken link fails this script.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CONFIG = REPO / "mkdocs.offline.yml"
DEFAULT_OUT = REPO / "site-offline"

# Material references this from the CDN when the offline plugin is active.
SHIM_URL = "https://unpkg.com/iframe-worker/shim"
SHIM_CACHE = HERE / "vendor" / "iframe-worker-shim.js"
SHIM_TAG = re.compile(r'<script src="https://unpkg\.com/iframe-worker/shim"></script>')
SHIM_LOCAL = "assets/javascripts/iframe-worker-shim.js"

SKIP_SCHEMES = ("http:", "https:", "mailto:", "javascript:", "data:", "tel:")


class LinkCollector(HTMLParser):
    """Collects href/src targets that point inside the build."""

    def __init__(self) -> None:
        super().__init__()
        self.targets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.targets.append(value)


def build(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    print("[1/4] mkdocs build (%s)" % CONFIG.name)
    subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict", "-q",
         "-f", str(CONFIG), "-d", str(out)],
        cwd=str(REPO), check=True,
    )


def drop_server_only_pages(out: Path) -> None:
    """Removes what only a web server can use.

    mkdocs writes a `404.html` whose links are absolute (`/clients/python.html`),
    because a not-found page is served from an arbitrary URL and cannot know how
    deep it sits. From a local folder nothing serves it and every link in it is
    broken, so it is dropped rather than shipped as the one page that fails.
    """
    page = out / "404.html"
    if page.exists():
        page.unlink()
        print("      removed 404.html (server-only, absolute links)")


def vendor_search_shim(out: Path) -> bool:
    """Point the shim at a local copy. Returns False when it could not be had."""
    print("[2/4] vendoring the search shim")
    pages = [p for p in out.rglob("*.html") if SHIM_TAG.search(p.read_text(encoding="utf-8"))]
    if not pages:
        print("      no page references the shim - nothing to vendor")
        return True

    source = None
    if SHIM_CACHE.is_file():
        source = SHIM_CACHE.read_text(encoding="utf-8")
        print("      using the cached copy at %s" % SHIM_CACHE.relative_to(REPO))
    else:
        try:
            with urllib.request.urlopen(SHIM_URL, timeout=20) as response:
                source = response.read().decode("utf-8")
            SHIM_CACHE.parent.mkdir(parents=True, exist_ok=True)
            SHIM_CACHE.write_text(source, encoding="utf-8")
            print("      downloaded and cached at %s" % SHIM_CACHE.relative_to(REPO))
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            # Leaving the tag in place would keep a CDN reference in a copy
            # whose whole point is that it needs no network. Strip it instead:
            # the search box stops working, everything else is unaffected, and
            # the promise "loads nothing from outside the folder" still holds.
            print("      could not fetch %s (%s)" % (SHIM_URL, error))
            for page in pages:
                page.write_text(SHIM_TAG.sub("", page.read_text(encoding="utf-8")),
                                encoding="utf-8")
            print("      removed the CDN reference from %d page(s)" % len(pages))
            print("      the copy is complete and offline; only the search box will not")
            print("      work. Run again with network access to restore it.")
            return False

    target = out / SHIM_LOCAL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    for page in pages:
        depth = len(page.relative_to(out).parts) - 1
        rel = "../" * depth + SHIM_LOCAL
        text = SHIM_TAG.sub('<script src="%s"></script>' % rel,
                            page.read_text(encoding="utf-8"))
        page.write_text(text, encoding="utf-8")
    print("      rewritten in %d page(s)" % len(pages))
    return True


def check_links(out: Path) -> list[str]:
    print("[3/4] resolving every internal link")
    problems: list[str] = []
    pages = sorted(out.rglob("*.html"))
    for page in pages:
        collector = LinkCollector()
        collector.feed(page.read_text(encoding="utf-8", errors="replace"))
        for target in collector.targets:
            if target.startswith(SKIP_SCHEMES) or target.startswith("#") or not target:
                continue
            if target.startswith("/"):
                problems.append("%s: absolute path %s" % (page.relative_to(out), target))
                continue
            path = (page.parent / target.split("#")[0].split("?")[0]).resolve()
            if not path.exists():
                problems.append("%s: %s does not resolve" % (page.relative_to(out), target))
    print("      %d page(s), %d problem(s)" % (len(pages), len(problems)))
    return problems


def make_zip(out: Path) -> Path:
    dist = REPO / "dist"
    dist.mkdir(exist_ok=True)
    archive = dist / ("opendxl-docs-offline-%s.zip" % dt.date.today().isoformat())
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(out.rglob("*")):
            if path.is_file():
                zf.write(path, Path(out.name) / path.relative_to(out))
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help="output directory (default: site-offline)")
    parser.add_argument("--zip", action="store_true",
                        help="also write dist/opendxl-docs-offline-<date>.zip")
    parser.add_argument("--no-search-shim", action="store_true",
                        help="do not vendor the search shim, and do not fail without it")
    args = parser.parse_args()

    out = Path(args.out).resolve()
    build(out)
    drop_server_only_pages(out)

    if args.no_search_shim:
        print("[2/4] skipping the search shim (--no-search-shim)")
        shimmed = True
    else:
        shimmed = vendor_search_shim(out)

    problems = check_links(out)
    if problems:
        for problem in problems[:20]:
            print("      %s" % problem)
        if len(problems) > 20:
            print("      ... and %d more" % (len(problems) - 20))
        print("build failed: the copy would be broken from a local folder")
        return 1

    print("[4/4] done")
    print("  %s" % out)
    print("  open %s" % (out / "index.html"))
    if not shimmed:
        print("  note: search is unavailable in this copy (no shim)")
    if args.zip:
        archive = make_zip(out)
        size = archive.stat().st_size / (1024 * 1024)
        print("  %s (%.1f MB)" % (archive, size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
