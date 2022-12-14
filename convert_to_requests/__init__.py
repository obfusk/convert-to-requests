#!/usr/bin/python3
# SPDX-FileCopyrightText: 2022 FC Stegerman <flx@obfusk.net>
# SPDX-License-Identifier: GPL-3.0-or-later

r"""
convert curl/fetch command to python requests

Parse curl command (from "copy to cURL") or (w/ --fetch) fetch code (from "copy
to fetch") from stdin and either execute the request using requests.request()
(exec subcommand) or print Python code to do so (code subcommand).


CLI
===

$ convert-to-requests code --pretty <<< "curl 'https://obfusk.ch' -H 'User-Agent: Mozilla/5.0'"
requests.request('GET', 'https://obfusk.ch', headers={
    'User-Agent': 'Mozilla/5.0'
})

$ convert-to-requests exec -v <<< "curl 'https://obfusk.ch' -H 'User-Agent: Mozilla/5.0'" | head -2
GET https://obfusk.ch headers={'User-Agent': 'Mozilla/5.0'} data=None
<!DOCTYPE html>
<html lang="en">

$ convert-to-requests code <<< "curl 'https://example.com' -H 'User-Agent: Mozilla/5.0' -H 'Accept: application/json' -X POST --data-raw foo"
requests.request('POST', 'https://example.com', headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}, data=b'foo')

$ convert-to-requests --fetch code <<-END
fetch("https://example.com", {
  "headers": {
    "accept": "application/json"
  },
  "body": null,
  "method": "GET",
  "mode": "cors",
  "credentials": "omit"
});
END
Warning: ignoring mode=
Warning: ignoring credentials=
requests.request('GET', 'https://example.com', headers={'accept': 'application/json'})


API
===

>>> from convert_to_requests import curl_to_requests, to_python_code
>>> req = curl_to_requests(r"curl 'https://example.com' -X POST --data-raw $'\'foo\''")
>>> req
RequestData(method='POST', url='https://example.com', headers={}, data=b"'foo'", ignored=[])
>>> print(to_python_code(req.method, req.url, req.headers, req.data))
requests.request('POST', 'https://example.com', headers={}, data=b"'foo'")
>>> print(req.code())               # shorter alternative
requests.request('POST', 'https://example.com', headers={}, data=b"'foo'")

#>> import requests
#>> r = requests.request(req.method, req.url, headers=req.headers, data=req.data)
#>> r.raise_for_status()
#>> print(r.text, end="")
[...]
#>> print(req.exec().text, end="")  # shorter alternative
[...]

>>> from convert_to_requests import fetch_to_requests, to_python_code
>>> req = fetch_to_requests('''fetch("https://example.com", {"headers": {}, "method": "POST", "body": "'foo'"});''')
>>> req
RequestData(method='POST', url='https://example.com', headers={}, data=b"'foo'", ignored=[])
>>> print(to_python_code(req.method, req.url, req.headers, req.data))
requests.request('POST', 'https://example.com', headers={}, data=b"'foo'")

>>> from convert_to_requests import parse_dollar_string
>>> parse_dollar_string(r"$'\'foo\''")
("'foo'", '')

"""

import argparse
import json
import pprint
import re
import sys

from collections import namedtuple
from typing import Callable, Dict, Optional, Tuple

import requests

__version__ = "0.2.0"
NAME = "convert-to-requests"
DESC = """
Parse curl command (from "copy to cURL") or (w/ --fetch) fetch code (from "copy
to fetch") from stdin and either execute the request using requests.request()
(exec subcommand) or print Python code to do so (code subcommand).
"""[1:-1]

METHODS = ("GET", "OPTIONS", "HEAD", "POST", "PUT", "PATCH", "DELETE")

ESC = {
    "a": "\a", "b": "\b", "e": "\027", "E": "\027", "f": "\f", "n": "\n",
    "r": "\r", "t": "\t", "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?"
}
OCT = "01234567"
HEX = "0123456789abcdef"


