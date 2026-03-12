# domains/taxes

## Purpose
All tax logic, tax-loss harvesting, capital-gains timing, asset-location strategies.
This is the SINGLE source of truth for anything tax-related in India + global.

## Public API (only these are imported by other domains)
- TaxImpactCalculator.calculate()
- TaxLossHarvester.suggest_trades()
- AssetLocationOptimizer.optimize()

## Where bugs hide (99% of tax bugs live here)
- Incorrect ITR section mapping
- State-specific rules not updated
- EMI + capital-gains interaction edge cases

Debug tip: Run `pytest domains/taxes/tests/ -k tax_impact`
