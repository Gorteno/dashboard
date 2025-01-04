from flask import Flask, render_template, redirect, request, session, flash, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import subprocess
from threading import Thread
from queue import Queue
import psutil
import os


app = Flask(__name__)
app.secret_key = "supergeheimespasswort"

# SQLite-Datenbank konfigurieren
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

# Benutzerverwaltung
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)

# Datenbank initialisieren
with app.app_context():
    db.create_all()

# Discord Bots (Python)
BOTS = {
    "Mr Mauer Bot": {"path": "C:/Byte/main.py", "process": None, "output": Queue(), "pid": None},
    "Byte Bot": {"path": "C:/byteserver/main.py", "process": None, "output": Queue(), "pid": None},
}

GAMESERVERS = {
    "Valheim": {
        "path": "C:/valheim/start_headless_server.bat",  # .bat für Konfiguration
        "exe_path": "C:/valheim/valheim_server.exe",  # .exe für den Server
        "args": "",  # Argumente bereits in der .bat enthalten
        "config": "C:/valheim/config.txt",
        "pid": None,
        "exe_pid": None,
        "output": Queue(),
    },
    "Core Keeper": {
        "path": "C:/core-keeper-server/Launch.bat",  # .bat
        "exe_path": "C:/core-keeper-server/CoreKeeperServer.exe",  # .exe
        "args": "",
        "config": "C:/core-keeper-server/config.json",
        "pid": None,
        "exe_pid": None,
        "output": Queue(),
    },
    "Minecraft - Vanilla": {
        "path": "C:/Minecraft/start.bat",  # .bat für Konfiguration
        "exe_path": None,  # Keine separate Exe, nur .jar
        "args": "",
        "config": "C:/Minecraft/server.properties",
        "pid": None,
        "exe_pid": None,
        "output": Queue(),
    },
    "Minecraft GARPG": {
        "path": "C:/CARPG/start.bat",  # .bat, keine .exe
        "exe_path": "",
        "args": "",
        "config": "C:/CARPG/config.txt",
        "pid": None,
        "exe_pid": None,
        "output": Queue(),
    },
}


# CMD oder PowerShell ausführen und Ausgaben erfassen
def run_script(service, service_data):
    # Bestimme, ob die Datei eine .bat-Datei ist
    if service_data['path'].endswith('.bat'):
        command = f'cmd /c "{service_data["path"]}"'
    else:
        command = f'python "{service_data["path"]}"'

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=True,
        encoding="utf-8",
        errors="replace"
    )
    service_data["process"] = process

    def clean_line(line):
        return line.strip()

    for line in process.stdout:
        cleaned_line = clean_line(line)
        if cleaned_line:
            service_data["output"].put(cleaned_line)

    for line in process.stderr:
        cleaned_line = clean_line(line)
        if cleaned_line:
            service_data["output"].put(cleaned_line)

    process.wait()
    if process.returncode == 0:
        service_data["output"].put("Prozess erfolgreich beendet.")
    else:
        service_data["output"].put(f"Prozess mit Fehlercode {process.returncode} beendet.")
    service_data["process"] = None

# Systemauslastung
def get_system_usage():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    return {"cpu": cpu, "memory": memory}
def get_server_stats():
    return {
        "cpu": psutil.cpu_percent(interval=1),
        "ram": psutil.virtual_memory().percent
    }
@app.route("/")
def index():
    return render_template("index.html", title="Login")

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    user = User.query.filter_by(username=username, password=password).first()
    if user:
        session["user"] = user.username
        return redirect("/bots")
    else:
        flash("Falsche Anmeldedaten!")
        return redirect("/")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

@app.route("/bots")
def bots():
    if "user" not in session:
        return redirect("/")
    return render_template("bots.html", title="Discord Bots", bots=BOTS)

@app.route("/gameservers")
def gameservers():
    if "user" not in session:
        return redirect("/")
    usage = get_system_usage()
    return render_template("gameserver.html", title="Gameserver", gameservers=GAMESERVERS, usage=usage)

@app.route("/gameserver/<name>")
def gameserver_view(name):
    if "user" not in session:
        return redirect("/")
    if name not in GAMESERVERS:
        flash("Gameserver existiert nicht!")
        return redirect("/gameservers")
    return render_template("gameserver_view.html", title=name, server=GAMESERVERS[name], name=name, usage=get_system_usage())

