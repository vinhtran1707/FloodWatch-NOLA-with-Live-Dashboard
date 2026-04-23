from datetime import datetime

DEMO_MODE = True

STATUS_COLORS = {
    "PUMPING": "#10b981",
    "STANDBY": "#f59e0b",
    "OFFLINE": "#ef4444",
    "TESTING": "#3b82f6",
}


def get_swbno_status() -> dict:
    return {
        "timestamp": datetime.now().isoformat(),
        "source": "SWBNO PumpingAndPower Dashboard (Demo Data)",
        "pumps_total": 93,
        "pumps_available": 87,
        "pumps_standby": 4,
        "pumps_offline": 2,
        "turbines_total": 3,
        "turbines_online": 2,
        "turbine_4_status": "Emergency Standby",
        "sfc2_note": "30-day reliability test in progress",
        "system_capacity_pct": 93.5,
        "stations": [
            {
                "id": "DPS-02",
                "name": "Mid-City Station",
                "neighborhood": "Mid-City",
                "status": "PUMPING",
                "capacity_cfs": 1250,
                "operational_pct": 95,
            },
            {
                "id": "DPS-07",
                "name": "Lakeview Station",
                "neighborhood": "Lakeview",
                "status": "STANDBY",
                "capacity_cfs": 980,
                "operational_pct": 0,
            },
            {
                "id": "DPS-12",
                "name": "Gentilly Station",
                "neighborhood": "Gentilly",
                "status": "PUMPING",
                "capacity_cfs": 1100,
                "operational_pct": 78,
            },
            {
                "id": "DPS-19",
                "name": "Broadmoor Station",
                "neighborhood": "Broadmoor",
                "status": "OFFLINE",
                "capacity_cfs": 870,
                "operational_pct": 0,
            },
            {
                "id": "DPS-24",
                "name": "Bywater Station",
                "neighborhood": "Bywater",
                "status": "PUMPING",
                "capacity_cfs": 760,
                "operational_pct": 88,
            },
            {
                "id": "DPS-31",
                "name": "Tremé Station",
                "neighborhood": "Tremé",
                "status": "PUMPING",
                "capacity_cfs": 640,
                "operational_pct": 91,
            },
            {
                "id": "DPS-38",
                "name": "Algiers Station",
                "neighborhood": "Algiers",
                "status": "PUMPING",
                "capacity_cfs": 820,
                "operational_pct": 82,
            },
            {
                "id": "SFC2",
                "name": "Superpump SFC2",
                "neighborhood": "System-Wide",
                "status": "TESTING",
                "capacity_cfs": 3200,
                "operational_pct": 40,
            },
        ],
        "drainage_basins": [
            {
                "basin": "Metairie Ridge",
                "pump_coverage": "High",
                "notes": "All stations operational",
            },
            {
                "basin": "Gentilly",
                "pump_coverage": "Medium",
                "notes": "DPS-12 at 78% capacity",
            },
            {
                "basin": "Broadmoor",
                "pump_coverage": "Critical",
                "notes": "DPS-19 offline — reduced drainage",
            },
            {
                "basin": "Lakeview",
                "pump_coverage": "Standby",
                "notes": "DPS-07 on standby, manual activation required",
            },
        ],
    }
