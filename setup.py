from pathlib import Path
import setuptools

__version__ = "0.1.1"

info = Path(__file__).with_name("README.md").read_text(encoding = "utf8")

setuptools.setup(
    name              = "convert-to-requests",
    url               = "https://github.com/obfusk/convert-to-requests",
    description       = "convert curl/fetch command to python requests",
    long_description  = info,
    long_description_content_type = "text/markdown",
    version           = __version__,
    author            = "FC Stegerman",
    author_email      = "flx@obfusk.net",
    license           = "GPLv3+",
    classifiers       = [
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Telecommunications Industry",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX :: Linux",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
      # "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Software Development",
        "Topic :: Utilities",
    ],
    keywords          = "curl fetch requests",
    entry_points      = dict(console_scripts = ["convert-to-requests = convert_to_requests:main"]),
    packages          = ["convert_to_requests"],
    package_data      = dict(convert_to_requests = ["py.typed"]),
    python_requires   = ">=3.8",
    install_requires  = ["requests"],
)
