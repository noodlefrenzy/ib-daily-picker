"""
Strategies API endpoints.

PURPOSE: JSON API for strategy management and analysis
DEPENDENCIES: fastapi
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ib_daily_picker.analysis import get_strategy_loader

router = APIRouter()


# --- Response Models ---


class StrategySummaryResponse(BaseModel):
    """Strategy summary response."""

    name: str
    file: str
    version: str
    description: str


class StrategyListResponse(BaseModel):
    """List of strategies."""

    strategies: list[StrategySummaryResponse]
    total: int


class StrategyDetailResponse(BaseModel):
    """Strategy detail response."""

    name: str
    version: str
    description: str | None
    indicators: list[str]
    entry_conditions: list[str]
    exit_conditions: list[str]


# --- Endpoints ---


@router.get("/strategies", response_model=StrategyListResponse)
async def list_strategies() -> StrategyListResponse:
    """List all available strategies."""
    loader = get_strategy_loader()
    strategies = loader.list_strategies()

    return StrategyListResponse(
        strategies=[
            StrategySummaryResponse(
                name=s["name"],
                file=s["file"],
                version=s["version"],
                description=s.get("description", ""),
            )
            for s in strategies
        ],
        total=len(strategies),
    )


@router.get("/strategies/{name}", response_model=StrategyDetailResponse)
async def get_strategy(name: str) -> StrategyDetailResponse:
    """Get strategy details."""
    loader = get_strategy_loader()

    try:
        strategy = loader.load(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Strategy {name} not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Extract indicator names
    indicators = [ind.name for ind in strategy.indicators]

    # Extract entry conditions
    entry_conditions = []
    if strategy.entry and strategy.entry.conditions:
        for cond in strategy.entry.conditions:
            if hasattr(cond, "indicator"):
                entry_conditions.append(f"{cond.indicator} {cond.operator} {cond.value}")
            else:
                entry_conditions.append(str(cond))

    # Extract exit conditions
    exit_conditions = []
    if strategy.exit and strategy.exit.targets:
        for target in strategy.exit.targets:
            exit_conditions.append(f"{target.type}: {target.value}")

    return StrategyDetailResponse(
        name=strategy.name,
        version=strategy.version,
        description=strategy.strategy.description if strategy.strategy else None,
        indicators=indicators,
        entry_conditions=entry_conditions,
        exit_conditions=exit_conditions,
    )


@router.post("/strategies/{name}/validate")
async def validate_strategy(name: str) -> dict[str, str | bool]:
    """Validate a strategy."""
    loader = get_strategy_loader()

    try:
        strategy = loader.load(name)
        return {"valid": True, "message": f"Strategy {strategy.name} is valid"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Strategy {name} not found")
    except Exception as e:
        return {"valid": False, "message": str(e)}
