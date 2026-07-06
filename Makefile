PREFIX=/usr

install:
	mkdir -p $(DESTDIR)$(PREFIX)/share/applications
	mkdir -p $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps
	mkdir -p $(DESTDIR)$(PREFIX)/share/icons/hicolor/48x48/apps
	mkdir -p $(DESTDIR)$(PREFIX)/share/icons/hicolor/128x128/apps
	mkdir -p $(DESTDIR)$(PREFIX)/share/icons/hicolor/256x256/apps
	cp resources/desktop/calamus.desktop \
	    $(DESTDIR)$(PREFIX)/share/applications/calamus.desktop
	cp resources/desktop/calamus.svg \
	    $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/calamus.svg
	cp resources/desktop/calamus_48x48.png \
	    $(DESTDIR)$(PREFIX)/share/icons/hicolor/48x48/apps/calamus.png
	cp resources/desktop/calamus_128x128.png \
	    $(DESTDIR)$(PREFIX)/share/icons/hicolor/128x128/apps/calamus.png
	cp resources/desktop/calamus_256x256.png \
	    $(DESTDIR)$(PREFIX)/share/icons/hicolor/256x256/apps/calamus.png
	gtk-update-icon-cache -f $(DESTDIR)$(PREFIX)/share/icons/hicolor || true
	update-desktop-database $(DESTDIR)$(PREFIX)/share/applications || true

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/share/applications/calamus.desktop
	rm -f $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/calamus.svg
	rm -f $(DESTDIR)$(PREFIX)/share/icons/hicolor/48x48/apps/calamus.png
	rm -f $(DESTDIR)$(PREFIX)/share/icons/hicolor/128x128/apps/calamus.png
	rm -f $(DESTDIR)$(PREFIX)/share/icons/hicolor/256x256/apps/calamus.png
	gtk-update-icon-cache -f $(DESTDIR)$(PREFIX)/share/icons/hicolor || true
	update-desktop-database $(DESTDIR)$(PREFIX)/share/applications || true

.PHONY: install uninstall
