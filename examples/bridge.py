#!/usr/bin/env python3
"""
Bridge Simulator — an atomm-clap example.

Showcases deep, domain-specific CLI paths in the style of infrastructure tools
(kubectl, docker CLI), but in a starship bridge command context.

Try:
    bridge status
    bridge alert set red
    bridge system shields set power 80
    bridge system engines repair
    bridge shields raise
    bridge shields set power 60
    bridge engine engage warp 6
    bridge engine all stop
    bridge weapon by type torpedo fire at target "Klingon Bird-of-Prey"
    bridge weapon by type phaser status
    bridge crew ranked "chief engineer" report
    bridge crew ranked "chief engineer" assign to system engines
    bridge crew named Reyes assign to system sensors
    bridge scan for ships
    bridge scan sector "12-A" for resources
    bridge course plot to system "Alpha Centauri"
    bridge log entry add "Encountered anomaly at bearing 270"
    bridge log show
"""

import sys
from atomc import CLI, parse_tokens, Argument


# ---------------------------------------------------------------------------
# Ship state
# ---------------------------------------------------------------------------

class Ship:
    def __init__(self):
        self.name = "ISS Relentless"
        self.hull = 100
        self.alert = "green"
        self.shields_raised = False
        self.warp_factor = 0
        self.position = "Sol system"
        self.systems = {
            "shields":       {"power": 100, "status": "operational"},
            "engines":       {"power": 100, "status": "operational"},
            "weapons":       {"power": 100, "status": "operational"},
            "life-support":  {"power": 100, "status": "operational"},
            "sensors":       {"power":  80, "status": "degraded"},
        }
        self.weapons = {
            "torpedo": {"count": 12, "ready": True},
            "phaser":  {"charge": 100, "banks": 4, "ready": True},
        }
        self.crew = [
            {"name": "Vasquez",   "rank": "captain",                 "system": None,           "status": "on bridge"},
            {"name": "Park",      "rank": "first officer",           "system": None,           "status": "on bridge"},
            {"name": "Kowalski",  "rank": "chief engineer",          "system": "engines",      "status": "on duty"},
            {"name": "Reyes",     "rank": "science officer",         "system": "sensors",      "status": "on duty"},
            {"name": "Osei",      "rank": "weapons officer",         "system": "weapons",      "status": "on duty"},
            {"name": "Lindqvist", "rank": "communications officer",  "system": None,           "status": "on bridge"},
            {"name": "Nakamura",  "rank": "helmsman",                "system": "engines",      "status": "on duty"},
            {"name": "Abara",     "rank": "doctor",                  "system": "life-support", "status": "on duty"},
        ]
        self.targets = {
            "Klingon Bird-of-Prey": {"hull": 100, "shields": 85, "distance": "4,200 km",  "bearing": "035"},
            "Romulan Warbird":      {"hull": 100, "shields": 92, "distance": "12,000 km", "bearing": "142"},
            "asteroid":             {"hull": 100, "shields":  0, "distance": "800 km",    "bearing": "270"},
            "derelict freighter":   {"hull":  34, "shields":  0, "distance": "6,100 km",  "bearing": "310"},
        }
        self.sectors = {
            "7-G":  {"ships": ["Klingon Bird-of-Prey", "derelict freighter"],
                     "resources": ["dilithium (trace)", "deuterium (moderate)"]},
            "12-A": {"ships": ["Romulan Warbird"],
                     "resources": ["latinum (rich)", "plasma ore (trace)"]},
            "3-F":  {"ships": [],
                     "resources": ["ice (abundant)", "silicates (moderate)"]},
        }
        self.log = [
            "Departed spacedock 0600 hours.",
            "Crossed the Neutral Zone perimeter at bearing 142.",
        ]


_ship = Ship()


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

_COLORS = {"green": "\033[32m", "yellow": "\033[33m", "red": "\033[31m"}
_RESET  = "\033[0m"
_BOLD   = "\033[1m"

def _color(text, level):
    return f"{_COLORS.get(level, '')}{text}{_RESET}"

def _heading(text):
    print(f"\n{_BOLD}{text}{_RESET}")

def _bar(value, width=20):
    filled = int(width * max(0, min(value, 100)) / 100)
    return "[" + "█" * filled + "░" * (width - filled) + f"] {value}%"

def _find_crew(*, name=None, rank=None):
    key, val = ("name", name) if name is not None else ("rank", rank)
    for m in _ship.crew:
        if m[key].lower() == val.lower():
            return m
    return None


# ---------------------------------------------------------------------------
# Handlers — status
# ---------------------------------------------------------------------------

