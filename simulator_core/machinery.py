from __future__ import annotations

from dataclasses import asdict, dataclass, field


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class EmissionFactors:
    co2_kg_per_kg_fuel: float = 3.114
    ch4_kg_per_kg_fuel: float = 0.0003
    n2o_kg_per_kg_fuel: float = 0.00012
    nox_kg_per_kg_fuel: float = 0.07
    sox_kg_per_kg_fuel: float = 0.01


FUEL_LIBRARY = {
    "MGO_PROXY": EmissionFactors(),
    "MDO": EmissionFactors(co2_kg_per_kg_fuel=3.206, sox_kg_per_kg_fuel=0.012),
    "LNG_DF": EmissionFactors(co2_kg_per_kg_fuel=2.75, ch4_kg_per_kg_fuel=0.0038, nox_kg_per_kg_fuel=0.02, sox_kg_per_kg_fuel=0.0001),
}


@dataclass(frozen=True)
class MachineryComponentOutput:
    power_kw: float
    load_pct: float
    fuel_kg_h: float
    co2_kg_h: float
    ch4_kg_h: float
    n2o_kg_h: float
    nox_kg_h: float
    sox_kg_h: float

    @classmethod
    def zero(cls) -> "MachineryComponentOutput":
        return cls(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


@dataclass
class MachinerySubsystem:
    rated_power_kw: float
    sfoc_g_per_kwh: float
    fuel_type: str = "MGO_PROXY"
    minimum_stable_load_pct: float = 5.0
    emission_factors: EmissionFactors = field(init=False)

    def __post_init__(self) -> None:
        self.emission_factors = FUEL_LIBRARY.get(self.fuel_type, FUEL_LIBRARY["MGO_PROXY"])

    def output_for_power(self, power_kw: float) -> MachineryComponentOutput:
        if power_kw <= 0:
            return MachineryComponentOutput.zero()

        bounded_power = _clamp(power_kw, 0.0, self.rated_power_kw)
        load_pct = _clamp((bounded_power / self.rated_power_kw) * 100.0, self.minimum_stable_load_pct, 115.0)
        fuel_kg_h = bounded_power * self.sfoc_g_per_kwh / 1000.0
        ef = self.emission_factors
        return MachineryComponentOutput(
            power_kw=round(bounded_power, 3),
            load_pct=round(load_pct, 3),
            fuel_kg_h=round(fuel_kg_h, 3),
            co2_kg_h=round(fuel_kg_h * ef.co2_kg_per_kg_fuel, 3),
            ch4_kg_h=round(fuel_kg_h * ef.ch4_kg_per_kg_fuel, 5),
            n2o_kg_h=round(fuel_kg_h * ef.n2o_kg_per_kg_fuel, 5),
            nox_kg_h=round(fuel_kg_h * ef.nox_kg_per_kg_fuel, 5),
            sox_kg_h=round(fuel_kg_h * ef.sox_kg_per_kg_fuel, 5),
        )


@dataclass
class MainEngine(MachinerySubsystem):
    pass


@dataclass
class AuxiliaryEngineSystem(MachinerySubsystem):
    generator_count: int = 2


@dataclass
class BoilerSystem(MachinerySubsystem):
    pass


@dataclass(frozen=True)
class MachinerySnapshot:
    main_engine: MachineryComponentOutput
    auxiliary_system: MachineryComponentOutput
    boiler_system: MachineryComponentOutput
    total: MachineryComponentOutput

    @classmethod
    def build(
        cls,
        *,
        main_engine: MainEngine,
        auxiliary_system: AuxiliaryEngineSystem,
        boiler_system: BoilerSystem,
        main_engine_power_kw: float,
        auxiliary_power_kw: float,
        boiler_power_kw: float,
    ) -> "MachinerySnapshot":
        me = main_engine.output_for_power(main_engine_power_kw)
        ae = auxiliary_system.output_for_power(auxiliary_power_kw)
        boiler = boiler_system.output_for_power(boiler_power_kw)
        total_power = me.power_kw + ae.power_kw + boiler.power_kw
        total_fuel = me.fuel_kg_h + ae.fuel_kg_h + boiler.fuel_kg_h
        total = MachineryComponentOutput(
            power_kw=round(total_power, 3),
            load_pct=round(
                ((me.load_pct * me.power_kw) + (ae.load_pct * ae.power_kw) + (boiler.load_pct * boiler.power_kw))
                / total_power,
                3,
            )
            if total_power
            else 0.0,
            fuel_kg_h=round(total_fuel, 3),
            co2_kg_h=round(me.co2_kg_h + ae.co2_kg_h + boiler.co2_kg_h, 3),
            ch4_kg_h=round(me.ch4_kg_h + ae.ch4_kg_h + boiler.ch4_kg_h, 5),
            n2o_kg_h=round(me.n2o_kg_h + ae.n2o_kg_h + boiler.n2o_kg_h, 5),
            nox_kg_h=round(me.nox_kg_h + ae.nox_kg_h + boiler.nox_kg_h, 5),
            sox_kg_h=round(me.sox_kg_h + ae.sox_kg_h + boiler.sox_kg_h, 5),
        )
        return cls(main_engine=me, auxiliary_system=ae, boiler_system=boiler, total=total)

    def as_dict(self) -> dict:
        return {
            "main_engine": asdict(self.main_engine),
            "auxiliary_system": asdict(self.auxiliary_system),
            "boiler_system": asdict(self.boiler_system),
            "total": asdict(self.total),
        }
