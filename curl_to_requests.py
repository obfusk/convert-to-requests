#!/usr/bin/python3
# SPDX-FileCopyrightText: 2022 FC Stegerman <flx@obfusk.net>
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import json
import re
import shlex
import sys

import requests

METHODS = ("GET", "OPTIONS", "HEAD", "POST", "PUT", "PATCH", "DELETE")


def curl_to_requests(command):
    """
    Parse curl command from "copy as cURL" (Firefox, Chromium).

    Returns method, url, headers, data, ignored_opts.
    """
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
            method = "POST"   # Chromium doesn't add -X POST
            i += 1
        elif curl[i] == "--compressed":
            ignored.append(curl[i])
        else:
            raise NotImplementedError(f"Unknown curl argument: {curl[i]}")
        i += 1
    return method, url, headers, data, ignored


def fetch_to_requests(command):
    """
    Parse fetch code from "copy as fetch" (Firefox, Chromium) or "copy
    as Node.js fetch" (Chromium).

    CAVEATS:
    * "copy as fetch" does not include cookies ("copy as Node.js fetch" does);
    * Chromium doesn't include a User-Agent header in either.

    Returns method, url, headers, data, ignored_args.
    """
    command = re.sub(r"^(await )?fetch\(", "[", command)
    command = re.sub(r"\);$", "]", command)
    url, args = json.loads(command)
    method = args.pop("method", "GET")
    headers = args.pop("headers")
    data = args.pop("body", None)
    if data is not None:
        data = data.encode()
    if referrer := args.pop("referrer", None):
        headers["referer"] = referrer   # not a typo
    if referrer_policy := args.pop("referrerPolicy", None):
        headers["referrer-policy"] = referrer_policy
    assert method in METHODS
    return method, url, headers, data, [f"{k}=" for k in args]


def curl_to_python_code(command):
    """Convert curl command to Python code."""
    return to_python_code(*curl_to_requests(command)[:-1])


def fetch_to_python_code(command):
    """Convert fetch code to Python code."""
    return to_python_code(*fetch_to_requests(command)[:-1])


def to_python_code(method, url, headers, data=None):
    """Create Python code for requests.request() call."""
    d = f", data={data!r}" if data is not None else ""
    return f"requests.request({method!r}, {url!r}, headers={headers!r}{d})"


def main():
    parser = argparse.ArgumentParser(prog="curl-to-requests.py")
    parser.add_argument("--fetch", action="store_true",
                        help="parse fetch instead of curl")
    subs = parser.add_subparsers(title="subcommands", dest="command")
    subs.required = True
    sub_exec = subs.add_parser("exec", help="execute the request")
    sub_exec.add_argument("-v", "--verbose", action="store_true")
    sub_code = subs.add_parser("code", help="print the Python code")
    args = parser.parse_args()
    command = sys.stdin.read()
    method, url, headers, data, ign = \
        fetch_to_requests(command) if args.fetch else curl_to_requests(command)
    for arg in ign:
        print(f"Warning: ignoring {arg}", file=sys.stderr)
    if args.command == "code":
        print(to_python_code(method, url, headers, data))
    elif args.command == "exec":
        if args.verbose:
            print(f"{method} {url} headers={headers} data={data}", file=sys.stderr)
        kwargs = dict(headers=headers)
        if data is not None:
            kwargs["data"] = data
        r = requests.request(method, url, **kwargs)
        r.raise_for_status()
        print(r.text, end="")


if __name__ == "__main__":
    main()

# vim: set tw=80 sw=4 sts=4 et fdm=marker :
