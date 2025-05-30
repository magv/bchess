import enscons
import os
import os.path
import packaging.tags
import platform
import subprocess
import sys
import toml

def get_universal_platform_tag():
    """Return the wheel tag for universal Python 3, but specific platform."""
    tag = next(packaging.tags.sys_tags())
    return f"py3-none-{tag.platform}"

def DirectoryFiles(dir):
    """Return a File() for each file in and under a directory."""
    files = []
    for root, dirnames, filenames in os.walk(dir):
        files += File(sorted(filenames), root)
    return files

pyproject = toml.load("pyproject.toml")

env = Environment(
    tools = ["default", "packaging", enscons.generate],
    PACKAGE_METADATA = pyproject["project"],
    WHEEL_TAG = get_universal_platform_tag(),
    ENV = os.environ
)

generated = []

def build_sqlite(target, source, env):
    import sqlite3
    with sqlite3.connect(target[0].get_path()) as db:
        for src in source:
            with open(src.get_path(), "r") as f:
                sql = f.read()
            db.executescript(sql)
        db.executescript("reindex;")
        db.executescript("vacuum;")

generated += \
    env.Command("bchess/data/openings.sqlite", ["openings.sql", "evaluations.sql"], build_sqlite)

arch = (platform.machine(), 64 if sys.maxsize > 2**32 else 32)
stockfish_arch = \
    "x86-64" if arch in (("x86_64", 64), ("x64", 64)) else \
    "x86-32" if arch in (("x86_64", 32), ("i686", 32)) else \
    "ppc-64" if arch in (("ppc64", 64), ("ppc", 64)) else \
    "ppc-32" if arch in (("ppc", 32),) else \
    "armv7" if arch in (("armv7l", 32),) else \
    "armv8" if arch in (("armv8b", 64), ("armv8l", 64)) else \
    "general-64" if arch[1] == 64 else \
    "general-32"

generated += \
    env.Command("bchess/data/stockfish", ["build/Stockfish-sf_17.1.tar.gz"], """
        cd build && \
        tar vxf Stockfish-sf_17.1.tar.gz && \
        cd Stockfish-sf_17.1/src && \
        sed -e 's/^net:/net:\\n\\ttrue\\n\\nxnet:/' -i.bak Makefile && \
        make build ARCH=$ARCH EXTRACXXFLAGS=-DNNUE_EMBEDDING_OFF=1 -j4 && \
        strip stockfish
        cp build/Stockfish-sf_17.1/src/stockfish $TARGET
        rm -rf build/Stockfish-sf_17.1
    """, ARCH=stockfish_arch)

lczero_common_tag = "55e1b382efadd57903e37f2a2e29caef3ea85799"

generated += \
    env.Command("bchess/data/lc0", ["build/lc0-0.31.2.tar.gz", "build/lczero-common.tar.gz"], """
        which meson
        which ninja
        cd build && \
        tar vxf lc0-0.31.2.tar.gz && \
        tar vxf lczero-common.tar.gz && \
        cd lc0-0.31.2 && \
        cp -a ../lczero-common-${LCZERO_COMMON_TAG}/. libs/lczero-common && \
        cp -a ../lc0deps/* subprojects/packagefiles && \
        sed -i.bak -E '/^[a-z]*_url/d' subprojects/*wrap && \
        sed -i.bak -e 's/>=0.52/>=0.55/' -e "s/'eigen3'/'eigen3-xxx'/" -e "s/'zlib'/'zlib-xxx'/" meson.build && \
        ./build.sh minsize \
            --auto-features disabled \
            --default-library static \
            -Dblas=true \
            -Dcudnn=false \
            -Dispc=false \
            -Dcudnn=false \
            -Dplain_cuda=false \
            -Dopencl=false \
            -Ddx=false \
            -Dtensorflow=false \
            -Dopenblas=false \
            -Dmkl=false \
            -Ddnnl=false \
            -Daccelerate=false \
            -Dpopcnt=false \
            -Dpext=false \
            -Dneon=false \
            -Dgtest=false \
            -Dembed=false \
            -Dnvcc_ccbin=false && \
        strip build/minsize/lc0
        cp build/lc0-0.31.2/build/minsize/lc0 $TARGET
    """, LCZERO_COMMON_TAG=lczero_common_tag)

File("PKG-INFO")
#source = DirectoryFiles("bchess") + File(["bchess_data/__init__.py"])

def vcs_files(*paths):
    if os.path.exists(".hg"):
        return File(sorted(subprocess.check_output(["hg", "files", *paths], encoding="utf8").splitlines()))
    if os.path.exists(".git"):
        return File(sorted(subprocess.check_output(["git", "ls-files", *paths], encoding="utf8").splitlines()))
    raise ValueError("Neither .hg nor .git directory is present")

