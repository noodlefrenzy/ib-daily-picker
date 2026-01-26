"""
Strategy YAML loader.

PURPOSE: Load, validate, and manage strategy files
DEPENDENCIES: pydantic, pyyaml

ARCHITECTURE NOTES:
- Strategies are loaded from YAML files
- Validates against Pydantic schema
- Caches loaded strategies for performance
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ib_daily_picker.analysis.strategy_schema import Strategy
from ib_daily_picker.config import get_settings

logger = logging.getLogger(__name__)


class StrategyValidationError(Exception):
    """Raised when strategy validation fails."""

    def __init__(self, message: str, errors: list[dict] | None = None) -> None:
        """Initialize with message and optional error details."""
        super().__init__(message)
        self.errors = errors or []


class StrategyLoader:
    """Loads and validates strategy YAML files."""

    def __init__(self, strategies_dir: Path | None = None) -> None:
        """Initialize with optional strategies directory.

        Args:
            strategies_dir: Directory containing strategy files (defaults to config)
        """
        self._strategies_dir = strategies_dir
        self._cache: dict[str, Strategy] = {}

    @property
    def strategies_dir(self) -> Path:
        """Get strategies directory."""
        if self._strategies_dir:
            return self._strategies_dir
        return get_settings().strategies_dir

    def load(self, name_or_path: str) -> Strategy:
        """Load a strategy by name or file path.

        Args:
            name_or_path: Strategy name (without extension) or full path

        Returns:
            Validated Strategy object

        Raises:
            StrategyValidationError: If validation fails
            FileNotFoundError: If strategy file not found
        """
        # Check cache first
        if name_or_path in self._cache:
            return self._cache[name_or_path]

        # Determine file path
        path = Path(name_or_path)
        if not path.is_absolute():
            # Try as name in strategies directory
            for ext in [".yaml", ".yml"]:
                candidate = self.strategies_dir / f"{name_or_path}{ext}"
                if candidate.exists():
                    path = candidate
                    break
            else:
                # Check if it's a relative path
                if not path.exists():
                    raise FileNotFoundError(
                        f"Strategy not found: {name_or_path}. "
                        f"Looked in: {self.strategies_dir}"
                    )

        if not path.exists():
            raise FileNotFoundError(f"Strategy file not found: {path}")

        # Load and parse YAML
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise StrategyValidationError(f"Invalid YAML: {e}")

        # Validate against schema
        strategy = self.validate(data)

        # Cache the result
        self._cache[name_or_path] = strategy
        self._cache[str(path)] = strategy

        logger.info(f"Loaded strategy: {strategy.name} v{strategy.version}")
        return strategy

    def validate(self, data: dict[str, Any]) -> Strategy:
        """Validate strategy data against schema.

        Args:
            data: Strategy data dictionary

        Returns:
            Validated Strategy object

        Raises:
            StrategyValidationError: If validation fails
        """
        try:
            strategy = Strategy.model_validate(data)
        except ValidationError as e:
            errors = e.errors()
            error_msgs = [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in errors]
            raise StrategyValidationError(
                f"Strategy validation failed:\n" + "\n".join(f"  - {m}" for m in error_msgs),
                errors=errors,
            )

        # Additional validation
        missing_indicators = strategy.validate_indicators_referenced()
        if missing_indicators:
            raise StrategyValidationError(
                f"Referenced indicators not defined: {', '.join(missing_indicators)}"
            )

        return strategy

    def validate_file(self, path: Path) -> tuple[bool, str]:
        """Validate a strategy file.

        Args:
            path: Path to strategy file

        Returns:
            Tuple of (is_valid, message)
        """
        try:
            strategy = self.load(str(path))
            return True, f"Valid strategy: {strategy.name} v{strategy.version}"
        except StrategyValidationError as e:
            return False, str(e)
        except FileNotFoundError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error: {e}"

    def list_strategies(self) -> list[dict[str, str]]:
        """List all available strategies.

        Returns:
            List of dicts with 'name', 'file', and 'version' keys
        """
        strategies = []
        strategy_dir = self.strategies_dir

        if not strategy_dir.exists():
            return strategies

        for path in sorted(strategy_dir.glob("*.yaml")) + sorted(
            strategy_dir.glob("*.yml")
        ):
            try:
                strategy = self.load(str(path))
                strategies.append({
                    "name": strategy.name,
                    "file": path.name,
                    "version": strategy.version,
                    "description": strategy.strategy.description or "",
                })
            except Exception as e:
                logger.warning(f"Failed to load {path.name}: {e}")
                strategies.append({
                    "name": path.stem,
                    "file": path.name,
                    "version": "error",
                    "description": f"Error: {e}",
                })

        return strategies

    def clear_cache(self) -> None:
        """Clear the strategy cache."""
        self._cache.clear()


# Singleton instance
_loader: StrategyLoader | None = None


def get_strategy_loader() -> StrategyLoader:
    """Get or create singleton StrategyLoader instance."""
    global _loader
    if _loader is None:
        _loader = StrategyLoader()
    return _loader


def reset_strategy_loader() -> None:
    """Reset singleton (for testing)."""
    global _loader
    _loader = None
