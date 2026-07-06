Name:           calamus
Version:        0.1.0
Release:        1%{?dist}
Summary:        A GTK4 Markdown editor for GNOME

License:        GPL-3.0-or-later
URL:            https://github.com/OWNER/calamus
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  desktop-file-utils

# pygobject and gtk4 must come from system packages, not PyPI wheels
Requires:       python3-gobject
Requires:       gtk4
Requires:       python3-weasyprint
Requires:       python3-mistune
Requires:       python3-odfpy

%description
Calamus is a GTK4 Markdown editor for GNOME with live preview,
syntax highlighting, and export to HTML, PDF, and ODF formats.

Requires GTK 4.22.4+ (Fedora 44+).

%prep
%autosetup -n %{name}-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files calamus

# Install desktop integration files
install -Dpm 0644 resources/desktop/calamus.desktop \
    %{buildroot}%{_datadir}/applications/calamus.desktop
install -Dpm 0644 resources/desktop/calamus.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/calamus.svg
install -Dpm 0644 resources/desktop/calamus_48x48.png \
    %{buildroot}%{_datadir}/icons/hicolor/48x48/apps/calamus.png
install -Dpm 0644 resources/desktop/calamus_128x128.png \
    %{buildroot}%{_datadir}/icons/hicolor/128x128/apps/calamus.png
install -Dpm 0644 resources/desktop/calamus_256x256.png \
    %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/calamus.png

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/calamus.desktop

%files -f %{pyproject_files}
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/calamus
%{_datadir}/applications/calamus.desktop
%{_datadir}/icons/hicolor/scalable/apps/calamus.svg
%{_datadir}/icons/hicolor/48x48/apps/calamus.png
%{_datadir}/icons/hicolor/128x128/apps/calamus.png
%{_datadir}/icons/hicolor/256x256/apps/calamus.png

%changelog
* Sat Jul 05 2026 Daniel P. Dougherty <mray271@gmail.com> - 0.1.0-1
- Initial package
