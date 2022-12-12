#!/usr/bin/python3
# SPDX-FileCopyrightText: 2022 FC Stegerman <flx@obfusk.net>
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import json
import re
import shlex
import sys

from collections import namedtuple
from typing import Dict, Optional, Tuple

import requests

METHODS = ("GET", "OPTIONS", "HEAD", "POST", "PUT", "PATCH", "DELETE")

DESC = """
Parse curl command (from "copy to cURL") or (w/ --fetch) fetch code (from "copy
to fetch") from stdin and either execute the request using requests.request()
(exec subcommand) or print Python code to do so (code subcommand).
"""[1:-1]

ESC = {
    "a": "\a", "b": "\b", "e": "\027", "E": "\027", "f": "\f", "n": "\n",
    "r": "\r", "t": "\t", "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?"
}
OCT = "01234567"
HEX = "0123456789abcdef"

RequestData = namedtuple("RequestData", ("method", "url", "headers", "data", "ignored"))


# FIXME: use argparse?!
def curl_to_requests(command: str, parse_bash_strings: bool = False) -> RequestData:
    r"""
    Parse curl command from "copy as cURL" (Firefox, Chromium).

    Returns RequestData.

    CAVEATS
    -------

    Firefox and Chromium produce e.g. --data-raw $'\'foo\'' when the POST data
    contains single quotes.  Unfortunately, shlex can't parse this kind of
    bash-style string.  Use parse_bash_strings=True to (attempt to) parse these
    properly.  Of course, manually rewriting to e.g. --data-raw \''foo'\' always
    works.

    Examples
    --------

    >>> command = r'''
    ... curl 'https://example.com' -H 'User-Agent: Mozilla/5.0' --compressed
    ... '''
    >>> curl_to_requests(command)
    RequestData(method='GET', url='https://example.com', headers={'User-Agent': 'Mozilla/5.0'}, data=None, ignored=['--compressed'])
    >>> command = r'''
    ... curl 'https://example.com' -H 'User-Agent: Mozilla/5.0'
    ... -H 'Accept: application/json' -X POST --data-raw foo
    ... '''
    >>> curl_to_requests(command)
    RequestData(method='POST', url='https://example.com', headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}, data=b'foo', ignored=[])

    """
    method, headers, data, ignored = None, {}, None, []
    if parse_bash_strings:
        command, data = _bash_string_data(command)
    cmd, url, *curl = [x for x in shlex.split(command) if x != "\n"]
    assert cmd == "curl"
    i, n = 0, len(curl)
    while i < n:
        if curl[i] == "-H":
            k, v = curl[i + 1].split(": ", 1)
            headers[k] = v
            i += 1
        elif curl[i] == "-X":
            method = curl[i + 1]
            assert method in METHODS
            i += 1
        elif curl[i] == "--data-raw":
            data = curl[i + 1].encode()
            i += 1
        elif curl[i] == "--compressed":
            ignored.append(curl[i])
        else:
            raise NotImplementedError(f"Unknown curl argument: {curl[i]}")
        i += 1
    if method is None:
        method = "POST" if data else "GET"
    return RequestData(method, url, headers, data, ignored)


def _bash_string_data(command: str) -> Tuple[str, Optional[bytes]]:
    if (s := " --data-raw $'") in command:
        i = command.index(s)
        try:
            shlex.split(command[:i])
        except ValueError:
            pass
        else:
            data, rest = parse_dollar_string(command[i + s.index("$"):])
            return command[:i] + rest, data.encode()
    return command, None


def parse_dollar_string(s: str) -> Tuple[str, str]:
    r"""
    Parse bash-style $'' string (at start).

    Returns parsed_string, rest_of_input.

    >>> parse_dollar_string(r"$'\'foo\''")
    ("'foo'", '')
    >>> parse_dollar_string(r"$'\b\e\\\"\027\x20\u732b\cH' ...")
    ('\x08\x17\\"\x17 猫\x08', ' ...')
    >>> parse_dollar_string(r"$''")
    ('', '')
    >>> parse_dollar_string(r"$'\''")
    ("'", '')
    >>> tuple(parse_dollar_string(r"$'\x123'")[0])
    ('\x12', '3')
    >>> errors = []
    >>> for s in (r"$'", r"$'\'", "$'\\", r"$'\x'", r"$'\c'"):
    ...     try:
    ...         parse_dollar_string(r"$'")
    ...     except ValueError as e:
    ...         errors.append(str(e))
    >>> errors == ["Could not parse $'' string"] * 5
    True

    """
    t, i, n = "", 2, len(s)
    try:
        while i < n:
            c = s[i]
            i += 1
            if c == "'":
                return t, s[i:]
            elif c == "\\":
                d = s[i]
                i += 1
                if d in ESC:
                    t += ESC[d]
                elif d in OCT:
                    o = d
                    for _ in range(2):
                        if not s[i] in OCT:
                            break
                        o += s[i]
                        i += 1
                    t += chr(int(o, 8))
                elif d in "xuU":
                    if not s[i].lower() in HEX:
                        break
                    h = s[i]
                    i += 1
                    for _ in range(2 ** (1 + "xuU".index(d)) - 1):
                        if not s[i].lower() in HEX:
                            break
                        h += s[i]
                        i += 1
                    t += chr(int(h, 16))
                elif d == "c":
                    x = s[i]
                    i += 1
                    t += chr(ord(x) - 64)
                else:
                    break
            else:
                t += c
    except IndexError:
        pass
    raise ValueError("Could not parse $'' string")


