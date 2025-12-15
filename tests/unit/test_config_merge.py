"""Tests for configuration merge strategy."""

from multi_mcp.models.config import semantic_merge


class TestSemanticMerge:
    """Tests for semantic_merge function."""

    def test_merge_models_by_name(self):
        """Models are merged by name (key-level)."""
        base = {"models": {"gpt-4": {"aliases": ["g4"], "notes": "old"}}}
        override = {"models": {"gpt-4": {"notes": "updated"}}}
        result = semantic_merge(base, override)

        assert result["models"]["gpt-4"]["aliases"] == ["g4"]  # Preserved
        assert result["models"]["gpt-4"]["notes"] == "updated"  # Overridden

    def test_merge_models_add_new(self):
        """New models are added."""
        base = {"models": {"gpt-4": {}}}
        override = {"models": {"gpt-5": {"notes": "new model"}}}
        result = semantic_merge(base, override)

        assert "gpt-4" in result["models"]
        assert "gpt-5" in result["models"]
        assert result["models"]["gpt-5"]["notes"] == "new model"

    def test_merge_other_keys_replaced(self):
        """Non-models keys are replaced entirely."""
        base = {"version": "1.0", "extra": {"nested": "value"}}
        override = {"version": "2.0"}
        result = semantic_merge(base, override)

        assert result["version"] == "2.0"
        assert result["extra"]["nested"] == "value"  # Preserved (not in override)

    def test_merge_empty_override(self):
        """Empty override returns base unchanged."""
        base = {"version": "1.0", "models": {"test": {}}}
        override = {}
        result = semantic_merge(base, override)

        assert result == base

    def test_merge_empty_base(self):
        """Override adds to empty base."""
        base = {}
        override = {"version": "2.0", "models": {"new": {"notes": "test"}}}
        result = semantic_merge(base, override)

        assert result["version"] == "2.0"
        assert result["models"]["new"]["notes"] == "test"

    def test_merge_preserves_base_models_not_in_override(self):
        """Models in base but not in override are preserved."""
        base = {"models": {"model-a": {"notes": "a"}, "model-b": {"notes": "b"}}}
        override = {"models": {"model-a": {"notes": "a-updated"}}}
        result = semantic_merge(base, override)

        assert result["models"]["model-a"]["notes"] == "a-updated"
        assert result["models"]["model-b"]["notes"] == "b"

    def test_merge_model_disabled_override(self):
        """Can disable a model via override."""
        base = {"models": {"gpt-4": {"disabled": False, "notes": "original"}}}
        override = {"models": {"gpt-4": {"disabled": True}}}
        result = semantic_merge(base, override)

        assert result["models"]["gpt-4"]["disabled"] is True
        assert result["models"]["gpt-4"]["notes"] == "original"  # Preserved


class TestAliasOverride:
    """Tests for user alias override behavior."""

    def test_user_can_steal_alias_from_package_model(self):
        """User config can 'steal' an alias from a package model."""
        base = {"models": {"gpt-5-mini": {"aliases": ["mini", "fast"], "notes": "package"}}}
        override = {"models": {"my-custom": {"aliases": ["mini"], "notes": "user"}}}
        result = semantic_merge(base, override)

        # User model has the alias
        assert "mini" in result["models"]["my-custom"]["aliases"]
        # Package model lost the alias (but keeps others)
        assert "mini" not in result["models"]["gpt-5-mini"]["aliases"]
        assert "fast" in result["models"]["gpt-5-mini"]["aliases"]

    def test_alias_override_is_case_insensitive(self):
        """Alias stealing works case-insensitively."""
        base = {"models": {"gpt-5-mini": {"aliases": ["Mini", "FAST"]}}}
        override = {"models": {"my-custom": {"aliases": ["MINI"]}}}
        result = semantic_merge(base, override)

        # User model has the alias (case preserved)
        assert "MINI" in result["models"]["my-custom"]["aliases"]
        # Package model lost it (case-insensitive match)
        assert "Mini" not in result["models"]["gpt-5-mini"]["aliases"]
        assert "FAST" in result["models"]["gpt-5-mini"]["aliases"]

    def test_alias_override_multiple_aliases(self):
        """User can steal multiple aliases at once."""
        base = {"models": {"model-a": {"aliases": ["a1", "a2"]}, "model-b": {"aliases": ["b1", "b2"]}}}
        override = {"models": {"my-model": {"aliases": ["a1", "b1"]}}}
        result = semantic_merge(base, override)

        # User model has both aliases
        assert set(result["models"]["my-model"]["aliases"]) == {"a1", "b1"}
        # Both package models lost their respective aliases
        assert result["models"]["model-a"]["aliases"] == ["a2"]
        assert result["models"]["model-b"]["aliases"] == ["b2"]

    def test_alias_not_removed_when_same_model_overridden(self):
        """When user overrides same model, aliases are replaced not stolen."""
        base = {"models": {"gpt-5-mini": {"aliases": ["mini", "fast"], "notes": "package"}}}
        override = {"models": {"gpt-5-mini": {"aliases": ["mini", "quick"]}}}
        result = semantic_merge(base, override)

        # User's aliases replace package's aliases for same model
        assert set(result["models"]["gpt-5-mini"]["aliases"]) == {"mini", "quick"}

    def test_no_alias_conflict_after_merge(self):
        """After merge, validation should pass (no duplicate aliases)."""
        from multi_mcp.models.config import ModelsConfiguration

        base = {
            "version": "1.0",
            "models": {"gpt-5-mini": {"aliases": ["mini"], "litellm_model": "openai/gpt-5-mini"}},
        }
        override = {
            "models": {"my-custom": {"aliases": ["mini"], "litellm_model": "openai/gpt-4o"}},
        }
        result = semantic_merge(base, override)

        # Should not raise ValidationError
        config = ModelsConfiguration(**result)
        assert "my-custom" in config.models
        assert "mini" in config.models["my-custom"].aliases
        assert "mini" not in config.models["gpt-5-mini"].aliases