def cmd_status():
    _heading(f"[ {_ship.name} — STATUS REPORT ]")
    print(f"  Alert    : {_color(_ship.alert.upper(), _ship.alert)}")
    print(f"  Position : {_ship.position}")
    warp = f"Warp {_ship.warp_factor}" if _ship.warp_factor > 0 else "Impulse"
    print(f"  Speed    : {warp}")
    print(f"  Hull     : {_bar(_ship.hull)}")
    shields = "RAISED" if _ship.shields_raised else "LOWERED"
    print(f"  Shields  : {shields}  {_bar(_ship.systems['shields']['power'])}")
    print()
    print("  Systems:")
    for name, s in _ship.systems.items():
        mark = "✓" if s["status"] == "operational" else "✗"
        print(f"    {mark} {name:<16} {_bar(s['power'], width=12)}")


# ---------------------------------------------------------------------------
# Handlers — systems
# ---------------------------------------------------------------------------

def cmd_system_status(system):
    if system not in _ship.systems:
        print(f"  Unknown system '{system}'. Known: {', '.join(_ship.systems)}")
        return
    s = _ship.systems[system]
    _heading(f"[ {system.upper()} ]")
    print(f"  Status : {s['status']}")
    print(f"  Power  : {_bar(s['power'])}")
    crew = [m["name"] for m in _ship.crew if m["system"] == system]
    print(f"  Crew   : {', '.join(crew) if crew else '(none assigned)'}")


def cmd_system_set_power(system, power):
    if system not in _ship.systems:
        print(f"  Unknown system '{system}'.")
        return
    _ship.systems[system]["power"] = power
    print(f"  {system.capitalize()} power set to {power}%.")
    if power < 20:
        print(f"  WARNING: {system} running at critically low power.")


def cmd_system_repair(system):
    if system not in _ship.systems:
        print(f"  Unknown system '{system}'.")
        return
    s = _ship.systems[system]
    if s["status"] == "operational":
        print(f"  {system.capitalize()} is already operational.")
    else:
        s["status"] = "operational"
        print(f"  {system.capitalize()} repaired and back online.")


# ---------------------------------------------------------------------------
# Handlers — shields
# ---------------------------------------------------------------------------

def cmd_shields_raise():
    if _ship.shields_raised:
        print("  Shields are already raised.")
    else:
        _ship.shields_raised = True
        print("  Shields raised.")
        if _ship.systems["shields"]["power"] < 50:
            print("  WARNING: Shield power below 50% — effectiveness reduced.")


def cmd_shields_lower():
    if not _ship.shields_raised:
        print("  Shields are already down.")
    else:
        _ship.shields_raised = False
        print("  Shields lowered.")


def cmd_shields_set_power(power):
    _ship.systems["shields"]["power"] = power
    print(f"  Shield power set to {power}%.")


# ---------------------------------------------------------------------------
# Handlers — engines
# ---------------------------------------------------------------------------

def cmd_engage_warp(factor):
    if not 1 <= factor <= 9:
        print("  Warp factor must be between 1 and 9.")
        return
    if _ship.systems["engines"]["status"] != "operational":
        print("  Cannot engage warp — engines offline.")
        return
    if _ship.systems["engines"]["power"] < 30:
        print(f"  Insufficient engine power ({_ship.systems['engines']['power']}%) for warp.")
        return
    _ship.warp_factor = factor
    print(f"  Warp {factor} engaged.")
    if factor >= 8:
        print(f"  WARNING: Sustained warp {factor} will stress the hull.")


def cmd_all_stop():
    _ship.warp_factor = 0
    print("  All stop. Dropping to impulse.")


# ---------------------------------------------------------------------------
# Handlers — weapons
# ---------------------------------------------------------------------------

def _resolve_weapon(weapon_type):
    w = weapon_type.lower().rstrip("s")  # "torpedoes" → "torpedo", "phasers" → "phaser"
    return w if w in _ship.weapons else None

def _resolve_target(target):
    for name in _ship.targets:
        if target.lower() in name.lower():
            return name
    return None

