import requests
import socket
import platform
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime

# === CONFIGURATION ===
DJANGO_API_URL = "http://127.0.0.1:8000/api"
API_KEY = "2I40nUf9.7WAhdblmBeyxYnwukAKXSyNELLMO7W2F"
INSTALL_DIR = Path("C:/Installers")

OFFICE_XML = """
<Configuration>
  <Add OfficeClientEdition="64" Channel="Current">
    <Product ID="O365ProPlusRetail">
      <Language ID="en-us" />
    </Product>
  </Add>
  <Display Level="None" AcceptEULA="TRUE" />
  <Property Name="AUTOACTIVATE" Value="1"/>
</Configuration>
"""

HEADERS = {
    "Authorization": f"Api-Key {API_KEY}",
    "Content-Type": "application/json"
}

# === SYSTEM INFO ===
def get_machine_info():
    hostname = platform.node()
    try:
        ip_address = socket.gethostbyname(hostname)
    except socket.gaierror:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except:
            ip_address = "N/A"
    return {"hostname": hostname, "ip_address": ip_address}

# === API COMMUNICATION ===
def register_machine(machine_info):
    try:
        response = requests.post(f"{DJANGO_API_URL}/agent/checkin/", headers=HEADERS, data=json.dumps(machine_info))
        response.raise_for_status()
        return response.json().get("id")
    except Exception as e:
        print(f"[ERROR] Machine registration failed: {e}")
        return None

def fetch_tasks(machine_id, hostname):
    try:
        response = requests.get(f"{DJANGO_API_URL}/agent/tasks/{machine_id}/", headers={**HEADERS, "X-Hostname": hostname})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch tasks: {e}")
        return None

def update_checklist(machine_id, checklist_items):
    completed = []
    for item in checklist_items:
        completed.append({
            "checklist_item_id": item["id"],
            "status": "COMPLETED",
            "notes": "Automatically completed by agent."
        })

    payload = {"checklist_statuses": completed}
    try:
        r = requests.post(f"{DJANGO_API_URL}/machine/{machine_id}/checklist_status/", headers=HEADERS, json=payload)
        r.raise_for_status()
        print("[✓] Checklist updated successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to update checklist: {e}")

# === FILE HANDLING & INSTALLATION ===
def download_file(url, dest_path):
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

def install_office_odt():
    print("[...] Installing Microsoft 365 via ODT...")
    setup_exe = INSTALL_DIR / "OfficeSetup.exe"
    config_xml = INSTALL_DIR / "config.xml"

    # Download ODT setup.exe from official source
    odt_url = "https://aka.ms/officeinstall"
    download_file(odt_url, setup_exe)

    # Write config
    with open(config_xml, "w") as f:
        f.write(OFFICE_XML)

    subprocess.run([str(setup_exe), "/configure", str(config_xml)], check=True)

def install_application(tool):
    name = tool["name"]
    url = tool.get("download_link")
    result = {"tool": name, "status": "FAILED", "details": "", "timestamp": datetime.now().isoformat()}

    try:
        if "office" in name.lower():
            install_office_odt()
            result["status"] = "INSTALLED"
            result["details"] = "Installed using ODT"
            return result

        if not url:
            result["details"] = "No download link provided"
            return result

        filename = INSTALL_DIR / f"{name.replace(' ', '_')}.exe"
        print(f"[...] Downloading {name}...")
        download_file(url, filename)
        print(f"[...] Installing {name}...")
        subprocess.run([str(filename), "/quiet", "/norestart"], check=True)
        result["status"] = "INSTALLED"
        result["details"] = "Downloaded and executed successfully"
    except subprocess.CalledProcessError as e:
        result["details"] = f"Installer exited with code {e.returncode}"
    except Exception as e:
        result["details"] = str(e)

    return result

# === MAIN EXECUTION FLOW ===
def main():
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    machine_info = get_machine_info()
    machine_id = register_machine(machine_info)
    if not machine_id:
        return

    tasks = fetch_tasks(machine_id, machine_info["hostname"])
    if not tasks:
        return

    tools = tasks.get("required_tools", []) + tasks.get("optional_tools_assigned", [])
    checklist = tasks.get("checklist_items_status", [])

    install_log = []

    for tool in tools:
        result = install_application(tool)
        install_log.append(result)
        print(f"[{result['status']}] {result['tool']}: {result['details']}")

    update_checklist(machine_id, checklist)

    # Save local log
    log_path = INSTALL_DIR / f"install_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_path, "w") as f:
        json.dump(install_log, f, indent=2)
    print(f"[✓] Installation log saved to {log_path}")

if __name__ == "__main__":
    main()
