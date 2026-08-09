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
    bottom: 0;
    left: 0;
    background: var(--tooltip-bg);
    color: var(--tooltip-text);
    padding: 8px 12px;
    font-size: 0.8125em;
    font-family: 'Courier New', monospace;
    border-radius: 0 8px 0 0;
    display: none;
    z-index: 99999;
    max-width: 90vw;
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
    --tooltip-bg: #ffffff;
    --tooltip-text: #1c1c1c;
    --tooltip-border: #d0d0d0;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --tooltip-bg: #2d2d2d;
      --tooltip-text: #e8e8e8;
      --tooltip-border: #454545;
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
        
        Returns:
            JavaScript string with event listeners and tooltip logic.
        """
        js = """
  (function() {
    const tooltip = document.getElementById('url-tooltip');
    
    if (!tooltip) return;
    
    let currentLink = null;
    
    function showTooltip(link) {
      const href = link.getAttribute('href');
      if (!href) {
        hideTooltip();
        return;
      }
      
      tooltip.textContent = href;
      tooltip.classList.add('visible');
      currentLink = link;
    }
    
    function hideTooltip() {
      tooltip.classList.remove('visible');
      currentLink = null;
    }
    
    // Use event delegation with composedPath for better coverage
    document.addEventListener('mouseover', function(event) {
      const path = event.composedPath ? event.composedPath() : [event.target];
      const link = path.find(el => el.tagName === 'A');
      
      if (link) {
        showTooltip(link);
      } else if (currentLink) {
        hideTooltip();
      }
    }, true);  // Use capture phase for better event handling
    
    document.addEventListener('mouseout', function(event) {
      const path = event.composedPath ? event.composedPath() : [event.target];
      const link = path.find(el => el.tagName === 'A');
      
      if (link) {
        hideTooltip();
      }
    }, true);  // Use capture phase
    
    // Ensure tooltip is hidden when mouse leaves document
    document.addEventListener('mouseleave', hideTooltip, true);
    
    // Also hide when scrolling
    document.addEventListener('scroll', hideTooltip, true);
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
