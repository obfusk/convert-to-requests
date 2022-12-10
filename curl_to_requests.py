#!/usr/bin/python3
# SPDX-FileCopyrightText: 2022 FC Stegerman <flx@obfusk.net>
# SPDX-License-Identifier: GPL-3.0-or-later

import shlex
import sys

import requests


def curl_to_requests(curl_command):
    method = "GET"
    headers = {}
    data = None
    ignored = []
    cmd, url, *curl = [x for x in shlex.split(curl_command) if x != "\n"]
    assert cmd == "curl"
    i, l = 0, len(curl)
    while i < l:
        if curl[i] == "-H":
            k, v = curl[i+1].split(": ", 1)
            headers[k] = v
            i += 1
        elif curl[i] == "-X":
            method = curl[i+1]
            if method not in ("GET", "OPTIONS", "HEAD", "POST", "PUT", "PATCH", "DELETE"):
                raise NotImplementedError(f"Unknown method: {curl[i+1]}")
            i += 1
        elif curl[i] == "--data-raw":
            data = curl[i+1].encode()
            i += 1
        elif curl[i] == "--compressed":
            ignored.append(curl[i])
        else:
            raise NotImplementedError(f"Unknown curl argument: {curl[i]}")
        i += 1
    return method, url, headers, data, ignored


def curl_to_python_code(curl_command):
    method, url, headers, data, _ = curl_to_requests(curl_command)
    d = f", data={d!r}" if data is not None else ""
    return f"requests.request({method!r}, {url!r}, headers={headers!r}{d})"


def main(*args):
    verbose = "-v" in args or "--verbose" in args
    dry_run = "--dry-run" in args
    curl_command = sys.stdin.read()
    method, url, headers, data, ign = curl_to_requests(curl_command)
    for arg in ign:
        print(f"Warning: ignoring {arg}", file=sys.stderr)
    if verbose or dry_run:
        print(f"method={method} url={url} headers={headers} data={data}", file=sys.stderr)
    if not dry_run:
        kwargs = dict(headers=headers)
        if data is not None:
            kwargs["data"] = data
        r = requests.request(method, url, **kwargs)
        r.raise_for_status()
        print(r.text, end="")


if __name__ == "__main__":
    main(*sys.argv[1:])
