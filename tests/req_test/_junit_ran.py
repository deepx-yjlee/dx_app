#!/usr/bin/env python3
"""Did a pytest run actually execute anything?

``pytest`` exits 0 both when tests really passed and when every case was
skipped -- including the degenerate case where ``parametrize`` got an empty
list, which yields a single ``[NOTSET] SKIPPED (got empty parameter set)``
placeholder.  A req_test runner that judges on the exit code alone therefore
reports ``[PASS]`` for a sweep in which nothing ran at all.

Read the JUnit XML and report the number of cases that genuinely executed:

    exit 0   at least one case passed  -> the caller may report PASS
    exit 77  nothing executed          -> the caller must report SKIP
    exit 1   XML missing/unparsable    -> the caller must not claim PASS

Usage:  _junit_ran.py <junit-xml-path>
"""

import sys
import xml.etree.ElementTree as ET

EXIT_RAN = 0
EXIT_NOTHING_RAN = 77
EXIT_UNKNOWN = 1


def executed_count(xml_path: str) -> int:
    """Return the count of cases that ran to a real verdict (i.e. passed)."""
    root = ET.parse(xml_path).getroot()
    # pytest >= 5 wraps <testsuite> in <testsuites>; older emits it at the root.
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    if not suites:
        raise ValueError(f"no <testsuite> element in {xml_path}")

    def attr(suite, key):
        return int(suite.get(key, "0"))

    return sum(
        attr(s, "tests") - attr(s, "skipped") - attr(s, "errors") - attr(s, "failures")
        for s in suites
    )


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return EXIT_UNKNOWN
    try:
        ran = executed_count(argv[1])
    except (OSError, ET.ParseError, ValueError) as exc:
        print(f"[_junit_ran] cannot read {argv[1]}: {exc}", file=sys.stderr)
        return EXIT_UNKNOWN
    print(f"[_junit_ran] executed={ran}")
    return EXIT_RAN if ran > 0 else EXIT_NOTHING_RAN


if __name__ == "__main__":
    sys.exit(main(sys.argv))
