import sys
import os
import time
import uuid
import logging
from flask import Flask, jsonify, request, render_template

# Add Project Root to Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [Dashboard] - %(message)s')
logger = logging.getLogger("Dashboard")

# --- GLOBAL STATE ---
STATE = {
    "queue": [],
    "history": [],
    "current_job": None,
    
    # Telemetry
    "robot_status": "Offline",     
    "printer_status": "Offline",
    "printer_temp": 0.0,
    "job_progress": 0.0,
    "printer_console": [] 
}

# Settings (User Adjustable)
SETTINGS = {
    "system_paused": False,
    "bed_cooldown_target": 45.0,
    "speed_override": 1.0,
    "auto_harvest": True,
    "skip_inspection": False,
    "material_remaining_g": 1000.0,
    "material_low_threshold": 200.0
}

# --- ROUTES ---
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/dashboard_data')
def get_dashboard_data():
    return jsonify({
        "telemetry": {
            "robot": STATE['robot_status'],
            "printer": STATE['printer_status'],
            "temp": STATE['printer_temp'],
            "progress": STATE['job_progress'],
            "console": STATE['printer_console'] 
        },
        "queue": STATE['queue'],
        "history": STATE['history'][-10:],
        "current_job": STATE['current_job'],
        "settings": SETTINGS,
        "flags": {
            "paused": SETTINGS['system_paused'],
            "material_alert": SETTINGS['material_remaining_g'] < SETTINGS['material_low_threshold']
        }
    })

@app.route('/api/status/update', methods=['POST'])
def update_status():
    """Called by Orchestrator to report health."""
    data = request.json
    STATE['robot_status'] = data.get('robot', STATE['robot_status'])
    STATE['printer_status'] = data.get('printer', STATE['printer_status'])
    STATE['printer_temp'] = data.get('temp', 0.0)
    STATE['job_progress'] = data.get('progress', 0.0)
    
    if 'console' in data:
        STATE['printer_console'] = data['console']
        
    return jsonify({"status": "updated"})

# --- JOB MANAGEMENT ---
@app.route('/api/jobs', methods=['POST'])
def add_job():
    data = request.json
    if not data or 'gcode' not in data:
        return jsonify({"error": "No G-Code"}), 400

    job_id = str(uuid.uuid4())[:8]
    job = {
        "id": job_id,
        "name": data.get('name', f"Job_{job_id}"),
        "gcode": data['gcode'], 
        "metadata": data.get('metadata', {}),
        "created_at": time.time(),
        "status": "pending",
        "material_est_g": data.get('material_est', 50.0)
    }
    STATE['queue'].append(job)
    logger.info(f"➕ Job Added: {job_id}")
    return jsonify({"status": "queued", "job_id": job_id})

@app.route('/api/jobs/next', methods=['GET'])
def pop_job():
    if SETTINGS['system_paused'] or STATE['current_job']:
        return jsonify(None), 204

    if STATE['queue']:
        # Material Check
        if SETTINGS['material_remaining_g'] < STATE['queue'][0]['material_est_g']:
            SETTINGS['system_paused'] = True
            logger.warning("⚠️ Material Low - Pausing Queue")
            return jsonify(None), 204

        job = STATE['queue'].pop(0)
        job['started_at'] = time.time()
        STATE['current_job'] = job
        SETTINGS['material_remaining_g'] -= job['material_est_g']
        
        logger.info(f"🚀 Dispatching {job['id']}")
        
        return jsonify({
            "job": job,
            "settings": {
                "bed_temp": SETTINGS['bed_cooldown_target'],
                "speed": SETTINGS['speed_override'],
                "auto_harvest": SETTINGS['auto_harvest']
            }
        })
    return jsonify(None), 204

@app.route('/api/jobs/<job_id>/complete', methods=['POST'])
def complete_job(job_id):
    if STATE['current_job'] and STATE['current_job']['id'] == job_id:
        finished = STATE['current_job']
        finished['result'] = request.json
        STATE['history'].append(finished)
        STATE['current_job'] = None
        logger.info(f"✅ Job {job_id} Finished")
        return jsonify({"status": "ok"})
    return jsonify({"error": "Mismatch"}), 400

# --- NEW: FORCE CLEAR ENDPOINT ---
@app.route('/api/jobs/force_clear', methods=['POST'])
def force_clear():
    """Manually resets the current job and status."""
    if STATE['current_job']:
        logger.warning(f"⚠️ User Force-Cleared Job {STATE['current_job']['id']}")
        STATE['current_job'] = None
    
    # Also reset status text just in case
    STATE['printer_status'] = "Idle"
    STATE['job_progress'] = 0.0
    
    return jsonify({"status": "cleared"})

# --- CONTROLS ---
@app.route('/api/queue/control', methods=['POST'])
def queue_control():
    action = request.json.get('action')
    if action == 'pause': SETTINGS['system_paused'] = True
    elif action == 'resume': SETTINGS['system_paused'] = False
    return jsonify({"status": "ok"})

@app.route('/api/settings/update', methods=['POST'])
def update_settings():
    data = request.json
    for k, v in data.items():
        if k in SETTINGS: SETTINGS[k] = v
    return jsonify({"status": "updated"})

@app.route('/api/maintenance/refill', methods=['POST'])
def refill():
    amt = request.json.get('amount', 1000)
    SETTINGS['material_remaining_g'] = float(amt)
    return jsonify({"status": "ok"})

@app.route('/api/emergency/stop', methods=['POST'])
def estop():
    logger.critical("🚨 ESTOP TRIGGERED")
    SETTINGS['system_paused'] = True
    return jsonify({"status": "ESTOP"})

@app.route('/api/jobs/<job_id>/delete', methods=['POST'])
def delete_job(job_id):
    STATE['queue'] = [j for j in STATE['queue'] if j['id'] != job_id]
    return jsonify({"status": "deleted"})

@app.route('/api/jobs/<job_id>/promote', methods=['POST'])
def promote_job(job_id):
    # Find index first to avoid race conditions with remove/insert
    try:
        idx = next((i for i, j in enumerate(STATE['queue']) if j['id'] == job_id), -1)
        
        if idx > 0: # If found and not already top
            job = STATE['queue'].pop(idx)
            STATE['queue'].insert(0, job)
            logger.info(f"⬆️ Promoted job {job_id} to top of queue")
            return jsonify({"status": "promoted"})
        elif idx == 0:
            return jsonify({"status": "already_top"})
        
        return jsonify({"error": "Not found"}), 404
        
    except Exception as e:
        logger.error(f"Error promoting job: {e}")
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)