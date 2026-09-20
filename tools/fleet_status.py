#!/usr/bin/env python3
"""Report the CI state of every repository in the fork, and say so out loud.

Why this exists: the forks build on a nightly `schedule`, and a scheduled run that
fails is the quietest kind of failure there is. `opendxl-siem-sensor` sat red for
five nights with a rustls advisory (RUSTSEC-2026-0285) while the documentation next
to it said "all green", because nobody opens forty-seven Actions tabs in the morning.

Usage:

    python tools/fleet_status.py                  # human-readable table
    python tools/fleet_status.py --json state.json

The exit code is what the workflow acts on: 0 when every repository that has CI is
green, 1 otherwise. Two things count as "otherwise", and the second one matters:

* a repository whose last run failed, and
* a repository this script could not read.

An unreadable repository is not a green one. The first version of this script
folded a 403 into "has no workflow", and a throttled run therefore reported five
repositories with CI as deliberately having none - the same comfortable silence it
exists to break. Errors are now retried, then listed as unknown, and they fail the
check.

Only public data is read, but run it with a token. The unauthenticated limit is 60
requests an hour per address, this makes one per repository, and a hosted runner's
address is not its own - the first version ran anonymously and was throttled into
exactly the wrong answer. `GITHUB_TOKEN` is enough and raises the limit to 1000.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

OWNER = os.environ.get('FLEET_OWNER', 'JMuellerTX')
API = 'https://api.github.com'
BACKOFF = (2, 5, 15)  # seconds between attempts; four attempts in total


class Unreadable(Exception):
    """The API would not answer for this repository, after retrying."""


def get(path, **params):
    url = f'{API}{path}'
    if params:
        url += '?' + '&'.join(f'{k}={v}' for k, v in params.items())
    req = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'opendxl-fleet-status',
    })
    token = os.environ.get('FLEET_TOKEN') or os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token:
        req.add_header('Authorization', f'Bearer {token}')

    last = None
    for pause in (0,) + BACKOFF:
        if pause:
            time.sleep(pause)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            last = exc
            # 404 is an answer, not a failure: the resource is not there.
            if exc.code == 404:
                raise
            # An exhausted rate limit resets on the hour, not in fifteen seconds.
            # Retrying it turns a quick wrong answer into a slow one; say so instead.
            if exc.headers.get('x-ratelimit-remaining') == '0':
                reset = exc.headers.get('x-ratelimit-reset', '?')
                limit = exc.headers.get('x-ratelimit-limit', '?')
                when = time.strftime('%H:%M:%SZ', time.gmtime(int(reset))) if reset.isdigit() else reset
                raise Unreadable(f'rate limit of {limit}/h exhausted, resets {when}'
                                 f'{" - run with a token" if not token else ""}') from exc
            # Throttling and server trouble are worth another attempt; anything
            # else (401, 422, ...) will not improve by repeating it.
            if exc.code not in (403, 429, 500, 502, 503, 504):
                raise Unreadable(f'HTTP {exc.code}') from exc
        except OSError as exc:  # timeout, DNS, reset connection
            last = exc
    raise Unreadable(str(last))


def repositories():
    out, page = [], 1
    while True:
        batch = get(f'/users/{OWNER}/repos', per_page=100, page=page, type='owner')
        if not batch:
            return sorted(out, key=lambda r: r['name'])
        out += [r for r in batch if not r.get('archived')]
        page += 1


def latest_run(name, branch):
    """The newest run on `branch`, or None when the repository has no runs.

    Raises Unreadable when the API would not say.
    """
    try:
        runs = get(f'/repos/{OWNER}/{name}/actions/runs',
                   per_page=1, branch=branch, exclude_pull_requests='true')
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # Actions is disabled for the repository: the same answer as "no runs".
            return None
        raise Unreadable(f'HTTP {exc.code}') from exc
    runs = runs.get('workflow_runs') or []
    return runs[0] if runs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', metavar='FILE', help='also write the raw state here')
    args = ap.parse_args()

    green, broken, running, no_ci, unknown = [], [], [], [], []
    try:
        repos = repositories()
    except Unreadable as exc:
        # Without the list there is nothing to say, and saying nothing is the
        # failure mode this script exists to prevent. Fail loudly.
        print(f'cannot list the repositories of {OWNER}: {exc}', file=sys.stderr)
        return 1
    for repo in repos:
        name = repo['name']
        branch = repo.get('default_branch') or 'main'
        try:
            run = latest_run(name, branch)
        except Unreadable as exc:
            unknown.append({'repo': name, 'branch': branch, 'reason': str(exc)})
            continue
        if run is None:
            no_ci.append({'repo': name, 'branch': branch})
            continue
        row = {
            'repo': name, 'branch': branch,
            'status': run['status'], 'conclusion': run['conclusion'],
            'event': run['event'], 'created_at': run['created_at'],
            'url': run['html_url'],
        }
        if run['status'] != 'completed':
            running.append(row)
        elif run['conclusion'] == 'success':
            green.append(row)
        else:
            broken.append(row)

    state = {'owner': OWNER, 'green': green, 'broken': broken,
             'running': running, 'no_ci': no_ci, 'unknown': unknown}
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump(state, fh, indent=2)

    total = len(green) + len(broken) + len(running) + len(no_ci) + len(unknown)
    with_ci = len(green) + len(broken) + len(running)
    print(f'{OWNER}: {total} repositories, {with_ci} with CI, {len(green)} green, '
          f'{len(broken)} not green, {len(running)} still running, '
          f'{len(no_ci)} without a workflow, {len(unknown)} unreadable')
    for row in broken:
        print(f'  NOT GREEN  {row["repo"]} ({row["branch"]}) '
              f'{row["conclusion"]} via {row["event"]} {row["created_at"]}')
        print(f'             {row["url"]}')
    for row in unknown:
        print(f'  UNREADABLE {row["repo"]} ({row["branch"]}) {row["reason"]}')
    for row in running:
        print(f'  running    {row["repo"]} ({row["branch"]}) since {row["created_at"]}')
    for row in no_ci:
        print(f'  no CI      {row["repo"]} ({row["branch"]})')

    return 1 if broken or unknown else 0


if __name__ == '__main__':
    sys.exit(main())
