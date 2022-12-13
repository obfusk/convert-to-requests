<!-- SPDX-FileCopyrightText: 2022 FC Stegerman <flx@obfusk.net> -->
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

[![GitHub Release](https://img.shields.io/github/release/obfusk/convert-to-requests.svg?logo=github)](https://github.com/obfusk/convert-to-requests/releases)
[![PyPI Version](https://img.shields.io/pypi/v/convert-to-requests.svg)](https://pypi.python.org/pypi/convert-to-requests)
[![Python Versions](https://img.shields.io/pypi/pyversions/convert-to-requests.svg)](https://pypi.python.org/pypi/convert-to-requests)
[![CI](https://github.com/obfusk/convert-to-requests/workflows/CI/badge.svg)](https://github.com/obfusk/convert-to-requests/actions?query=workflow%3ACI)
[![GPLv3+](https://img.shields.io/badge/license-GPLv3+-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html)

<!--
<a href="https://repology.org/project/convert-to-requests/versions">
  <img src="https://repology.org/badge/vertical-allrepos/convert-to-requests.svg?header="
    alt="Packaging status" align="right" />
</a>

<a href="https://repology.org/project/python:convert-to-requests/versions">
  <img src="https://repology.org/badge/vertical-allrepos/python:convert-to-requests.svg?header="
    alt="Packaging status" align="right" />
</a>
-->

# convert-to-requests

## convert curl/fetch command to python requests

Parse `curl` command (from "copy to cURL") or (w/ `--fetch`) `fetch` code (from
"copy to fetch") from stdin and either execute the request using
`requests.request()` (`exec` subcommand) or print Python code to do so (`code`
subcommand).

### curl

Get the code:

```bash
$ convert-to-requests code --pretty <<< "curl 'https://obfusk.ch' -H 'User-Agent: Mozilla/5.0'"
requests.request('GET', 'https://obfusk.ch', headers={
    'User-Agent': 'Mozilla/5.0'
})
```

Execute the request:

```bash
$ convert-to-requests exec -v <<< "curl 'https://obfusk.ch' -H 'User-Agent: Mozilla/5.0'" | head -2
GET https://obfusk.ch headers={'User-Agent': 'Mozilla/5.0'} data=None
<!DOCTYPE html>
<html lang="en">
```

POST works too:

```bash
$ convert-to-requests code <<< "curl 'https://example.com' -H 'User-Agent: Mozilla/5.0' -H 'Accept: application/json' -X POST --data-raw foo"
requests.request('POST', 'https://example.com', headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}, data=b'foo')
```

### fetch

```bash
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
```

## Python API

```python
>>> from convert_to_requests import curl_to_requests, to_python_code
>>> req = curl_to_requests(r"curl 'https://example.com' -X POST --data-raw $'\'foo\''", parse_bash_strings=True)
>>> req
RequestData(method='POST', url='https://example.com', headers={}, data=b"'foo'", ignored=[])
>>> print(to_python_code(req.method, req.url, req.headers, req.data))
requests.request('POST', 'https://example.com', headers={}, data=b"'foo'")
>>> print(req.code())               # shorter alternative
requests.request('POST', 'https://example.com', headers={}, data=b"'foo'")
```

```python
>>> import requests
>>> r = requests.request(req.method, req.url, headers=req.headers, data=req.data)
>>> r.raise_for_status()
>>> print(r.text, end="")
[...]
>>> print(req.exec().text, end="")  # shorter alternative
[...]
```

```python
>>> from convert_to_requests import fetch_to_requests, to_python_code
>>> req = fetch_to_requests('''fetch("https://example.com", {"headers": {}, "method": "POST", "body": "'foo'"});''')
>>> req
RequestData(method='POST', url='https://example.com', headers={}, data=b"'foo'", ignored=[])
>>> print(to_python_code(req.method, req.url, req.headers, req.data))
requests.request('POST', 'https://example.com', headers={}, data=b"'foo'")
```

```python
>>> from convert_to_requests import parse_dollar_string
>>> parse_dollar_string(r"$'\'foo\''")
("'foo'", '')
```

## CAVEATS

### curl

Firefox and Chromium produce e.g. `--data-raw $'\'foo\''` when the POST data
contains single quotes.  Unfortunately, `shlex` can't parse this kind of
`bash`-style string.  Use `--parse-bash-strings` to (attempt to) parse these
properly.  Of course, manually rewriting to e.g. `--data-raw \''foo'\'` always
works.

### fetch

Unfortunately, "copy as fetch" doesn't include cookies ("copy as Node.js fetch"
does).

Chromium doesn't include a `User-Agent` header in either.

## Installing

### Using pip

```bash
$ pip install convert-to-requests
```

NB: depending on your system you may need to use e.g. `pip3 --user`
instead of just `pip`.

### From git

NB: this installs the latest development version, not the latest
release.

```bash
$ git clone https://github.com/obfusk/convert-to-requests.git
$ cd convert-to-requests
$ pip install -e .
```

NB: you may need to add e.g. `~/.local/bin` to your `$PATH` in order
to run `convert-to-requests`.

To update to the latest development version:

```bash
$ cd convert-to-requests
$ git pull --rebase
```

## Dependencies

* Python >= 3.8 + requests.

### Debian/Ubuntu

```bash
$ apt install python3-requests
```

## License

[![GPLv3+](https://www.gnu.org/graphics/gplv3-127x51.png)](https://www.gnu.org/licenses/gpl-3.0.html)

<!-- vim: set tw=70 sw=2 sts=2 et fdm=marker : -->
