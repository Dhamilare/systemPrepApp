# client_agent.py
import os
import socket
import platform
import json
import requests
import subprocess
import time

DJANGO_API_URL = "http://127.0.0.1:8000/api/agent/checkin/"
INSTALL_REPORT_URL = "http://127.0.0.1:8000/api/agent/report_installation/"
API_KEY = "2I40nUf9.7WAhdblmBeyxYnwukAKXSyNELLMO7W2F"

INSTALL_DIR = "C:\\Installers"
os.makedirs(INSTALL_DIR, exist_ok=True)

def get_machine_info():
    hostname = platform.node()
    try:
        ip_address = socket.gethostbyname(hostname)
    except socket.gaierror:
        ip_address = "127.0.0.1"
    return {"hostname": hostname, "ip_address": ip_address}

def send_checkin_data(machine_info):
    headers = {"Authorization": f"Api-Key {API_KEY}", "Content-Type": "application/json"}
    try:
        response = requests.post(DJANGO_API_URL, data=json.dumps(machine_info), headers=headers)
        response.raise_for_status()
        return response.json().get("id")
    except Exception as e:
        print(f"Check-in failed: {e}")
        return None

def fetch_tasks(machine_id):
    headers = {"Authorization": f"Api-Key {API_KEY}", "X-Hostname": platform.node()}
    try:
        response = requests.get(f"http://127.0.0.1:8000/api/agent/tasks/{machine_id}/", headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to fetch tasks: {e}")
        return None

def download_installer(url, filename):
    path = os.path.join(INSTALL_DIR, filename)
    if os.path.exists(path):
        return path
    try:
        r = requests.get(url, stream=True)
        with open(path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return path
    except Exception as e:
        print(f"Download failed: {e}")
        return None

def run_installer(command):
    try:
        result = subprocess.run(command, shell=True, timeout=1800)
        return result.returncode == 0
    except Exception as e:
        print(f"Installation error: {e}")
        return False

def install_office():
    xml_path = os.path.join(INSTALL_DIR, "office.xml")
    with open(xml_path, 'w') as f:
        f.write("""
<Configuration>
  <Add OfficeClientEdition=\"64\" Channel=\"Current\">
    <Product ID=\"O365ProPlusRetail\">
      <Language ID=\"en-us\" />
    </Product>
    <Product ID=\"ProjectProRetail\">
      <Language ID=\"en-us\" />
    </Product>
    <Product ID=\"VisioProRetail\">
      <Language ID=\"en-us\" />
    </Product>
  </Add>
  <Display Level=\"None\" AcceptEULA=\"TRUE\" />
  <Property Name=\"AUTOACTIVATE\" Value=\"1\"/>
</Configuration>
        """)
    setup_exe = download_installer("https://officecdn.microsoft.com/pr/wsus/setup.exe", "setup.exe")
    if setup_exe:
        return run_installer(f'"{setup_exe}" /configure "{xml_path}"')
    return False

def enable_hyperv():
    cmd = "dism /Online /Enable-Feature /All /FeatureName:Microsoft-Hyper-V"
    return run_installer(cmd)

def report_installation(machine_id, installed_tools):
    headers = {"Authorization": f"Api-Key {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "machine_id": machine_id,
        "installed_tools": installed_tools,
        "status": "completed"
    }
    try:
        r = requests.post(INSTALL_REPORT_URL, data=json.dumps(payload), headers=headers)
        r.raise_for_status()
        print("Reported installation status.")
    except Exception as e:
        print(f"Failed to report installation: {e}")

def install_tool(tool):
    name = tool['name'].lower()
    url = tool.get('download_link')
    if not url:
        return (tool['name'], False)

    filename = name.replace(' ', '_') + ".exe"
    path = download_installer(url, filename)
    if not path:
        return (tool['name'], False)

    # Install using silent switches
    if "chrome" in name:
        cmd = f'"{path}" /silent /install'
    elif "acrobat" in name:
        cmd = f'"{path}" /sAll'
    elif "openvpn" in name:
        cmd = f'"{path}" /S'
    elif "docker" in name:
        cmd = f'"{path}" install --quiet'
    elif "power bi" in name:
        cmd = f'"{path}" /quiet'
    elif "putty" in name:
        cmd = f'"{path}" /VERYSILENT'
    elif "figma" in name:
        cmd = f'"{path}" /S'
    else:
        cmd = f'"{path}" /quiet /norestart'

    return (tool['name'], run_installer(cmd))

def main():
    info = get_machine_info()
    machine_id = send_checkin_data(info)
    if not machine_id:
        return

    task_data = fetch_tasks(machine_id)
    if not task_data:
        return

    installed = []
    required = task_data.get("required_tools", []) + task_data.get("optional_tools_assigned", [])
    checklist = task_data.get("checklist_items_status", [])

    for tool in required:
        if "office" in tool['name'].lower():
            success = install_office()
            installed.append({"tool": tool['name'], "status": "success" if success else "failed"})
        elif "hyper-v" in tool['name'].lower():
            success = enable_hyperv()
            installed.append({"tool": tool['name'], "status": "success" if success else "failed"})
        else:
            name, success = install_tool(tool)
            installed.append({"tool": name, "status": "success" if success else "failed"})

    report_installation(machine_id, installed)

if __name__ == "__main__":
    main()
