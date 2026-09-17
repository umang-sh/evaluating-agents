"""
Halvard Works — a fictional plant, for Session 7 onwards.

WHY THIS EXISTS
---------------
Sessions 1-6 used questions an undergrad could verify in ten seconds (a PyPI
version, an env-var rename). Nobody in a classroom can verify a gearbox
diagnosis. So the plant is simulated: fictional works, fictional machines,
fictional sensor logs, fictional manuals.

But the PHYSICS is real. Bearing defect frequencies, gear mesh sidebands,
cavitation below NPSH, DC-bus ripple from degraded capacitors -- all real
mechanisms, so the model's prior actually helps it reason instead of just
retrieving. And every diagnosis is checkable IN THE ROOM, because the
verification chain is printed by the tools themselves: equipment_kb prints
the bearing's defect frequency, sensor_history prints the measured peak, and
the student compares two numbers.

NOT AFFILIATED WITH SIEMENS. Inspired by publicly described industrial-copilot
products. Halvard Works, its machines, sensors, manuals, parts and history are
entirely fictional and were invented for this course.

WHAT IT COSTS IN REALISM (say this out loud in class)
-----------------------------------------------------
  * No sensor noise unless we seed it.
  * No conflicting evidence unless we seed it.
  * No ambiguity: every request here HAS a right answer.
Real plants have the worst property of all, which we cannot simulate:
nobody there knows the right answer either.

Tools are deterministic and file-backed. Tavily spend for this session: zero.
"""

from __future__ import annotations

PLANT_NAME = "Halvard Works"

# What the plant actually does. Without this, "criticality: high" is a word
# with no referent -- a student cannot judge whether a recommendation is
# proportionate if they do not know what stops when the machine stops.
PLANT_ONE_LINER = ("a soft-drink bottling plant: empty bottles in, filled, "
                   "capped and labelled cases out")
PLANT_DESCRIPTION = (
    "Halvard Works bottles soft drinks. This session covers ONE bottling line — "
    "Line 3 — and the two plant-wide utilities it depends on. Along Line 3: "
    "empty bottles are conveyed in and rinsed, filled and capped, blown dry by "
    "an air knife, then labelled and packed into cases. It runs 18 hours a day, "
    "five days a week, and nothing downstream of the filler runs when the filler "
    "stops."
)

# Which line does what, and what it costs when it is down. The whole plant is
# in series, which is why so much of it is "high" criticality.
# STAGES along Line 3, in order. These are positions on one line, not separate
# lines: "Line 3" is the bottling line, and a bottling plant numbers its LINES,
# not its stages. Getting this wrong produced a slide reading
# "Line 3 -> Line 4 -> Line 1", which is a sequence running 3, 4, 1.
STAGES = {
    "infeed":    {"does": "convey in and rinse",  "machine": "CONVEYOR",
                  "down": "the filler starves — no bottles reach it"},
    "filling":   {"does": "fill and cap",         "machine": "FILLER",
                  "down": "nothing gets filled"},
    "labelling": {"does": "air-knife dry, label, pack", "machine": "BLOWER",
                  "down": "labels will not stick to wet bottles"},
}
UTILITIES = {
    "rinse water": {"machine": "RINSE-PUMP", "down": "bottles cannot be rinsed, so they cannot be filled"},
    "plant air":   {"machine": "AIR-COMP",
                    "down": "the grippers that move bottles and the valves on the filler have nothing to drive them"},
}
# Kept as an alias: older code and the notebook iterate LINES.
LINES = {f"Line 3 · {k}": v for k, v in STAGES.items()}
DISCLAIMER = (
    "Halvard Works is a fictional plant invented for this course. "
    "Inspired by publicly described industrial-copilot products; "
    "not affiliated with or endorsed by any vendor."
)

# --------------------------------------------------------------------------
# EQUIPMENT KNOWLEDGE BASE
# --------------------------------------------------------------------------
# bpfo / bpfi / gmf are expressed as MULTIPLES OF SHAFT SPEED, which is how a
# vibration analyst reads them. That is deliberate: it lets a student check a
# diagnosis by comparing the multiple here with the peak in sensor_history.
#   BPFO = ball pass frequency, outer race   BPFI = ... inner race
#   GMF  = gear mesh frequency (= number of teeth x shaft speed)
#   NPSHr = net positive suction head required (metres) -- below it, cavitation

