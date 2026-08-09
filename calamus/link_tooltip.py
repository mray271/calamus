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
    padding: 6px 10px;
    font-size: 0.875em;
    font-family: monospace;
    border-radius: 0 8px 0 0;
    display: none;
    z-index: 10000;
    max-width: 90vw;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    box-shadow: 0 -1px 4px rgba(0, 0, 0, 0.1);
    border-top: 1px solid var(--tooltip-border);
    border-right: 1px solid var(--tooltip-border);
  }}
  #url-tooltip.visible {{
    display: block;
  }}
  :root {{
    --tooltip-bg: #ffffff;
    --tooltip-text: #000000;
    --tooltip-border: #d0d0d0;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --tooltip-bg: #2d2d2d;
      --tooltip-text: #e0e0e0;
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
    
    // Track the current link being hovered
    let currentLink = null;
    
    function showTooltip(link) {
      const href = link.getAttribute('href') || '';
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
    
    // Delegate event listeners to all anchor tags
    document.addEventListener('mouseover', function(event) {
      if (event.target.tagName === 'A') {
        showTooltip(event.target);
      } else if (currentLink && !event.target.closest('a')) {
        hideTooltip();
      }
    });
    
    document.addEventListener('mouseout', function(event) {
      if (event.target.tagName === 'A') {
        hideTooltip();
      }
    });
    
    // Hide tooltip when leaving the document
    document.addEventListener('mouseleave', hideTooltip);
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
