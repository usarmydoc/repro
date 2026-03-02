"""Tests for network detection module."""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro import network


def test_is_online():
    """Test online detection returns a boolean."""
    network.reset_cache()
    result = network.is_online()
    assert isinstance(result, bool)
    print("  is_online() = {}".format(result))


def test_force_offline():
    """Test forced offline mode."""
    network.reset_cache()
    network.force_offline(True)
    assert network.is_online() is False
    assert network.is_forced_offline() is True
    network.reset_cache()


def test_cache():
    """Test that results are cached."""
    network.reset_cache()
    first = network.is_online()
    second = network.is_online()
    assert first == second
    print("  Cache works: both calls returned {}".format(first))


def test_proxy_config():
    """Test proxy detection from environment."""
    # Set test proxy
    os.environ["HTTP_PROXY"] = "http://proxy.example.com:8080"
    config = network.get_proxy_config()
    assert config.get("http") == "http://proxy.example.com:8080"
    print("  Proxy detected: {}".format(config))

    # Clean up
    del os.environ["HTTP_PROXY"]


def test_requests_proxies():
    """Test requests-compatible proxy dict."""
    os.environ["HTTPS_PROXY"] = "https://secure-proxy:443"
    result = network.get_requests_proxies()
    assert result is not None
    assert "https" in result
    print("  Requests proxies: {}".format(result))

    del os.environ["HTTPS_PROXY"]


def test_status_message():
    """Test human-readable status message."""
    network.reset_cache()
    msg = network.online_status_message()
    assert isinstance(msg, str)
    assert len(msg) > 0
    print("  Status: {}".format(msg))


def test_force_offline_status():
    """Test status message in forced offline mode."""
    network.reset_cache()
    network.force_offline(True)
    msg = network.online_status_message()
    assert "forced" in msg.lower() or "offline" in msg.lower()
    print("  Forced offline status: {}".format(msg))
    network.reset_cache()


if __name__ == "__main__":
    tests = [
        test_is_online,
        test_force_offline,
        test_cache,
        test_proxy_config,
        test_requests_proxies,
        test_status_message,
        test_force_offline_status,
    ]
    for t in tests:
        print("Running {}...".format(t.__name__))
        t()
        print("  PASSED")
    print("\nAll network tests passed!")
