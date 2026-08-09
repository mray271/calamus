"""URL tooltip manager for displaying link destinations on hover in the preview pane."""

from __future__ import annotations


class LinkTooltipManager:
    """Manages URL tooltip styling and JavaScript injection for link preview.
    
    Encapsulates all tooltip logic including CSS generation, HTML structure,
    and JavaScript event handlers. Respects light/dark color schemes.
    """

    def __init__(self) -> None:
        """Initialize the tooltip manager."""
        pass

    def _generate_tooltip_css(self) -> str:
        """Generate CSS styles for the URL tooltip popup.
        
        Returns:
            CSS string with light and dark mode variants.
        """
        css = """
  /* URL Tooltip Styles */
  #url-tooltip {{
    position: fixed;
    background: var(--tooltip-bg);
    color: var(--tooltip-text);
    padding: 8px 12px;
    font-size: 0.8125em;
    font-family: 'Courier New', monospace;
    border-radius: 0 8px 0 0;
    display: none;
    z-index: 99999;
    max-width: calc(100vw - 20px);
    max-height: 3em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.15);
    border-top: 1px solid var(--tooltip-border);
    border-right: 1px solid var(--tooltip-border);
    pointer-events: none;
  }}
  #url-tooltip.visible {{
    display: block;
  }}
  :root {{
    --tooltip-bg: #f6f8fa;
    --tooltip-text: #1c1c1c;
    --tooltip-border: #e1e4e8;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --tooltip-bg: #24292e;
      --tooltip-text: #e1e4e8;
      --tooltip-border: #30363d;
    }}
  }}
"""
        return css

    def _generate_tooltip_html(self) -> str:
        """Generate HTML structure for the tooltip element.
        
        Returns:
            HTML string containing the tooltip div.
        """
        html = '<div id="url-tooltip"></div>'
        return html

    def _generate_tooltip_js(self) -> str:
        """Generate JavaScript code for handling link hover events.
        
        Positions the tooltip at the bottom of the visible viewport to ensure
        it's always visible without requiring vertical scrolling.
        
        Returns:
            JavaScript string with event listeners and tooltip logic.
        """
        js = """
  (function() {
    const tooltip = document.getElementById('url-tooltip');
    if (!tooltip) return;
    
    function positionTooltip() {
      // Position tooltip at the bottom of the visible viewport
      // Account for scrollbar width by using window.innerWidth - scrollbar
      tooltip.style.left = '0px';
      tooltip.style.bottom = '0px';
      tooltip.style.width = 'auto';
    }
    
    function updateTooltipText(href) {
      tooltip.textContent = href;
      positionTooltip();
    }
    
    function attachTooltipsToLinks() {
      // Find all links and attach hover listeners directly
      const links = document.querySelectorAll('a[href]');
      
      links.forEach(link => {
        link.addEventListener('mouseenter', function() {
          const href = this.getAttribute('href');
          if (href) {
            updateTooltipText(href);
            tooltip.classList.add('visible');
          }
        }, false);
        
        link.addEventListener('mouseleave', function() {
          tooltip.classList.remove('visible');
        }, false);
      });
    }
    
    // Attach listeners when DOM is ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function() {
        attachTooltipsToLinks();
        positionTooltip();
      }, false);
    } else {
      attachTooltipsToLinks();
      positionTooltip();
    }
    
    // Re-position on scroll to keep tooltip visible
    window.addEventListener('scroll', function() {
      if (tooltip.classList.contains('visible')) {
        positionTooltip();
      }
    }, false);
    
    // Re-position on window resize
    window.addEventListener('resize', function() {
      if (tooltip.classList.contains('visible')) {
        positionTooltip();
      }
    }, false);
    
    // Re-attach listeners when content is dynamically updated (e.g., from Mermaid)
    const observer = new MutationObserver(function(mutations) {
      // Only re-attach if new links were added
      const hasNewLinks = mutations.some(m => 
        Array.from(m.addedNodes).some(n => 
          n.nodeName === 'A' || (n.querySelectorAll && n.querySelectorAll('a').length > 0)
        )
      );
      if (hasNewLinks) {
        attachTooltipsToLinks();
      }
    });
    
    // Watch for changes in the body
    if (document.body) {
      observer.observe(document.body, {
        childList: true,
        subtree: true
      });
    }
  })();
"""
        return js

    def get_tooltip_injection(self) -> dict[str, str]:
        """Generate complete tooltip injection bundle.
        
        Returns a dictionary with 'css', 'html', and 'js' keys that
        contain the complete tooltip implementation. This method provides
        a clean public interface for injecting the tooltip into the preview.
        
        Returns:
            Dictionary with keys:
                - 'css': CSS styles to inject into <style> tag
                - 'html': HTML to inject into <body>
                - 'js': JavaScript to inject into <script> tag
        """
        return {
            "css": self._generate_tooltip_css(),
            "html": self._generate_tooltip_html(),
            "js": self._generate_tooltip_js(),
        }
