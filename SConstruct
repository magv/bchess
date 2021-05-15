import enscons
import enscons.tags
import toml
import os
import os.path
import subprocess

def get_universal_platform_tag():
    """Return the wheel tag for universal Python 3, but specific platform."""
    tag = list(enscons.tags.sys_tags())[0]
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

generated_src = []

#generated_src += File(["PKG-INFO"])

generated_src += \
    env.Command("build/Stockfish-sf_13.tar.gz", [],
        "wget -O $TARGET 'https://github.com/official-stockfish/Stockfish/archive/refs/tags/sf_13.tar.gz'")

generated_src += \
    env.Command("build/lc0-0.27.0.tar.gz", [],
        "wget -O $TARGET 'https://github.com/LeelaChessZero/lc0/archive/refs/tags/v0.27.0.tar.gz'")

generated_src += \
    env.Command("build/nn-62ef826d1a6d.nnue", [],
        "wget -O $TARGET 'https://tests.stockfishchess.org/api/nn/nn-62ef826d1a6d.nnue'")

generated_src += \
    env.Command("bchess/data/maia-1100.pb.gz", [],
        "wget -O $TARGET 'https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1100.pb.gz'")

generated_src += \
    env.Command("bchess/data/maia-1300.pb.gz", [],
        "wget -O $TARGET 'https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1300.pb.gz'")

generated_src += \
    env.Command("bchess/data/maia-1500.pb.gz", [],
        "wget -O $TARGET 'https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1500.pb.gz'")

generated_src += \
    env.Command("bchess/data/maia-1700.pb.gz", [],
        "wget -O $TARGET 'https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1700.pb.gz'")

generated_src += \
    env.Command("bchess/data/maia-1900.pb.gz", [],
        "wget -O $TARGET 'https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1900.pb.gz'")

generated_src += \
    env.Command("bchess/data/tinygyal-8.pb.gz", [],
        "wget -O $TARGET 'https://github.com/dkappe/leela-chess-weights/files/4432261/tinygyal-8.pb.gz'")

generated = []

generated += \
    env.Command("bchess/data/openings.sqlite", "openings.sql",
        "sqlite3 $TARGET '.read $SOURCE' reindex vacuum")

generated += \
    env.InstallAs("bchess/data/default.nnue", "build/nn-62ef826d1a6d.nnue")

generated += \
    env.Command("bchess/data/stockfish", ["build/Stockfish-sf_13.tar.gz"], """
        cd build && \
        tar vxf Stockfish-sf_13.tar.gz && \
        cd Stockfish-sf_13/src && \
        sed -e 's/^net:/net:\\n\\ttrue\\n\\nxnet:/' -i Makefile && \
        make build ARCH=x86-64 EXTRACXXFLAGS=-DNNUE_EMBEDDING_OFF=1 -j4 && \
        strip stockfish
        cp build/Stockfish-sf_13/src/stockfish $TARGET
        rm -rf build/Stockfish-sf_13
    """)

generated += \
    env.Command("bchess/data/lc0", ["build/lc0-0.27.0.tar.gz"], """
        which meson
        which ninja
        cd build && \
        tar vxf lc0-0.27.0.tar.gz && \
        cd lc0-0.27.0 && \
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
        cp build/lc0-0.27.0/build/minsize/lc0 $TARGET
    """)

File("PKG-INFO")
#source = DirectoryFiles("bchess") + File(["bchess_data/__init__.py"])

def vcs_files(*paths):
    if os.path.exists(".hg"):
        return File(subprocess.check_output(["hg", "files", *paths], encoding="utf8").splitlines())
    if os.path.exists(".git"):
        return File(subprocess.check_output(["git", "ls-files", *paths], encoding="utf8").splitlines())
    raise ValueError("Neither .hg nor .git directory is present")

def vcs_commit():
    if os.path.exists(".hg"):
        return subprocess.check_output(["hg", "id", "-i"], encoding="utf8").strip()
    if os.path.exists(".git"):
        return subprocess.check_output(["git", "rev-parse", "HEAD"], encoding="utf8").strip()
    raise ValueError("Neither .hg nor .git directory is present")

if os.path.exists(".hg") or os.path.exists(".git"):
    source = vcs_files("bchess")
    commit = vcs_commit()
    generated_source = env.Textfile(target="bchess/__init__.py", source=[
        f'__version__ = "{pyproject["project"]["version"]}"',
        f'__commit__ = "{commit}"'
    ])
    AlwaysBuild(generated_source)
else:
    # We are in a sdist.
    source = DirectoryFiles("bchess")
    generated_source = []


platformlib = env.Whl("platlib", source + generated, root="")
bdist = env.WhlFile(source=platformlib)

sdist = env.SDist(source=FindSourceFiles() + generated_src)

env.Alias("sdist", sdist)
env.Alias("bdist", bdist)
env.Alias("build", generated_src + generated)
env.Default("build")
