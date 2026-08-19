"""
Replace the real `casadi` package with a tiny inert stub before freezing.

Why: CadQuery imports casadi unconditionally at package-import time
(cadquery/occ_impl/solver.py -> "import casadi as ca"), even though
casadi is only actually *used* by cq.Assembly's constraint solver. This
app only builds cq.Workplane geometry and never touches cq.Assembly, so
none of casadi's code ever runs - but merely "import cadquery" still
drags it in.

The real casadi wheel is a ~50MB compiled solver bundling dozens of
interdependent DLLs (Ipopt, MUMPS, BLAS/LAPACK, its own SWIG-generated
_casadi extension, ...). That combination is what PyInstaller keeps
failing to freeze correctly ("DLL load failed while importing
_casadi") - onefile vs onedir, --collect-all, --copy-metadata, none of
it reliably reconstructs casadi's exact DLL search-path expectations
inside a frozen bundle.

Since nothing in this app ever calls into casadi, the simplest fix is
to not ship it at all: swap the installed `casadi` package for a stub
that satisfies every way CadQuery imports it -
  - cadquery/occ_impl/solver.py:  import casadi as ca      (eager)
  - cadquery/occ_impl/nurbs.py:   from casadi import ldl, ... (lazy,
    only reached if something imports cadquery.vis - this app doesn't)
without shipping any of its 50MB of compiled solver code.

Every attribute access on the stub (ca.Opti, ca.MX, ca.DM, ...) returns
another stub object, which is enough for cadquery's module-level type
annotations and function bodies to import cleanly. If cq.Assembly
constraint solving is ever actually needed, delete this script's call
from the workflow, put "casadi" back as an explicit requirement, and
go back to bundling the real package.
"""

import importlib.util
import shutil
from pathlib import Path

STUB_SOURCE = '''"""Inert stand-in for casadi - see stub_casadi.py in the build repo for why."""


class _Stub:
    def __call__(self, *args, **kwargs):
        return _Stub()

    def __getattr__(self, item):
        return _Stub()

    def __getitem__(self, item):
        return _Stub()


def __getattr__(name):
    # Covers both "import casadi as ca" (attribute access happens later,
    # e.g. ca.Opti) and "from casadi import ldl, DM, ..." (triggers this
    # immediately per name via PEP 562 module __getattr__).
    return _Stub()
'''


def main() -> None:
    spec = importlib.util.find_spec("casadi")
    if spec is None or not spec.submodule_search_locations:
        print("[stub_casadi] casadi is not installed - nothing to stub, skipping")
        return

    casadi_dir = Path(list(spec.submodule_search_locations)[0])
    print(f"[stub_casadi] removing real casadi package at {casadi_dir}")
    shutil.rmtree(casadi_dir)

    casadi_dir.mkdir(parents=True)
    (casadi_dir / "__init__.py").write_text(STUB_SOURCE, encoding="utf-8")
    print(f"[stub_casadi] wrote inert stub casadi package to {casadi_dir}")


if __name__ == "__main__":
    main()
