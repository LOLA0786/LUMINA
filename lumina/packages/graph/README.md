# [REPLACE WITH FOLDER NAME]

## Purpose
What lives here and why.

## Rules (never break these)
- Import only through packages/core interfaces
- All business logic stays pure (no FastAPI, no DB calls here)
- Every public function has full type hints + docstring

## Where bugs hide
- Most common bugs: [specific to this domain]
- How to debug: [exact command]

## Onboarding in 2 minutes
1. Read this file
2. Look at tests/
3. Run ...

Last updated: 2026

## Financial Knowledge Graph

Single source of truth: nodes = entities (Person, Asset, Liability, TaxEvent, ...), relationships = flows/connections (OWNS, IMPACTS_TAX, DEPENDS_ON, ...)

## Rules
- All writes go through domain services (not direct Cypher in agents/apps)
- Use MERGE to avoid duplicates
- Vector embeddings on Asset/Transaction descriptions for hybrid search

## Where bugs hide
- Duplicate nodes from bad merges
- Missing constraints → run schema.cypher first
- Cypher injection (always parametrize)

## Onboarding
See neo4j/schema.cypher and domain/models.py