EQUIPMENT = {
    "CONVEYOR": {
        "name": "Filler infeed conveyor gearbox",
        "type": "helical gearbox, 2-stage",
        "line": "Line 3 · infeed",
        "criticality": "high — the filler starves; no bottles reach it",
        "installed": "2021-04-12",
        "shaft_speed_hz": 24.5,
        "input_bearing": "SKF-6208",
        "bearing_thumps_per_turn": 3.19,
        "inner_bearing_thumps_per_turn": 4.81,
        "gear_teeth_per_turn": 31.0,
        "alarm_temp_c": 72.0,
        "duty": "continuous, 18 h/day",
    },
    "RINSE-PUMP": {
        "name": "Rinse-water transfer pump",
        "type": "single-stage centrifugal pump",
        "line": "Utilities",
        "criticality": "medium — it pumps the water that rinses every bottle before filling; a second pump exists, but unrinsed bottles cannot be filled",
        "installed": "2019-11-30",
        "shaft_speed_hz": 48.3,
        "impeller_vanes": 6,
        "impeller_vanes_per_turn": 6.0,
        "min_actual_suction_head_m": 4.2,
        "alarm_temp_c": 65.0,
        "duty": "continuous",
    },
    "FILLER": {
        "name": "Filler and capper main drive inverter",
        "type": "variable frequency drive, 90 kW",
        "line": "Line 3 · filling",
        "criticality": "high — nothing gets filled, and no spare drive on site",
        "installed": "2020-08-03",
        "dc_bus_nominal_v": 565.0,
        "power_wobble_limit_pct": 3.0,
        "igbt_alarm_temp_c": 85.0,
        "duty": "intermittent, 3-shift",
    },
    "BLOWER": {
        "name": "Air-knife blower fan",
        "type": "centrifugal fan, belt driven",
        "line": "Line 3 · labelling",
        "criticality": "medium — labelling halts; labels will not stick to wet bottles",
        "installed": "2018-02-19",
        "shaft_speed_hz": 19.8,
        "bearing_thumps_per_turn": 3.05,
        "balance_grade": "G6.3",
        "alarm_temp_c": 70.0,
        "duty": "continuous",
    },
    "AIR-COMP": {
        "name": "Plant air screw compressor",
        "type": "oil-flooded rotary screw, 75 kW",
        "line": "Utilities",
        "criticality": "high — compressed air drives the grippers that lift and move every bottle, and the valves on the filler; without it the line stops dead",
        "installed": "2022-06-25",
        "shaft_speed_hz": 59.0,
        "rotor_lobes": 5,
        "rotor_lobes_per_turn": 5.0,
        "alarm_temp_c": 95.0,
        "duty": "continuous",
    },
}

# --------------------------------------------------------------------------
# SENSOR HISTORY
# --------------------------------------------------------------------------
# Each entry is a 14-day summary as a condition-monitoring system would print
# it. The diagnosis is derivable by comparing `measured_thumps_per_turn` with the defect
# multiples in EQUIPMENT -- no hidden knowledge, no domain expert required.

SENSORS = {
    "CONVEYOR": {
        "window": "last 14 days",
        "vibration_rms_mm_s": {"day_1": 2.1, "day_7": 3.4, "day_14": 6.8},
        "measured_thumps_per_turn": 3.2,
        "sidebands_per_turn": 1.0,
        "bearing_temp_c": {"day_1": 54.0, "day_7": 61.0, "day_14": 72.0},
        "oil_particle_count_iso": "19/17/14 (was 16/14/11 at day 1)",
        "note": "trend accelerating in the last 4 days",
    },
    "RINSE-PUMP": {
        "window": "last 14 days",
        "vibration_rms_mm_s": {"day_1": 1.8, "day_7": 2.0, "day_14": 2.2},
        "measured_thumps_per_turn": None,
        "spectrum_shape": "broadband haystack, 500-2000 Hz, no discrete peak",
        "actual_suction_head_m": {"day_1": 5.1, "day_7": 4.4, "day_14": 3.6},
        "discharge_pressure_bar": {"day_1": 4.4, "day_7": 4.3, "day_14": 3.9},
        "bearing_temp_c": {"day_1": 48.0, "day_7": 49.0, "day_14": 50.0},
        "note": "audible rattling reported by Line operator, 'like gravel'",
    },
    "FILLER": {
        "window": "last 14 days",
        "dc_bus_v": {"day_1": 564.0, "day_7": 561.0, "day_14": 558.0},
        "power_wobble_pct": {"day_1": 1.9, "day_7": 3.6, "day_14": 5.8},
        "igbt_temp_c": {"day_1": 61.0, "day_7": 68.0, "day_14": 79.0},
        "overcurrent_trips": {"day_1": 0, "day_7": 1, "day_14": 4},
        "ambient_c": 31.0,
        "note": "trips cluster at shift start, under acceleration load",
    },
    "BLOWER": {
        "window": "last 14 days",
        "vibration_rms_mm_s": {"day_1": 3.9, "day_7": 4.1, "day_14": 4.2},
        "measured_thumps_per_turn": 1.0,
        "sidebands_per_turn": None,
        "phase_stable": True,
        "bearing_temp_c": {"day_1": 44.0, "day_7": 44.0, "day_14": 45.0},
        "note": "stable, not trending; the air-knife hood was washed down on day 2",
    },
    "AIR-COMP": {
        "window": "last 14 days",
        "vibration_rms_mm_s": {"day_1": 1.4, "day_7": 1.5, "day_14": 1.4},
        "measured_thumps_per_turn": 5.0,
        "discharge_temp_c": {"day_1": 88.0, "day_7": 89.0, "day_14": 88.0},
        "oil_pressure_bar": {"day_1": 3.8, "day_7": 3.8, "day_14": 3.7},
        "note": "nothing trending; within limits on every channel",
    },
}

