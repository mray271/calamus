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
    cairo-devel \
    cairo-gobject-devel \
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
    dbus-x11 \
    gnome-extensions-app \
    procps \
    curl \
    git \
    nodejs \
    npm \
    chromium \
    google-noto-sans-fonts \
    google-noto-sans-symbols2-fonts \
    google-noto-emoji-fonts \
    unifont-fonts \
    && dnf clean all

# Install mermaid-cli (mmdc) for server-side diagram pre-rendering.
# PUPPETEER_SKIP_CHROMIUM_DOWNLOAD avoids bundling a second Chromium —
# we use the system chromium package installed above instead.
ENV PUPPETEER_SKIP_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser
RUN npm install -g @mermaid-js/mermaid-cli@11.16.0

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

# Download Mermaid.js once at build time so the image works fully offline.
# Also store a copy outside /app so the dev volume mount (.:/app) can't shadow it.
RUN bash scripts/fetch-mermaid.sh && \
    mkdir -p /usr/local/share/calamus/js && \
    cp calamus/resources/js/mermaid.min.js /usr/local/share/calamus/js/mermaid.min.js

# Download highlight.js (code syntax highlighting in preview) at build time.
RUN bash scripts/fetch-highlight.sh && \
    mkdir -p /usr/local/share/calamus/js /usr/local/share/calamus/css && \
    cp calamus/resources/js/highlight.min.js /usr/local/share/calamus/js/highlight.min.js && \
    cp calamus/resources/css/highlight-github.min.css /usr/local/share/calamus/css/highlight-github.min.css && \
    cp calamus/resources/css/highlight-github-dark.min.css /usr/local/share/calamus/css/highlight-github-dark.min.css

# Puppeteer config for mmdc: use system Chromium with no-sandbox flags.
# Stored outside /app so the volume mount cannot shadow it.
COPY docker-mmdc-puppeteer.json /usr/local/share/calamus/mmdc-puppeteer.json

# Entrypoint: overlays /sys/block with a bind-mountable directory so
# WebKit's bwrap sandbox can access it (requires CAP_SYS_ADMIN at runtime).
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Set display for GUI
ENV DISPLAY=:0
ENV DBUS_SESSION_BUS_ADDRESS=autolaunch:

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uv", "run", "calamus"]