def cmd_weapon_fire(weapon_type, target):
    wkey = _resolve_weapon(weapon_type)
    if wkey is None:
        print(f"  Unknown weapon '{weapon_type}'. Available: {', '.join(_ship.weapons)}")
        return
    tkey = _resolve_target(target)
    if tkey is None:
        print(f"  No contact matching '{target}'. Contacts: {', '.join(_ship.targets)}")
        return

    t = _ship.targets[tkey]
    w = _ship.weapons[wkey]
    shield_factor = t["shields"] / 100

    if wkey == "torpedo":
        if w["count"] <= 0:
            print("  Torpedo tubes empty.")
            return
        raw = 35
        absorbed = int(raw * shield_factor)
        damage = raw - absorbed
        t["shields"] = max(0, t["shields"] - 15)
        t["hull"]    = max(0, t["hull"] - damage)
        w["count"] -= 1
        print(f"  Torpedo away — target {tkey} at bearing {t['bearing']}.")
        print(f"  Impact: shields absorbed {absorbed}, hull damage {damage}.")
        print(f"  Target: hull {t['hull']}%  shields {t['shields']}%")
        print(f"  Torpedoes remaining: {w['count']}")
    else:
        if w["charge"] <= 0:
            print("  Phasers depleted.")
            return
        raw = 20
        absorbed = int(raw * shield_factor)
        damage = raw - absorbed
        t["shields"] = max(0, t["shields"] - 10)
        t["hull"]    = max(0, t["hull"] - damage)
        w["charge"]  = max(0, w["charge"] - 25)
        print(f"  Phasers firing — target {tkey} at bearing {t['bearing']}.")
        print(f"  Impact: shields absorbed {absorbed}, hull damage {damage}.")
        print(f"  Target: hull {t['hull']}%  shields {t['shields']}%")
        print(f"  Phaser charge: {w['charge']}%")

    if t["hull"] <= 0:
        print(f"\n  *** {tkey} DESTROYED ***")
        del _ship.targets[tkey]


def cmd_weapon_status(weapon_type):
    wkey = _resolve_weapon(weapon_type)
    if wkey is None:
        print(f"  Unknown weapon '{weapon_type}'.")
        return
    w = _ship.weapons[wkey]
    _heading(f"[ {wkey.upper()} STATUS ]")
    if wkey == "torpedo":
        print(f"  Tubes ready : {'Yes' if w['ready'] else 'No'}")
        print(f"  Count       : {w['count']}")
    else:
        print(f"  Banks  : {w['banks']}")
        print(f"  Charge : {_bar(w['charge'])}")


# ---------------------------------------------------------------------------
# Handlers — crew
# ---------------------------------------------------------------------------

def _print_crew(member):
    _heading(f"[ CREW — {member['name'].upper()} ]")
    print(f"  Name   : {member['name']}")
    print(f"  Rank   : {member['rank'].title()}")
    print(f"  System : {member['system'] or '(none)'}")
    print(f"  Status : {member['status']}")

def _assign_crew(member, system):
    if system not in _ship.systems:
        print(f"  Unknown system '{system}'. Known: {', '.join(_ship.systems)}")
        return
    old = member["system"]
    member["system"] = system
    member["status"] = "on duty"
    if old:
        print(f"  {member['name']} reassigned from {old} to {system}.")
    else:
        print(f"  {member['name']} assigned to {system}.")

def cmd_crew_report_by_name(name):
    m = _find_crew(name=name)
    if m is None:
        print(f"  No crew member named '{name}'. Roster: {', '.join(c['name'] for c in _ship.crew)}")
        return
    _print_crew(m)

def cmd_crew_assign_by_name(name, system):
    m = _find_crew(name=name)
    if m is None:
        print(f"  No crew member named '{name}'.")
        return
    _assign_crew(m, system)

def cmd_crew_report_by_rank(rank):
    m = _find_crew(rank=rank)
    if m is None:
        print(f"  No crew with rank '{rank}'. Ranks: {', '.join(c['rank'] for c in _ship.crew)}")
        return
    _print_crew(m)

def cmd_crew_assign_by_rank(rank, system):
    m = _find_crew(rank=rank)
    if m is None:
        print(f"  No crew with rank '{rank}'.")
        return
    _assign_crew(m, system)


# ---------------------------------------------------------------------------
# Handlers — scan
# ---------------------------------------------------------------------------

def cmd_scan_ships(sector):
    if sector:
        if sector not in _ship.sectors:
            print(f"  No data for sector {sector}. Known: {', '.join(_ship.sectors)}")
            return
        contacts = _ship.sectors[sector]["ships"]
        _heading(f"[ SCAN — SECTOR {sector} — VESSELS ]")
    else:
        contacts = list(_ship.targets.keys())
        _heading("[ SCAN — IMMEDIATE RANGE — VESSELS ]")

    if not contacts:
        print("  No vessels detected.")
        return
    for name in contacts:
        t = _ship.targets.get(name, {})
        dist    = t.get("distance", "unknown")
        bearing = t.get("bearing",  "unknown")
        print(f"  {name:<30}  dist: {dist:<12}  bearing: {bearing}")

    if _ship.systems["sensors"]["power"] < 50:
        print(f"\n  NOTE: Sensor power at {_ship.systems['sensors']['power']}% — scan may be incomplete.")