class RequestData(namedtuple("_RequestData", ("method", "url", "headers", "data", "ignored"))):
    """Request data (method, url, headers, data, ignored opts/args)."""

    def exec(self, raise_for_status: bool = True) -> requests.Response:
        """Execute request using perform_request()."""
        return perform_request(*self[:-1], raise_for_status=raise_for_status)

    def code(self, pretty: bool = False) -> str:
        """Convert request to Python code using to_python_code()."""
        return to_python_code(*self[:-1], pretty=pretty)


# FIXME: use argparse?!
def curl_to_requests(command: str) -> RequestData:
    r"""
    Parse curl command from "copy as cURL" (Firefox, Chromium).

    Returns RequestData.

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
    cmd, url, *curl = split_curl_command(command)
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


def split_curl_command(command: str) -> Tuple[str, ...]:
    r"""
    Split curl command like shlex.split(), but with support for bash-style $''
    strings and specifically tailored for the curl commands produced by
    Firefox/Chromium, not generic shell-like syntax.

    >>> command = r'''
    ... curl 'https://example.com' -H $'foo: \'bar\'' -X POST \
    ... --data-raw $'\'foo\''
    ... '''
    >>> split_curl_command(command)
    ('curl', 'https://example.com', '-H', "foo: 'bar'", '-X', 'POST', '--data-raw', "'foo'")

    """
    tokens = []
    s = (command.rstrip() + " ").lstrip()
    i, n = 0, len(s)

    def read_token(f: Callable[[str], bool]) -> str:
        nonlocal i
        token = ""
        while i < n and not f(s[i]):
            token += s[i]
            i += 1
        return token

    while i < n:
        if s[i:i + 2] == "\\\n":
            i += 2
        elif s[i] == "#":
            break
        elif s[i] == "'":
            i += 1
            t = read_token(lambda c: c == "'")
            if not (i < n and s[i] == "'"):
                raise ValueError("Unterminated single-quoted string")
            i += 1
            if i < n and not s[i].isspace():
                raise ValueError("Expected whitespace after single-quoted string")
            tokens.append(t)
        elif s[i:i + 2] == "$'":
            t, s = parse_dollar_string(s[i:])
            i, n = 0, len(s)
            if i < n and not s[i].isspace():
                raise ValueError("Expected whitespace after $'' string")
            tokens.append(t)
        else:
            t = read_token(str.isspace)
            if "'" in t:
                raise ValueError("Expected whitespace before single-quoted string")
            if '"' in t:
                raise ValueError("Unsupported double-quoted string")
            tokens.append(t)
        s = s[i:].lstrip()
        i, n = 0, len(s)
    return tuple(tokens)


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
    r"""
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
    headers = args.pop("headers", {})
    data = args.pop("body", None)
    if data is not None:
        data = data.encode()
    if referrer := args.pop("referrer", None):
        headers["referer"] = referrer   # not a typo
    if referrer_policy := args.pop("referrerPolicy", None):
        headers["referrer-policy"] = referrer_policy
    assert method in METHODS
    return RequestData(method, url, headers, data, [f"{k}=" for k in args])