def vcs_commit():
    if os.path.exists(".hg"):
        return subprocess.check_output(["hg", "id", "-i"], encoding="utf8").strip()
    if os.path.exists(".git"):
        return subprocess.check_output(["git", "rev-parse", "HEAD"], encoding="utf8").strip()
    raise ValueError("Neither .hg nor .git directory is present")

if os.path.exists(".hg") or os.path.exists(".git"):
    generated_src = []

    generated_src += env.Command("build/Stockfish-sf_17.1.tar.gz", [],
        "wget -O $TARGET 'https://github.com/official-stockfish/Stockfish/archive/refs/tags/sf_17.1.tar.gz'")

    generated_src += env.Command("build/lczero-common.tar.gz", [],
        "wget -O $TARGET 'https://github.com/LeelaChessZero/lczero-common/archive/${LCZERO_COMMON_TAG}.tar.gz'",
        LCZERO_COMMON_TAG=lczero_common_tag)

    generated_src += env.Command("build/lc0-0.31.2.tar.gz", [],
        "wget -O $TARGET 'https://github.com/LeelaChessZero/lc0/archive/refs/tags/v0.31.2.tar.gz'")

    generated_src += env.Command("build/lc0deps/eigen-3.4.0.tar.bz2", [],
        "wget -O $TARGET 'https://gitlab.com/libeigen/eigen/-/archive/3.4.0/eigen-3.4.0.tar.bz2'")

    generated_src += env.Command("build/lc0deps/eigen_3.4.0-1_patch.zip", [],
        "wget -O $TARGET 'https://wrapdb.mesonbuild.com/v2/eigen_3.4.0-1/get_patch'")

    generated_src += env.Command("build/lc0deps/zlib-1.2.11.tar.gz", [],
        "wget -O $TARGET 'http://zlib.net/fossils/zlib-1.2.11.tar.gz'")

    generated_src += env.Command("build/lc0deps/zlib-1.2.11-4-wrap.zip", [],
        "wget -O $TARGET 'https://wrapdb.mesonbuild.com/v1/projects/zlib/1.2.11/4/get_zip'")

    generated_src += env.Command("bchess/data/default.nnue", [],
        "wget -O $TARGET 'https://tests.stockfishchess.org/api/nn/nn-1c0000000000.nnue'")

    generated_src += env.Command("bchess/data/default.small.nnue", [],
        "wget -O $TARGET 'https://tests.stockfishchess.org/api/nn/nn-37f18f62d772.nnue'")

    generated_src += env.Command("bchess/data/maia-1100.pb.gz", [],
        "wget -O $TARGET 'https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1100.pb.gz'")

    generated_src += env.Command("bchess/data/maia-1300.pb.gz", [],
        "wget -O $TARGET 'https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1300.pb.gz'")

    generated_src += env.Command("bchess/data/maia-1500.pb.gz", [],
        "wget -O $TARGET 'https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1500.pb.gz'")

    generated_src += env.Command("bchess/data/maia-1700.pb.gz", [],
        "wget -O $TARGET 'https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1700.pb.gz'")

    generated_src += env.Command("bchess/data/maia-1900.pb.gz", [],
        "wget -O $TARGET 'https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1900.pb.gz'")

    generated_src += env.Command("bchess/data/tinygyal-8.pb.gz", [],
        "wget -O $TARGET 'https://github.com/dkappe/leela-chess-weights/files/4432261/tinygyal-8.pb.gz'")

    generated_src += env.Command("bchess/data/meangirl-8.pb.gz", [],
        "wget -O $TARGET 'https://github.com/dkappe/leela-chess-weights/releases/download/mean-girl-8/meangirl-8.pb.gz'")

    commit = vcs_commit()
    generated_src += env.Textfile(target="bchess/__init__.py", source=[
        f'__version__ = "{pyproject["project"]["version"]}"',
        f'__commit__ = "{commit}"'
    ])
    AlwaysBuild("bchess/__init__.py")

    source = vcs_files("bchess")
else:
    # Hackety hack! We are in a source dist, and because SCons
    # can't keep itself from rebuilding every generated file if
    # .sconsign.dblite file is gone (i.e. in a source dist), we
    # can't let it know that there are generated source files at all!
    #
    # Note that if some unlucky person downloads a source
    # tarball without a proper VCS repository (e.g. from github
    # releases), we'll also be in this branch, and the build won't
    # work. Solution? Ban unlucky people.
    generated_src = []
    source = DirectoryFiles("bchess")
    source = [file for file in DirectoryFiles("bchess") if file not in generated]

platformlib = env.Whl("platlib", source + generated, root="")
bdist = env.WhlFile(source=platformlib)

sdist = env.SDist(source=FindSourceFiles() + generated_src)

env.Alias("sdist", sdist)
env.Alias("bdist", bdist)
env.Alias("build", generated_src + generated)
env.Default(sdist + ["build"])
