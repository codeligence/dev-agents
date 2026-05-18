"""Tests for core.context_factory — origin factory registry."""

import pytest

from core.context_factory import (
    _factories,
    create_context_from_origin,
    get_registered_origin_types,
    register_origin_factory,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Ensure a clean factory registry for each test."""
    saved = dict(_factories)
    _factories.clear()
    yield
    _factories.clear()
    _factories.update(saved)


class TestRegisterOriginFactory:
    def test_register_and_list(self):
        register_origin_factory("test_type", lambda _info, _cfg, _p: None)
        assert "test_type" in get_registered_origin_types()

    def test_overwrite_existing(self):
        register_origin_factory("test_type", lambda _info, _cfg, _p: "first")
        register_origin_factory("test_type", lambda _info, _cfg, _p: "second")
        result = _factories["test_type"]({"type": "test_type"}, None, None)
        assert result == "second"


class TestCreateContextFromOrigin:
    def test_calls_registered_factory(self):
        sentinel = object()
        register_origin_factory("mock", lambda _info, _cfg, _p: sentinel)
        result = create_context_from_origin({"type": "mock"}, None, None)
        assert result is sentinel

    def test_passes_args_to_factory(self):
        received = {}

        def factory(info, cfg, prompts):
            received.update(info=info, cfg=cfg, prompts=prompts)
            return "ctx"

        register_origin_factory("test", factory)
        create_context_from_origin(
            {"type": "test", "extra": 42}, "my_cfg", "my_prompts"
        )

        assert received["info"] == {"type": "test", "extra": 42}
        assert received["cfg"] == "my_cfg"
        assert received["prompts"] == "my_prompts"

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="No context factory registered"):
            create_context_from_origin({"type": "nonexistent"}, None, None)

    def test_missing_type_key_raises(self):
        with pytest.raises(ValueError, match="unknown"):
            create_context_from_origin({}, None, None)


class TestGetRegisteredOriginTypes:
    def test_empty_initially(self):
        assert get_registered_origin_types() == []

    def test_returns_all_registered(self):
        register_origin_factory("a", lambda *_: None)
        register_origin_factory("b", lambda *_: None)
        assert sorted(get_registered_origin_types()) == ["a", "b"]