def curl_to_python_code(command: str, pretty: bool = False) -> str:
    r"""
    Convert curl command to Python code.

    >>> command = r'''
    ... curl 'https://example.com' -H 'User-Agent: Mozilla/5.0'
    ... '''
    >>> print(curl_to_python_code(command))
    requests.request('GET', 'https://example.com', headers={'User-Agent': 'Mozilla/5.0'})
    >>> print(curl_to_python_code(command, pretty=True))
    requests.request('GET', 'https://example.com', headers={
        'User-Agent': 'Mozilla/5.0'
    })
    >>> command = r'''
    ... curl 'https://example.com' -H 'User-Agent: Mozilla/5.0'
    ... -H 'Accept: application/json' -X POST --data-raw foo
    ... '''
    >>> print(curl_to_python_code(command))
    requests.request('POST', 'https://example.com', headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}, data=b'foo')
    >>> print(curl_to_python_code(command, pretty=True))
    requests.request('POST', 'https://example.com', headers={
        'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'
    }, data=b'foo')
    >>> command = command.replace("Mozilla/5.0", " ".join(["spam"] * 16))
    >>> command = command.replace("foo", "data" * 32)
    >>> print(curl_to_python_code(command, pretty=True))
    requests.request('POST', 'https://example.com', headers={
        'User-Agent': 'spam spam spam spam spam spam spam spam spam spam spam spam '
                      'spam spam spam spam',
        'Accept': 'application/json',
    }, data=(
        b'datadatadatadatadatadatadatadatadatadatadatadatadatadatadatadatadatadatadata'
        b'datadatadatadatadatadatadatadatadatadatadatadatadata'
    ))
    >>> command = r'''
    ... curl 'https://example.com' --data-raw foo
    ... '''
    >>> print(curl_to_python_code(command, pretty=True))
    requests.request('POST', 'https://example.com', headers={}, data=b'foo')
    >>> command = command.replace("foo", "data" * 8)
    >>> print(curl_to_python_code(command, pretty=True))
    requests.request('POST', 'https://example.com', headers={}, data=(
        b'datadatadatadatadatadatadatadata'
    ))

    """
    return to_python_code(*curl_to_requests(command)[:-1], pretty=pretty)


def fetch_to_python_code(command: str, pretty: bool = False) -> str:
    """Convert fetch code to Python code."""
    return to_python_code(*fetch_to_requests(command)[:-1], pretty=pretty)


def to_python_code(method: str, url: str, headers: Dict[str, str],
                   data: Optional[bytes] = None, pretty: bool = False) -> str:
    """Create Python code for requests.request() call."""
    if pretty and headers:
        h = pprint.pformat(headers, indent=4, sort_dicts=False)
        a = "\n " if "\n" in h else "\n    "
        b = ",\n" if "\n" in h else "\n"
        h = h[0] + a + h[1:-1] + b + h[-1]
    else:
        h = repr(headers)
    s = f"requests.request({method!r}, {url!r}, headers={h}"
    t = f", data={data!r})" if data is not None else ")"
    if pretty and data is not None:
        if len(s.rsplit("\n", 1)[-1]) + len(t) > 80:
            t = pprint.pformat(data).replace("\n", "\n   ")
            t = ", data=(\n    " + (t[1:-1] if "\n" in t else t) + "\n))"
    return s + t


def perform_request(method: str, url: str, headers: Dict[str, str],
                    data: Optional[bytes] = None,
                    raise_for_status: bool = True) -> requests.Response:
    r = requests.request(method, url, headers=headers, data=data)   # pylint: disable=W3101
    if raise_for_status:
        r.raise_for_status()
    return r


def main() -> None:
    parser = argparse.ArgumentParser(prog=NAME, description=DESC)
    parser.add_argument("--fetch", action="store_true",
                        help="parse fetch instead of curl; NB: see CAVEATS")
    parser.add_argument("--version", action="version",
                        version=f"{NAME}, version {__version__}")
    subs = parser.add_subparsers(title="subcommands", dest="command")
    subs.required = True
    sub_exec = subs.add_parser("exec", help="execute the request")
    sub_exec.add_argument("-v", "--verbose", action="store_true")
    sub_code = subs.add_parser("code", help="print the Python code")
    sub_code.add_argument("--pretty", action="store_true", help="pretty-print")
    args = parser.parse_args()
    command = sys.stdin.read()
    req = fetch_to_requests(command) if args.fetch else curl_to_requests(command)
    for arg in req.ignored:
        print(f"Warning: ignoring {arg}", file=sys.stderr)
    if args.command == "code":
        print(req.code(pretty=args.pretty))
    elif args.command == "exec":
        if args.verbose:
            print(f"{req.method} {req.url} headers={req.headers} data={req.data}", file=sys.stderr)
        print(req.exec().text, end="")


if __name__ == "__main__":
    main()

# vim: set tw=80 sw=4 sts=4 et fdm=marker :
