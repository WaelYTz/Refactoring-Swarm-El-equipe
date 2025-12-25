import json
import os
from datetime import datetime
import uuid

LOG_FILE = os.path.join("logs", "experiment_data.json")

def log_experiment(agent_name: str, action: str, details: str, status: str = "INFO", model_used: str = "unknown"):
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "agent": agent_name,
        "model": model_used,
        "action": action,
        "details": details,
        "status": status
    }

    data = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = []
    data.append(entry)
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)