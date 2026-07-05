FROM fedora:44
# Fedora 44 is the current stable release (July 2026).
# When a new Fedora stable is released, update this tag and test the build.
# See: https://fedoraproject.org/wiki/Releases

LABEL maintainer="calamus contributors"
LABEL description="Calamus GTK4 Markdown Editor - Development Container"

# Install system dependencies
RUN dnf update -y && dnf install -y \
    gcc \
    python3 \
    python3-devel \
    python3-pip \
    python3-gobject \
    python3-cairo \
    gtk4 \
    libadwaita \
    gobject-introspection \
    glib2-devel \
    webkit2gtk4.1 \
    webkitgtk6.0 \
    gtksourceview5 \
    xorg-x11-server-Xvfb \
    dbus-daemon \
    dbus-tools \
    curl \
    git \
    && dnf clean all

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml ./
# Install Python dependencies (PyGObject comes from system, others from uv)
RUN uv sync --no-install-project || true

# Copy source
COPY . .

# Entrypoint: overlays /sys/block with a bind-mountable directory so
# WebKit's bwrap sandbox can access it (requires CAP_SYS_ADMIN at runtime).
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Set display for GUI
ENV DISPLAY=:0
ENV DBUS_SESSION_BUS_ADDRESS=autolaunch:

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uv", "run", "calamus"]
