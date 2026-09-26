from pydantic import BaseModel, Field, model_validator


class FeeTierIn(BaseModel):
    up_to: float | None = Field(default=None, gt=0, le=10_000_000)
    rate: float = Field(ge=0, le=0.05)


class SettingsOut(BaseModel):
    min_orders_per_year: int
    penalty_fee: float
    fee_grid: list[FeeTierIn]


class SettingsUpdate(BaseModel):
    min_orders_per_year: int = Field(ge=0, le=100)
    penalty_fee: float = Field(ge=0, le=1000)
    fee_grid: list[FeeTierIn] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def check_grid(self) -> "SettingsUpdate":
        *bounded, last = self.fee_grid
        if last.up_to is not None:
            raise ValueError("La dernière tranche doit être sans limite.")
        bounds = [t.up_to for t in bounded]
        if any(b is None for b in bounds) or bounds != sorted(set(bounds)):
            raise ValueError("Les bornes des tranches doivent être croissantes.")
        return self
