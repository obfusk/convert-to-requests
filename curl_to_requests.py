#!/usr/bin/python3
# SPDX-FileCopyrightText: 2022 FC Stegerman <flx@obfusk.net>
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import shlex
import re
import sys

import requests

METHODS = ("GET", "OPTIONS", "HEAD", "POST", "PUT", "PATCH", "DELETE")


def curl_to_requests(command):
    method = "GET"
    headers = {}
    data = None
    ignored = []
    cmd, url, *curl = [x for x in shlex.split(command) if x != "\n"]
    assert cmd == "curl"
    i, l = 0, len(curl)
    while i < l:
        if curl[i] == "-H":
            k, v = curl[i+1].split(": ", 1)
            headers[k] = v
            i += 1
        elif curl[i] == "-X":
            method = curl[i+1]
            assert method in METHODS
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


def fetch_to_requests(command):
    command = re.sub(r"^(await )?fetch\(", "[", command)
    command = re.sub(r"\);$", "]", command)
    url, args = json.loads(command)
    method = args.pop("method", "GET")
    headers = args.pop("headers")
    data = args.pop("body", None)
    if data is not None:
        data = data.encode()
    assert method in METHODS
    return method, url, headers, data, [f"{k}=" for k in args]


def curl_to_python_code(command):
    return to_python_code(*curl_to_requests(command)[:-1])


def fetch_to_python_code(command):
    return to_python_code(*fetch_to_requests(command)[:-1])


def to_python_code(method, url, headers, data=None):
    d = f", data={data!r}" if data is not None else ""
    return f"requests.request({method!r}, {url!r}, headers={headers!r}{d})"


def main(*args):
    verbose = "-v" in args or "--verbose" in args
    dry_run = "--dry-run" in args
    fetch = "--fetch" in args
    command = sys.stdin.read()
    if fetch:
        method, url, headers, data, ign = fetch_to_requests(command)
    else:
        method, url, headers, data, ign = curl_to_requests(command)
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
