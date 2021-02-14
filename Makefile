all: data/.done bin/.done

bin/.done: bin/stockfish-12 bin/lc0
	date >$@

data/.done: \
		data/openings.sqlite \
		data/maia-1100.pb.gz \
		data/maia-1200.pb.gz \
		data/maia-1300.pb.gz \
		data/maia-1400.pb.gz \
		data/maia-1500.pb.gz \
		data/maia-1600.pb.gz \
		data/maia-1700.pb.gz \
		data/maia-1800.pb.gz \
		data/maia-1900.pb.gz
	date >$@

data/openings.sqlite: openings.sql
	rm -f "$@"
	sqlite3 "$@" ".read openings.sql" "reindex" "vacuum"

data/maia-%.pb.gz:
	wget -O "$@" "https://github.com/CSSLab/maia-chess/releases/download/v1.0/$$(basename '$@')"

bin/stockfish-12: tmp/stockfish_12_linux_x64_ssse.zip
	@mkdir -p tmp bin
	cd tmp && unzip -o stockfish_12_linux_x64_ssse.zip stockfish_20090216_x64_ssse
	mv tmp/stockfish_20090216_x64_ssse "$@"
	touch "$@"

tmp/stockfish_12_linux_x64_ssse.zip:
	@mkdir -p tmp
	wget -O "$@" 'https://stockfishchess.org/files/stockfish_12_linux_x64_ssse.zip'

bin/lc0: tmp/v0.26.3.zip
	which meson # must be installed
	which ninja # must be installed
	@mkdir -p tmp bin
	@rm -rf tmp/lc0-0.26.3/
	cd tmp && unzip v0.26.3.zip
	cd tmp/lc0-0.26.3 && ./build.sh minsize \
		--auto-features disabled \
		--default-library static \
		-Dopenblas=false \
		-Dcudnn=false \
		-Dispc=false \
		-Dcudnn=false \
		-Dplain_cuda=false \
		-Dopencl=false \
		-Ddx=false \
		-Dtensorflow=false \
		-Dmkl=false \
		-Ddnnl=false \
		-Daccelerate=false \
		-Dpopcnt=false \
		-Dpext=false \
		-Dgtest=false
	cp tmp/lc0-0.26.3/build/minsize/lc0 "$@"
	strip "$@"

tmp/v0.26.3.zip:
	@mkdir -p tmp
	wget -O "$@" 'https://github.com/LeelaChessZero/lc0/archive/v0.26.3.zip'

tmp/appdir.done: tmp/py38.appimage appimage/pyfiles.txt bin/.done data/.done
	@rm -rf tmp/squashfs-root tmp/appdir
	cd tmp && ./py38.appimage --appimage-extract
	./tmp/squashfs-root/usr/bin/pip --disable-pip-version-check install chess==1.4.0
	@#cp -a tmp/squashfs-root tmp/appdir
	for file in $$(cat appimage/pyfiles.txt); do \
	    mkdir -p tmp/appdir/$$(dirname "$$file"); \
	    cp -a "tmp/squashfs-root/$$file" "tmp/appdir/$$file"; \
	done
	echo >tmp/appdir/opt/python3.8/lib/python3.8/site-packages/chess/engine.py
	echo >tmp/appdir/opt/python3.8/lib/python3.8/site-packages/chess/svg.py
	date > "$@"

tmp/py38.appimage:
	@mkdir -p tmp
	wget -O tmp/py38.appimage "https://github.com/niess/python-appimage/releases/download/python3.8/python3.8.6-cp38-cp38-manylinux2010_x86_64.AppImage"
	chmod 755 tmp/py38.appimage

bchess.appimage: tmp/appdir.done *.py appimage/srcfiles.txt appimage/AppRun
	@rm -rf tmp/appdir/bchess
	for file in $$(cat appimage/srcfiles.txt); do \
	    mkdir -p tmp/appdir/bchess/$$(dirname "$$file"); \
	    cp -a "$$file" "tmp/appdir/bchess/$$file"; \
	done
	echo 'import bchess; bchess.main()' >tmp/appdir/bchess/main.py
	sed 's/export PYTHONDONTWRITEBYTECODE=1/unset PYTHONDONTWRITEBYTECODE/' appimage/AppRun >tmp/appdir/AppRun
	chmod 755 tmp/appdir/AppRun
	./tmp/appdir/AppRun -h >/dev/null 2>/dev/null </dev/null; true
	cp -a appimage/AppRun appimage/bchess.desktop appimage/bchess.svg tmp/appdir
	env ARCH=x86_64 appimagetool --comp=gzip tmp/appdir "$@"
