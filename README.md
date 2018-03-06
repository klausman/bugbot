# bugbot
Tools to work with Gentoo stabilisation requests on bugzilla. MIT licensed.

## getatoms
getatoms fetches atoms from a Gentoo stabilisation bug.

### Usage
```
usage: getatoms.py [-h] (--all-bugs | -b BUG | -s)
                   [--keywordreq | --stablereq] [-a ARCH] [-n]
                   [--no-sanity-check]

Get atoms from a stabilisation bug. This tool requires a Bugzilla API key to
operate, read from the envvar GETATOMS_APIKEY. Generate one at
https://bugs.gentoo.org/userprefs.cgi?tab=apikey If the variable
GETATOMS_TESTFILE is defined, the batch_stabilize-compatible output will be
written to that file.

optional arguments:
  -h, --help            show this help message and exit
  --all-bugs            process all bugs for the active architecture
  -b BUG, --bug BUG     bug to process
  -s, --security        fetch only security bugs
  --keywordreq          work on keywording bugs
  --stablereq           work on stabilisation bugs
  -a ARCH, --arch ARCH  target architecture (defaults to current)
  -n, --no-depends      exclude bugs that depend on other bugs
  --no-sanity-check     include bugs that are not marked as sanity checked
```

### Dependencies
* dev-python/requests
