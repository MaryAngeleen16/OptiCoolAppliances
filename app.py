from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route('/appliancesconsumption', methods=['GET'])
def appliancesconsumption():
    # === Step 1: Fetch data from endpoints ===
    power_url = "https://opticoolweb-backend.onrender.com/api/v1/powerconsumptions"
    logs_url = "https://opticoolweb-backend.onrender.com/api/v1/activity-logs"

    try:
        power_data = requests.get(power_url).json()
        activity_logs = requests.get(logs_url).json()
    except Exception as e:
        return jsonify({"error": "Failed to fetch data", "details": str(e)}), 500

    # === Step 2: Appliance wattage map ===
    wattage = {
        "AC 1": 1850,
        "AC 2": 1510,
        "Fan 1": 65,
        "Fan 2": 65,
        "Fan 3": 65,
        "Fan 4": 65,
        "Exhaust 1": 50,
        "Exhaust 2": 50,
        "Blower 1": 200
    }

    # === Step 3: Parse activity logs to ON/OFF timeline ===
    appliance_timelines = defaultdict(list)
    for log in activity_logs:
        if "timestamp" not in log or "action" not in log:
            continue  # skip invalid log

        ts = datetime.fromisoformat(log["timestamp"].replace("Z", "+00:00"))
        action_text = log["action"]

        for name in wattage:
            if name in action_text:
                state = "on" if "Turned on" in action_text else "off"
                appliance_timelines[name].append((state, ts))
                break
        else:
            if "Aircon" in action_text:
                state = "on" if "Turned on" in action_text else "off"
                appliance_timelines["AC 1"].append((state, ts))

    # === Step 4: Build power timeline with active devices ===
    power_records = []
    for record in power_data:
        if "timestamp" not in record or "consumption" not in record:
            continue
        ts = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
        power = record["consumption"]

        active = []
        for appliance, changes in appliance_timelines.items():
            current_state = None
            for state, state_ts in sorted(changes, key=lambda x: x[1]):
                if state_ts <= ts:
                    current_state = state
                else:
                    break
            if current_state == "on":
                active.append(appliance)

        power_records.append({"timestamp": ts, "power": power, "active": active})

    # === Step 5: Calculate usage per appliance ===
    consumption = defaultdict(float)
    for i in range(1, len(power_records)):
        t0 = power_records[i - 1]
        t1 = power_records[i]
        duration = (t1["timestamp"] - t0["timestamp"]).total_seconds() / 3600  # hours

        if not t0["active"]:
            continue

        total_watts = sum(wattage[a] for a in t0["active"])

        for appliance in t0["active"]:
            share = wattage[appliance] / total_watts
            consumption[appliance] += share * t0["power"] * duration

    # === Step 6: Prepare response ===
    result = [
        {"appliance": a, "energy_wh": round(wh, 2)}
        for a, wh in consumption.items()
    ]

    return jsonify({"appliance_consumption": result})

if __name__ == '__main__':
    app.run(port=5000)
# 