@app.route("/start/<service>")
def start_service(service):
    service_data = BOTS.get(service) or GAMESERVERS.get(service)
    if not service_data:
        return jsonify({"error": "Service existiert nicht"}), 404

    if service_data.get("process") or service_data.get("pid"):
        return jsonify({"error": f"{service} läuft bereits"}), 400

    try:
        if service in BOTS:  # Für Bots
            command = f'python "{service_data["path"]}"'
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True,
                encoding="utf-8",
                errors="replace",
            )
            service_data["process"] = process

        elif service in GAMESERVERS:  # Für Gameserver
            # Starte .bat
            if service_data["path"].endswith(".bat"):
                process = subprocess.Popen(
                    f'cmd /c "{service_data["path"]}"',
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=True,
                    encoding="utf-8",
                    errors="replace",
                )
                service_data["pid"] = process.pid

            # Starte .exe
            if service_data["exe_path"] and service_data["exe_path"].endswith(".exe"):
                exe_process = subprocess.Popen(
                    [service_data["exe_path"]] + service_data["args"].split(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=False,
                )
                service_data["exe_pid"] = exe_process.pid

            # Starte .jar (Minecraft)
            if service_data["path"].endswith(".jar"):
                jar_process = subprocess.Popen(
                    f'java {service_data["args"]}',
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=True,
                    encoding="utf-8",
                    errors="replace",
                )
                service_data["pid"] = jar_process.pid

        # Erfasse Logs
        def capture_output(proc):
            for line in iter(proc.stdout.readline, ""):
                service_data["output"].put(line.strip())
            proc.stdout.close()

            for line in iter(proc.stderr.readline, ""):
                service_data["output"].put(line.strip())
            proc.stderr.close()

        Thread(target=capture_output, args=(process,), daemon=True).start()
        return jsonify({"status": f"{service} gestartet"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/stop/<service>")
def stop_service(service):
    service_data = BOTS.get(service) or GAMESERVERS.get(service)
    if not service_data:
        return jsonify({"error": "Service existiert nicht"}), 404

    if not service_data.get("process") and not service_data.get("pid") and not service_data.get("exe_pid"):
        return jsonify({"error": f"{service} läuft nicht"}), 400

    try:
        # Stoppe .exe
        if service_data.get("exe_pid"):
            parent = psutil.Process(service_data["exe_pid"])
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
            service_data["exe_pid"] = None

        # Stoppe .bat/.jar
        if service_data.get("pid"):
            parent = psutil.Process(service_data["pid"])
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
            service_data["pid"] = None

        # Stoppe Bots
        if service_data.get("process"):
            service_data["process"].terminate()
            service_data["process"] = None

        return jsonify({"status": f"{service} gestoppt"}), 200

    except psutil.NoSuchProcess:
        service_data["pid"] = None
        service_data["exe_pid"] = None
        return jsonify({"status": f"{service} konnte nicht gefunden werden"}), 404

@app.route("/status/<service>")
def server_status(service):
    service_data = BOTS.get(service) or GAMESERVERS.get(service)
    if not service_data:
        return jsonify({"error": "Service existiert nicht"}), 404

    try:
        if service_data.get("process") or service_data.get("pid") or service_data.get("exe_pid"):
            cpu = psutil.cpu_percent(interval=1) / psutil.cpu_count()
            memory = psutil.virtual_memory().percent
            return jsonify({"status": "läuft", "cpu": round(cpu, 2), "memory": round(memory, 2)}), 200
    except psutil.NoSuchProcess:
        service_data["process"] = None
        service_data["pid"] = None
        service_data["exe_pid"] = None

    return jsonify({"status": "gestoppt"}), 200

@app.route("/edit/<name>", methods=["GET", "POST"])
def edit_config(name):
    if "user" not in session:
        return redirect("/")
    if name not in GAMESERVERS:
        flash("Gameserver existiert nicht!")
        return redirect("/gameservers")
    
    config_path = GAMESERVERS[name]["config"]
    if request.method == "POST":
        with open(config_path, "w") as file:
            file.write(request.form["content"])
        flash("Konfiguration gespeichert!")
        return redirect(f"/gameserver/{name}")
    
    with open(config_path, "r") as file:
        content = file.read()
    return render_template("file_editor.html", title=f"{name} - Datei bearbeiten", name=name, content=content)

@app.route('/api/server/stats')
def server_stats():
    stats = {
        "cpu": psutil.cpu_percent(interval=1),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent
    }
    return jsonify(stats)
    
@app.route('/config/<server>', methods=['GET', 'POST'])
def config(server):
    if server not in GAMESERVERS:
        return jsonify({"error": "Server nicht gefunden"}), 404

    config_path = GAMESERVERS[server].get("config")
    if not os.path.exists(config_path):
        return jsonify({"error": "Konfigurationsdatei nicht gefunden"}), 404

    if request.method == 'POST':
        # Bearbeitung der Konfigurationsdatei
        new_content = request.form.get("config", "")
        try:
            with open(config_path, "w") as file:
                file.write(new_content)
            return jsonify({"status": "Konfiguration gespeichert"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Anzeige der Konfigurationsdatei
    try:
        with open(config_path, "r") as file:
            content = file.read()
        return render_template("config.html", server=server, content=content)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
