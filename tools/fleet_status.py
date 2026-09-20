#!/usr/bin/env python3
"""Report the CI state of every repository in the fork, and say so out loud.

Why this exists: the forks build on a nightly `schedule`, and a scheduled run that
fails is the quietest kind of failure there is. `opendxl-siem-sensor` sat red for
five nights with a rustls advisory (RUSTSEC-2026-0285) while the documentation next
to it said "all green", because nobody opens forty-seven Actions tabs in the morning.

Usage:

    python tools/fleet_status.py                  # human-readable table, exit 1 if not green
    python tools/fleet_status.py --json state.json

The exit code is what the workflow acts on: 0 when every repository that has CI is
green, 1 when at least one is not. Repositories with no workflow at all are listed
but do not fail the check - they are a deliberate state, not a regression.

Only public data is read, so this works with the workflow's own GITHUB_TOKEN and
even unauthenticated; a token only buys a larger rate limit.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

OWNER = os.environ.get('FLEET_OWNER', 'JMuellerTX')
API = 'https://api.github.com'


def get(path, **params):
    url = f'{API}{path}'
    if params:
        url += '?' + '&'.join(f'{k}={v}' for k, v in params.items())
    req = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'opendxl-fleet-status',
    })
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def repositories():
    out, page = [], 1
    while True:
        batch = get(f'/users/{OWNER}/repos', per_page=100, page=page, type='owner')
        if not batch:
            return sorted(out, key=lambda r: r['name'])
        out += [r for r in batch if not r.get('archived')]
        page += 1


def latest_run(name, branch):
    try:
        runs = get(f'/repos/{OWNER}/{name}/actions/runs',
                   per_page=1, branch=branch, exclude_pull_requests='true')
    except urllib.error.HTTPError as exc:
        # 404 here means Actions is disabled for the repository, which is the
        # same answer as "no runs" for our purposes.
        if exc.code in (403, 404):
            return None
        raise
    runs = runs.get('workflow_runs') or []
    return runs[0] if runs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', metavar='FILE', help='also write the raw state here')
    args = ap.parse_args()

    green, broken, running, no_ci = [], [], [], []
    for repo in repositories():
        name = repo['name']
        branch = repo.get('default_branch') or 'main'
        run = latest_run(name, branch)
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
             'running': running, 'no_ci': no_ci}
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump(state, fh, indent=2)

    with_ci = len(green) + len(broken) + len(running)
    print(f'{OWNER}: {len(green) + len(broken) + len(running) + len(no_ci)} repositories, '
          f'{with_ci} with CI, {len(green)} green, {len(broken)} not green, '
          f'{len(running)} still running, {len(no_ci)} without a workflow')
    for row in broken:
        print(f'  NOT GREEN  {row["repo"]} ({row["branch"]}) '
              f'{row["conclusion"]} via {row["event"]} {row["created_at"]}')
        print(f'             {row["url"]}')
    for row in running:
        print(f'  running    {row["repo"]} ({row["branch"]}) since {row["created_at"]}')
    for row in no_ci:
        print(f'  no CI      {row["repo"]} ({row["branch"]})')

    return 1 if broken else 0


if __name__ == '__main__':
    sys.exit(main())
