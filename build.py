"""Genera PolyCutter-X.Y.Z.zip listo para instalar en Blender."""

import importlib.util
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
PKG = ROOT / "PolyCutter"


def version():
    spec = importlib.util.spec_from_file_location("pc_config", PKG / "config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.VERSION


def main():
    out = ROOT / ("PolyCutter-%d.%d.%d.zip" % version())
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(PKG.rglob("*.py")):
            if "__pycache__" in f.parts:
                continue
            z.write(f, "PolyCutter/" + str(f.relative_to(PKG)))
    print("Zip generado:", out)


if __name__ == "__main__":
    main()