def fetch_to_requests(command: str) -> RequestData:
    """
    Parse fetch code from "copy as fetch" (Firefox, Chromium) or "copy as
    Node.js fetch" (Chromium).

    Returns RequestData.

    CAVEATS
    -------

    Unfortunately, "copy as fetch" doesn't include cookies ("copy as Node.js
    fetch" does).

    Chromium doesn't include a User-Agent header in either.

    Examples
    --------

    >>> code = r'''
    ... fetch("https://example.com", {
    ...   "headers": {
    ...     "accept": "application/json"
    ...   },
    ...   "body": null,
    ...   "method": "GET",
    ...   "mode": "cors",
    ...   "credentials": "omit"
    ... });
    ... '''.strip()
    >>> fetch_to_requests(code)
    RequestData(method='GET', url='https://example.com', headers={'accept': 'application/json'}, data=None, ignored=['mode=', 'credentials='])
    >>> code = r'''
    ... await fetch("https://example.com", {
    ...     "credentials": "include",
    ...     "headers": {
    ...         "User-Agent": "Mozilla/5.0",
    ...         "Accept": "application/json"
    ...     },
    ...     "body": "foo",
    ...     "method": "POST",
    ...     "mode": "cors"
    ... });
    ... '''.strip()
    >>> fetch_to_requests(code)
    RequestData(method='POST', url='https://example.com', headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}, data=b'foo', ignored=['credentials=', 'mode='])

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
    return RequestData(method, url, headers, data, [f"{k}=" for k in args])


def curl_to_python_code(command: str) -> str:
    r"""
    Convert curl command to Python code.

    >>> command = r'''
    ... curl 'https://example.com' -H 'User-Agent: Mozilla/5.0'
    ... '''
    >>> print(curl_to_python_code(command))
    requests.request('GET', 'https://example.com', headers={'User-Agent': 'Mozilla/5.0'})
    >>> command = r'''
    ... curl 'https://example.com' -H 'User-Agent: Mozilla/5.0'
    ... -H 'Accept: application/json' -X POST --data-raw foo
    ... '''
    >>> print(curl_to_python_code(command))
    requests.request('POST', 'https://example.com', headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}, data=b'foo')

    """
    return to_python_code(*curl_to_requests(command)[:-1])


def fetch_to_python_code(command: str) -> str:
    """Convert fetch code to Python code."""
    return to_python_code(*fetch_to_requests(command)[:-1])


def to_python_code(method: str, url: str, headers: Dict[str, str],
                   data: Optional[bytes] = None) -> str:
    """Create Python code for requests.request() call."""
    d = f", data={data!r}" if data is not None else ""
    return f"requests.request({method!r}, {url!r}, headers={headers!r}{d})"


def main() -> None:
    parser = argparse.ArgumentParser(prog="convert-to-requests", description=DESC)
    parser.add_argument("--fetch", action="store_true",
                        help="parse fetch instead of curl; NB: see CAVEATS")
    parser.add_argument("--parse-bash-strings", action="store_true",
                        help="parse bash-style $'' string (as argument to --data-raw)")
    subs = parser.add_subparsers(title="subcommands", dest="command")
    subs.required = True
    sub_exec = subs.add_parser("exec", help="execute the request")
    sub_exec.add_argument("-v", "--verbose", action="store_true")
    subs.add_parser("code", help="print the Python code")
    args = parser.parse_args()
    command = sys.stdin.read()
    if args.fetch:
        req = fetch_to_requests(command)
    else:
        req = curl_to_requests(command, parse_bash_strings=args.parse_bash_strings)
    for arg in req.ignored:
        print(f"Warning: ignoring {arg}", file=sys.stderr)
    if args.command == "code":
        print(to_python_code(req.method, req.url, req.headers, req.data))
    elif args.command == "exec":
        if args.verbose:
            print(f"{req.method} {req.url} headers={req.headers} data={req.data}", file=sys.stderr)
        kwargs = dict(headers=req.headers)
        if req.data is not None:
            kwargs["data"] = req.data
        r = requests.request(req.method, req.url, **kwargs)     # pylint: disable=W3101
        r.raise_for_status()
        print(r.text, end="")


if __name__ == "__main__":
    main()

# vim: set tw=80 sw=4 sts=4 et fdm=marker :