# --------------------------------------------------------------------------
# FAULT CATALOGUE — ground truth, by construction
# --------------------------------------------------------------------------
# `derivation` is the chain a student checks on screen. It is NOT given to the
# agents; it is what the evaluator and the run sheet answer key use.

FAULTS = {
    "BEARING-WEAR": {
        "title": "Bearing outer-race defect, gearbox input shaft",
        "machine": "CONVEYOR",
        "derivation": "peak at 3.2x shaft speed matches BPFO 3.19x; "
                      "1x sidebands = load modulation; bearing temp at alarm; "
                      "oil particle count up three ISO codes",
        "part": "SKF-6208",
        "manual": "MAN-CONVEYOR-4.2",
        "urgency": "shutdown within 7 days",
    },
    "CAVITATION": {
        "title": "Cavitation, pump suction",
        "machine": "RINSE-PUMP",
        "derivation": "suction head 3.6 m is below NPSHr 4.2 m; broadband "
                      "spectrum with no discrete peak; discharge pressure "
                      "falling; audible gravel noise",
        "part": "STRN-PUMP-MESH",
        "manual": "MAN-PUMP-6.1",
        "urgency": "correct suction condition this week",
    },
    "CAPACITOR-WEAR": {
        "title": "DC-bus capacitor degradation",
        "machine": "FILLER",
        "derivation": "bus ripple 5.8% exceeds the 3.0% limit and is trending; "
                      "IGBT temp rising with it; overcurrent trips under "
                      "acceleration load",
        "part": "CAP-FILLER-KIT",
        "manual": "MAN-FILLER-9.3",
        "urgency": "replace at next planned stop",
    },
    "IMBALANCE": {
        "title": "Rotor imbalance (residual, stable)",
        "machine": "BLOWER",
        "derivation": "1x peak with stable phase and no trend; consistent with "
                      "residual imbalance after washdown, NOT a developing "
                      "fault -- this row's correct outcome is 'monitor'",
        "part": None,
        "manual": "MAN-BLOWER-3.4",
        "urgency": "monitor, no action",
    },
    "NO-FAULT": {
        "title": "No fault found",
        "machine": "AIR-COMP",
        "derivation": "every channel flat and within limits over 14 days",
        "part": None,
        "manual": None,
        "urgency": "none",
    },
}

# --------------------------------------------------------------------------
# MAINTENANCE HISTORY
# --------------------------------------------------------------------------
HISTORY = {
    "CONVEYOR": [
        {"date": "2025-03-08", "wo": "WO-88213", "action": "oil change, ISO VG 320", "by": "M. Otieno"},
        {"date": "2025-09-14", "wo": "WO-91120", "action": "input bearing replaced (SKF-6208)", "by": "R. Banda"},
        {"date": "2026-02-02", "wo": "WO-94402", "action": "vibration survey, baseline 2.0 mm/s", "by": "contract"},
    ],
    "RINSE-PUMP": [
        {"date": "2025-06-19", "wo": "WO-89701", "action": "mechanical seal replaced", "by": "R. Banda"},
        {"date": "2026-01-21", "wo": "WO-93887", "action": "suction strainer cleaned", "by": "M. Otieno"},
    ],
    "FILLER": [
        {"date": "2024-10-05", "wo": "WO-85110", "action": "cooling fan replaced", "by": "contract"},
        {"date": "2025-11-30", "wo": "WO-92455", "action": "firmware 3.11 -> 3.14", "by": "contract"},
    ],
    "BLOWER": [
        {"date": "2025-08-22", "wo": "WO-90644", "action": "belts tensioned", "by": "M. Otieno"},
        {"date": "2026-09-03", "wo": "WO-97012", "action": "line washdown, blower casing cleaned", "by": "Line 3 crew"},
    ],
    "AIR-COMP": [
        {"date": "2026-04-11", "wo": "WO-95330", "action": "separator element replaced", "by": "contract"},
    ],
}

