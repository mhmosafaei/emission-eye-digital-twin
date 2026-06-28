from __future__ import annotations

from dataclasses import dataclass


def calculate_mean_draft(forward_draft_m: float, aft_draft_m: float) -> float:
    return (forward_draft_m + aft_draft_m) / 2.0


def calculate_trim(forward_draft_m: float, aft_draft_m: float) -> float:
    return round(aft_draft_m - forward_draft_m, 6)


def estimate_displacement_proxy(
    length_pp_m: float,
    beam_m: float,
    mean_draft_m: float,
    block_coefficient: float = 0.7,
    seawater_density_tonnes_per_m3: float = 1.025,
) -> float:
    return length_pp_m * beam_m * mean_draft_m * block_coefficient * seawater_density_tonnes_per_m3


def calculate_depth_draft_ratio(depth_m: float, mean_draft_m: float) -> float:
    if mean_draft_m <= 0:
        raise ValueError("mean_draft_m must be positive")
    return depth_m / mean_draft_m


def classify_depth_condition(depth_draft_ratio: float) -> str:
    if depth_draft_ratio < 1.2:
        return "critical_shallow"
    if depth_draft_ratio < 1.5:
        return "shallow_water"
    if depth_draft_ratio < 2.5:
        return "restricted_water"
    return "deep_water"


@dataclass(frozen=True)
class VesselGeometry:
    length_pp_m: float
    beam_m: float
    design_draft_m: float
    mean_draft_m: float
    trim_m: float
    deadweight_tonnes: float
    gross_tonnage: float
    wetted_surface_m2: float
    air_drag_area_m2: float
    depth_draft_ratio: float

    @classmethod
    def from_drafts(
        cls,
        *,
        length_pp_m: float,
        beam_m: float,
        design_draft_m: float,
        forward_draft_m: float,
        aft_draft_m: float,
        depth_m: float,
        deadweight_tonnes: float,
        gross_tonnage: float,
        wetted_surface_m2: float,
        air_drag_area_m2: float,
    ) -> "VesselGeometry":
        mean_draft_m = calculate_mean_draft(forward_draft_m, aft_draft_m)
        trim_m = calculate_trim(forward_draft_m, aft_draft_m)
        return cls(
            length_pp_m=length_pp_m,
            beam_m=beam_m,
            design_draft_m=design_draft_m,
            mean_draft_m=mean_draft_m,
            trim_m=trim_m,
            deadweight_tonnes=deadweight_tonnes,
            gross_tonnage=gross_tonnage,
            wetted_surface_m2=wetted_surface_m2,
            air_drag_area_m2=air_drag_area_m2,
            depth_draft_ratio=calculate_depth_draft_ratio(depth_m, mean_draft_m),
        )
