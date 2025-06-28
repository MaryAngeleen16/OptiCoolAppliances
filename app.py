from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import requests
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route('/appliancesconsumption', methods=['GET'])
def appliancesconsumption():
    power_url = "https://opticoolweb-backend.onrender.com/api/v1/powerconsumptions"
    logs_url = "https://opticoolweb-backend.onrender.com/api/v1/activity-log"

    try:
        power_data = requests.get(power_url).json()
        activity_logs = requests.get(logs_url).json()
    except Exception as e:
        return jsonify({"error": "Failed to fetch data", "details": str(e)}), 500

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

    appliance_timelines = defaultdict(list)
    for log in activity_logs:
        if "timestamp" not in log or "action" not in log:
            continue
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

    consumption = defaultdict(float)
    for i in range(1, len(power_records)):
        t0 = power_records[i - 1]
        t1 = power_records[i]
        duration = (t1["timestamp"] - t0["timestamp"]).total_seconds() / 3600
        if not t0["active"]:
            continue
        total_watts = sum(wattage[a] for a in t0["active"])
        for appliance in t0["active"]:
            share = wattage[appliance] / total_watts
            consumption[appliance] += share * t0["power"] * duration

    result = [{"appliance": a, "energy_wh": round(wh, 2)} for a, wh in consumption.items()]

    # === Render HTML output with a popup ===
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Appliance Consumption</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            .modal { display: block; position: fixed; z-index: 1; left: 0; top: 0;
                     width: 100%; height: 100%; overflow: auto;
                     background-color: rgba(0,0,0,0.4); }
            .modal-content { background-color: #fefefe; margin: 10% auto; padding: 20px;
                             border: 1px solid #888; width: 80%; max-width: 600px; border-radius: 10px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #ccc; padding: 8px; }
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>

        <div class="modal">
            <div class="modal-content">
                <h2>Appliance Energy Consumption</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Appliance</th>
                            <th>Energy Used (Wh)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in result %}
                        <tr>
                            <td>{{ item.appliance }}</td>
                            <td>{{ item.energy_wh }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

    </body>
    </html>
    """

    return render_template_string(html_template, result=result)

if __name__ == '__main__':
    app.run(port=5000)