# --------------------------------------------------------------------------
# MANUAL SECTIONS
# --------------------------------------------------------------------------
MANUAL = {
    "MAN-CONVEYOR-4.2": {
        "machine": "CONVEYOR",
        "title": "Input shaft bearing replacement",
        "text": ("Isolate and lock out the drive. Drain oil. Remove the input "
                 "cover (8x M10). Extract the SKF-6208 with a blind-hole "
                 "puller; do not strike the race. Heat the replacement to "
                 "110 C max. Refill with ISO VG 320. Torque cover bolts to "
                 "47 Nm. Estimated 4.5 h, two technicians, drive isolated."),
    },
    "MAN-CONVEYOR-5.0": {
        "machine": "CONVEYOR",
        "title": "Vibration alarm thresholds",
        "text": ("ISO 10816-3 Zone B upper limit 4.5 mm/s RMS for this class. "
                 "Above 7.1 mm/s the machine is in Zone D and continued "
                 "operation risks secondary damage."),
    },
    "MAN-PUMP-6.1": {
        "machine": "RINSE-PUMP",
        "title": "Cavitation: diagnosis and correction",
        "text": ("Cavitation presents as broadband noise without a discrete "
                 "spectral peak and a characteristic gravel sound. Confirm by "
                 "comparing available suction head with NPSHr on the "
                 "nameplate. Correct by restoring suction head: clean the "
                 "strainer, check the suction valve is fully open, verify "
                 "tank level. Do NOT throttle the discharge."),
    },
    "MAN-FILLER-9.3": {
        "machine": "FILLER",
        "title": "DC-bus capacitor bank service",
        "text": ("Ripple above 3% of nominal indicates capacitor ageing. "
                 "Isolate, wait 15 minutes for bus discharge, verify below "
                 "50 V before contact. Replace the bank as a set using "
                 "CAP-FILLER-KIT; mixed-age capacitors will fail early. "
                 "Estimated 3 h, one technician, drive isolated."),
    },
    "MAN-BLOWER-3.4": {
        "machine": "BLOWER",
        "title": "Balance criteria",
        "text": ("Grade G6.3 permits residual unbalance producing up to "
                 "4.5 mm/s RMS at operating speed. A stable 1x component with "
                 "stable phase and no trend is residual unbalance and does not "
                 "require intervention. Re-balance only if the 1x amplitude "
                 "trends upward or phase shifts."),
    },
    "MAN-AIR-2.2": {
        "machine": "AIR-COMP",
        "title": "Routine condition limits",
        "text": ("Discharge temperature alarm at 95 C. Oil pressure normal "
                 "range 3.5-4.2 bar. Lobe-pass vibration component is normal "
                 "and expected at 5x shaft speed."),
    },
}

# --------------------------------------------------------------------------
# SPARE PARTS INVENTORY
# --------------------------------------------------------------------------
PARTS = {
    "SKF-6208": {"desc": "Deep groove ball bearing 40x80x18", "on_hand": 2,
                 "bin": "A-14", "lead_time_days": 5, "unit_cost_eur": 38.0},
    "STRN-PUMP-MESH": {"desc": "Suction strainer mesh insert, DN80", "on_hand": 0,
                       "bin": "C-03", "lead_time_days": 11, "unit_cost_eur": 96.0},
    "CAP-FILLER-KIT": {"desc": "DC-bus capacitor bank kit, 90 kW frame", "on_hand": 0,
                     "bin": "D-21", "lead_time_days": 21, "unit_cost_eur": 1240.0},
    "ISO-VG-320-20L": {"desc": "Gear oil ISO VG 320, 20 L", "on_hand": 6,
                       "bin": "A-02", "lead_time_days": 3, "unit_cost_eur": 74.0},
}

MACHINE_IDS = tuple(EQUIPMENT)
FAULT_CODES = tuple(FAULTS)

if __name__ == "__main__":
    print(PLANT_NAME, "—", PLANT_ONE_LINER)
    print()
    print(PLANT_DESCRIPTION)
    print()
    for ln, v in LINES.items():
        print(f"  {ln:10s} {v['does']:34s} down -> {v['down']}")
    print()
    print(len(EQUIPMENT), "machines,", len(FAULTS), "fault rows")
    print(DISCLAIMER)
    for mid, eq in EQUIPMENT.items():
        fc = next((k for k, v in FAULTS.items() if v["machine"] == mid), "-")
        print(f"  {mid:10s} {eq['name']:38s} -> {fc}")