def cmd_scan_resources(sector):
    if sector:
        if sector not in _ship.sectors:
            print(f"  No data for sector {sector}. Known: {', '.join(_ship.sectors)}")
            return
        resources = _ship.sectors[sector]["resources"]
        _heading(f"[ SCAN — SECTOR {sector} — RESOURCES ]")
    else:
        resources = [r for s in _ship.sectors.values() for r in s["resources"]]
        _heading("[ SCAN — IMMEDIATE RANGE — RESOURCES ]")

    if not resources:
        print("  No resources detected.")
    else:
        for r in resources:
            print(f"  {r}")


# ---------------------------------------------------------------------------
# Handlers — navigation, log, alert
# ---------------------------------------------------------------------------

def cmd_plot_course(destination):
    _ship.position = destination
    print(f"  Course plotted to {destination}.")
    if _ship.warp_factor > 0:
        eta = max(1, 12 // _ship.warp_factor)
        print(f"  At warp {_ship.warp_factor}: ETA approximately {eta} hour(s).")
    else:
        print("  Ship at impulse — engage warp to proceed.")


def cmd_log_add(message):
    _ship.log.append(message)
    print(f"  Log entry recorded.")


def cmd_log_show():
    _heading(f"[ SHIP'S LOG — {_ship.name} ]")
    for i, entry in enumerate(_ship.log, 1):
        print(f"  {i:3}.  {entry}")


def cmd_set_alert(level):
    if level not in ("red", "yellow", "green"):
        print(f"  Unknown alert level '{level}'. Use: red, yellow, green.")
        return
    _ship.alert = level
    print(f"  {_color(level.upper() + ' ALERT', level)}")
    if level == "red" and not _ship.shields_raised:
        _ship.shields_raised = True
        print("  Shields automatically raised.")


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

SYSTEM      = Argument('system')
POWER       = Argument('power',       arg_type=int)
WARP        = Argument('warp_factor', arg_type=int)
CREW_NAME   = Argument('crew_name')
CREW_RANK   = Argument('crew_rank')
WEAPON_TYPE = Argument('weapon_type')
TARGET      = Argument('target')
SECTOR      = Argument('sector')
DEST        = Argument('destination')
LOG_MSG     = Argument('message')
ALERT_LVL   = Argument('alert_level')

bridge = CLI('bridge', description=__doc__)

# --- status ---
bridge.status(cmd_status)

# --- systems ---
bridge.system[SYSTEM].status(cmd_system_status, SYSTEM)
bridge.system[SYSTEM].set.power[POWER](cmd_system_set_power, SYSTEM, POWER)
bridge.system[SYSTEM].repair(cmd_system_repair, SYSTEM)

# --- shields ---
bridge.shields.raise_(cmd_shields_raise)
bridge.shields.lower(cmd_shields_lower)
bridge.shields.set.power[POWER](cmd_shields_set_power, POWER)

# --- engines ---
bridge.engine.engage.warp[WARP](cmd_engage_warp, WARP)
bridge.engine.all.stop(cmd_all_stop)

# --- weapons: "by type <X>" selection, then action ---
bridge.weapon.by.type_[WEAPON_TYPE].fire.at.target[TARGET](cmd_weapon_fire, WEAPON_TYPE, TARGET)
bridge.weapon.by.type_[WEAPON_TYPE].status(cmd_weapon_status, WEAPON_TYPE)

# --- crew: two lookup paths ("named" and "ranked"), same actions ---
# Note: ".name" can't be used as a CLI token — it's a FunctionalSubcommand instance
# attribute. "named" and "ranked" sidestep the issue and read naturally.
bridge.crew.named[CREW_NAME].report(cmd_crew_report_by_name, CREW_NAME)
bridge.crew.named[CREW_NAME].assign.to.system[SYSTEM](cmd_crew_assign_by_name, CREW_NAME, SYSTEM)
bridge.crew.ranked[CREW_RANK].report(cmd_crew_report_by_rank, CREW_RANK)
bridge.crew.ranked[CREW_RANK].assign.to.system[SYSTEM](cmd_crew_assign_by_rank, CREW_RANK, SYSTEM)

# --- scan: sector is optional ---
bridge.scan.for_.ships(cmd_scan_ships, SECTOR)
bridge.scan.for_.resources(cmd_scan_resources, SECTOR)
bridge.scan.sector[SECTOR].for_.ships(cmd_scan_ships, SECTOR)
bridge.scan.sector[SECTOR].for_.resources(cmd_scan_resources, SECTOR)

# --- navigation ---
bridge.course.plot.to.system[DEST](cmd_plot_course, DEST)

# --- log ---
bridge.log.entry.add[LOG_MSG](cmd_log_add, LOG_MSG)
bridge.log.show(cmd_log_show)

# --- alert ---
bridge.alert.set[ALERT_LVL](cmd_set_alert, ALERT_LVL)


if __name__ == '__main__':
    parse_tokens(bridge, sys.argv)
