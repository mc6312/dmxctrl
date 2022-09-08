packer = tar
pack = $(packer) -caf
unpack = $(packer) --keep-newer-files -xaf
arcx = .tar.xz
#
imagedir = ./images
# ./images
backupdir = ~/shareddocs/pgm/python/
installdir = ~/bin
desktopfdir = ~/.local/share/applications
icondir = ~/.local/share/icons
distribdir = ~/downloads
#
basename = dmxctrl
srcversion = dmxctrl
version = $(shell python3 -c 'from $(srcversion) import VERSION; print(VERSION)')
branch = $(shell git symbolic-ref --short HEAD)
title_version = $(shell python3 -c 'from $(srcversion) import TITLE_VERSION; print(TITLE_VERSION)')
title = $(shell python3 -c 'from $(srcversion) import TITLE; print(TITLE)')
#
todo = TODO
docs = $(todo) COPYING Changelog README.md
zipname = $(basename).zip
arcname = $(basename)$(arcx)
srcarcname = $(basename)-$(branch)-src$(arcx)
pysrcs = *.py
uisrcs = *.ui
grsrcs = $(imagedir)/*.*
srcs = $(pysrcs) $(uisrcs) $(grsrcs)
iconfn = $(basename).png
desktopfn = $(basename).desktop

app:
	zip $(zipname) $(srcs)
	python3 -m zipapp $(zipname) -o $(basename) -p "/usr/bin/env python3" -c
	rm $(zipname)

archive:
	make todo
	$(pack) $(srcarcname) $(srcs) Makefile *.geany *.dmxctrl $(docs)

distrib:
	make app
	make desktop
	make winiconfn
	make todo
	$(eval distname = $(basename)-$(version)$(arcx))
	$(pack) $(distname) $(basename) $(docs) $(desktopfn) $(winiconfn)
	mv $(distname) $(distribdir)

backup:
	make archive
	mv $(srcarcname) $(backupdir)

update:
	$(unpack) $(backupdir)$(srcarcname)

commit:
	make todo
	git commit -a -uno -m "$(version)"
	@echo "не забудь сказать git push"

show-branch:
	@echo "$(branch)"

docview:
	$(eval docname = README.htm)
	grip $(readme) --export $(docname) --no-inline
	x-www-browser $(docname)
	#rm $(docname)

todo:
	pytodo.py $(pysrcs) >$(todo)

desktop:
	@echo "[Desktop Entry]" >$(desktopfn)
	@echo "Name=$(title)" >>$(desktopfn)
	@echo "Exec=/usr/bin/env python3 $(shell realpath $(installdir)/$(basename))" >>$(desktopfn)
	@echo "Icon=$(shell realpath $(icondir)/$(iconfn))" >>$(desktopfn)
	@echo "Type=Application" >>$(desktopfn)
	@echo "StartupWMClass=$(basename)" >>$(desktopfn)
	@echo "Categories=Multimedia;Utility" >>$(desktopfn)

install:
	make app
	cp $(basename) $(installdir)/
	cp $(imagedir)/$(iconfn) $(icondir)/
	make desktop
	cp $(desktopfn) $(desktopfdir)/

uninstall:
	rm $(desktopfdir)/$(desktopfn)
	rm $(installdir)/$(basename)
	rm $(icondir)/$(iconfn)
