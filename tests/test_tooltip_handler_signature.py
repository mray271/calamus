"""Test to understand the tooltip message handler signature."""

import json

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

try:
    gi.require_version("WebKit", "6.0")
    from gi.repository import GLib, WebKit
    WEBKIT_AVAILABLE = True
except ValueError:
    WEBKIT_AVAILABLE = False

from calamus.preview import WebKitPreview

# Skip all tests in this module if WebKit is not available
pytestmark = pytest.mark.skipif(
    not WEBKIT_AVAILABLE, reason="WebKit 6.0 not available"
)

def test_tooltip_handler_with_mock_gvariant():
    """Test the tooltip handler with a mocked GVariant message."""
    preview = WebKitPreview()

    # Create a test message as JSON string
    test_message = json.dumps({"href": "https://example.com", "state": "enter"})
    print(f"\n[TEST] test_message: {test_message}")

    # Try different parameter combinations to understand the actual signature

    # Attempt 1: Just manager and GVariant
    print("\n[TEST] Attempt 1: manager, GVariant")
    try:
        # GVariant is in GLib
        gvar = GLib.Variant.new_string(test_message)
        print(f"[TEST] GVariant created: {gvar}")
        print(f"[TEST] GVariant type: {type(gvar)}")
        print(
            f"[TEST] GVariant methods: {[m for m in dir(gvar) if not m.startswith('_')]}"
        )

        # Try to extract string
        if hasattr(gvar, "get_string"):
            extracted = gvar.get_string()
            print(f"[TEST] Extracted with get_string(): {extracted}")
        else:
            print(f"[TEST] No get_string() method on GVariant")

    except Exception as e:
        print(f"[TEST] Error creating GVariant: {e}")

    # Attempt 2: Check what UserMessage actually looks like
    print("\n[TEST] Checking UserMessage structure")
    try:
        # Try to create a UserMessage
        msg = WebKit.UserMessage.new("tooltip", GLib.Variant.new_string(test_message))
        print(f"[TEST] UserMessage created: {msg}")
        print(f"[TEST] UserMessage type: {type(msg)}")
        print(
            f"[TEST] UserMessage methods: {[m for m in dir(msg) if not m.startswith('_') and 'get' in m.lower()]}"
        )

        # Try to get parameters
        if hasattr(msg, "get_parameters"):
            params = msg.get_parameters()
            print(f"[TEST] get_parameters() returned: {params}")
            print(f"[TEST] params type: {type(params)}")
        else:
            print(f"[TEST] No get_parameters() method")

    except Exception as e:
        print(f"[TEST] Error with UserMessage: {e}")
        import traceback

        traceback.print_exc()

def test_signal_signature_detection():
    """Detect the actual signal signature by inspecting the UserContentManager."""
    try:
        from gi.repository import GObject

        print("\n[TEST] Inspecting UserContentManager signal")

        # Get the signal info
        manager = WebKit.UserContentManager()

        # Try to get signal info
        signal_info = GObject.signal_lookup(
            "script-message-received::tooltip", WebKit.UserContentManager
        )
        if signal_info:
            print(f"[TEST] Signal found: {signal_info}")
            signal_query = GObject.signal_query(signal_info)
            print(f"[TEST] Signal query: {signal_query}")
        else:
            print(f"[TEST] Signal not found")

    except Exception as e:
        print(f"[TEST] Error inspecting signal: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Run the tests
    print("=" * 60)
    print("Testing tooltip handler signature")
    print("=" * 60)

    test_tooltip_handler_with_mock_gvariant()
    test_signal_signature_detection()

    print("\n" + "=" * 60)
    print("Test complete - check output above")
    print("=" * 60)
