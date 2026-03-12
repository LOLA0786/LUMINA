from pydantic import BaseModel
from decimal import Decimal
from datetime import date

class TaxImpact(BaseModel):
    """Pure data class — never touches DB or API."""
    capital_gains_tax: Decimal
    tax_saving_opportunity: Decimal
    recommended_action: str
