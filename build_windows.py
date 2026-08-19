"""
Build script for the Windows GitHub Actions runner.

CadQuery pulls in several compiled/DLL-heavy dependencies (OCP - the
OpenCascade bindings, casadi - a solver library CadQuery imports at
top level even if you never use cq.Assembly, ezdxf, etc). PyInstaller's
default single-file (--onefile) mode is unreliable at locating sibling
DLLs for packages like these, and UPX compression can corrupt some of
those DLLs outright. This script:

  - builds in --onedir mode (exe + all DLLs sit together in one folder,
    which lets Windows' normal "look next to the exe" DLL search find
    everything reliably)
  - disables UPX compression (--noupx)
  - runs --collect-all (submodules + data + binaries) and --copy-metadata
    for every package in the CadQuery dependency chain known to cause
    exactly this kind of "DLL load failed" / "No module named X._x" error
    when frozen
  - additionally collects any "<package>.libs" sibling folder some of
    these ship (a common pattern for wheels that vendor their own DLLs),
    when one is actually importable, so we don't pass a bogus argument
    for packages that don't have one
"""

import importlib.util
import subprocess
import sys

# Packages known to need full collection when freezing CadQuery apps.
COLLECT_ALL = [
    "cadquery",
    "OCP",
    "casadi",
    "ezdxf",
    "multimethod",
    "nptyping",
    "typish",
    "numpy",
    "scipy",
]

COPY_METADATA = [
    "cadquery",
    "OCP",
    "casadi",
    "ezdxf",
    "multimethod",
    "nptyping",
    "typish",
]


def module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def main() -> None:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--noupx",
        "--name", "PelicanOrganizer",
    ]

    for pkg in COLLECT_ALL:
        if module_available(pkg):
            args += ["--collect-all", pkg]
        else:
            print(f"[build] skipping --collect-all {pkg} (not installed)")

    for pkg in COPY_METADATA:
        if module_available(pkg):
            args += ["--copy-metadata", pkg]

    # Sibling ".libs" folders some delvewheel-repaired wheels ship
    # (e.g. casadi.libs) that carry DLLs not reached by collect-all
    # on the base package name.
    for extra in ("casadi.libs", "OCP.libs", "cadquery.libs", "scipy.libs", "numpy.libs"):
        if module_available(extra):
            args += ["--collect-all", extra]
            print(f"[build] also collecting {extra}")

    args.append("organizer_app.py")

    print("[build] Running:", " ".join(args))
    subprocess.run(args, check=True)


if __name__ == "__main__":
    main()
