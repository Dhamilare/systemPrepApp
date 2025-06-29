import os
import sys
import json
import socket
import platform
import logging
import requests
import psutil
import uuid

# --- Configuration ---
API_URL = "http://127.0.0.1:8000"
API_KEY = "2I40nUf9.7WAhdblmBeyxYnwukAKXSyNELLMO7W2F"
CHECKIN_ENDPOINT = f"{API_URL}/agent/checkin/"
LOOKUP_ENDPOINT = f"{API_URL}/agent/lookup/?hostname={{}}"
TASKS_ENDPOINT = f"{API_URL}/agent/tasks/{{machine_id}}/"
REPORT_ENDPOINT = f"{API_URL}/agent/completed/"
INSTALL_DIR = "C:\\Installers"

# --- Logging Setup ---
os.makedirs(INSTALL_DIR, exist_ok=True)
LOG_FILE = os.path.join(INSTALL_DIR, "agent_log.txt")
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# --- Machine Info ---
def get_machine_info():
    return {
        "hostname": socket.gethostname(),
        "ip_address": socket.gethostbyname(socket.gethostname()),
        "is_lead": False,
        "assigned_user": os.getenv("USERNAME", "Unknown"),
        "os": platform.system() + " " + platform.release(),
        "cpu": platform.processor(),
        "ram": f"{round(psutil.virtual_memory().total / (1024**3))} GB",
        "mac_address": ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff)
                                 for ele in range(0, 8*6, 8)][::-1])
    }

# --- Download Utility ---
def download_file(url, dest_path):
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info(f"Downloaded: {url}")
        return True
    except Exception as e:
        logging.info(f"Failed to download {url}: {e}")
        return False

# --- Office Family Installers ---
def install_office_odt(product_id, product_name):
    setup_path = os.path.join(INSTALL_DIR, f"{product_name}_setup.exe")
    config_path = os.path.join(INSTALL_DIR, f"{product_name}_config.xml")

    xml_config = f"""
<Configuration>
  <Add OfficeClientEdition="64" Channel="Current">
    <Product ID="{product_id}">
      <Language ID="en-us" />
    </Product>
  </Add>
  <Display Level="None" AcceptEULA="TRUE" />
  <Property Name="AUTOACTIVATE" Value="1"/>
</Configuration>
"""

    if not os.path.exists(setup_path):
        odt_url = "https://download.microsoft.com/download/0/e/5/0e50a2db-f3c8-4a19-bd65-84ce4d57f55e/setup.exe"
        if not download_file(odt_url, setup_path):
            return False

    with open(config_path, "w") as f:
        f.write(xml_config)

    result = os.system(f'"{setup_path}" /configure "{config_path}"')
    if result == 0:
        logging.info(f"✅ {product_name} installed successfully.")
        return True
    else:
        logging.info(f"❌ {product_name} installation failed.")
        return False

def install_office():
    return install_office_odt("O365ProPlusRetail", "Office")

def install_visio():
    return install_office_odt("VisioProRetail", "Visio")

def install_project():
    return install_office_odt("ProjectProRetail", "Project")

# --- Generic Installer ---
def install_tool(tool):
    name = tool['name']
    download_link = tool.get('download_link', '')
    installer_path = os.path.join(INSTALL_DIR, f"{name}.exe")

    # Office-family routing
    name_lower = name.lower()
    if "office" in name_lower:
        return install_office()
    elif "visio" in name_lower:
        return install_visio()
    elif "project" in name_lower:
        return install_project()

    if not download_link:
        logging.info(f"No download URL for tool: {name}")
        return False

    if not os.path.exists(installer_path):
        if not download_file(download_link, installer_path) is True:
            return False

    logging.info(f"Installing {name}...")
    result = os.system(f'"{installer_path}" /quiet /norestart')
    if result == 0:
        logging.info(f"✅ {name} installed successfully.")
        return True
    else:
        logging.info(f"❌ {name} installation failed.")
        return False

# --- Agent Runner ---
def run_agent():
    machine_info = get_machine_info()
    headers = {
        "Authorization": f"Api-Key {API_KEY}",
        "Content-Type": "application/json"
    }

    # Step 1: Lookup by hostname
    try:
        hostname = machine_info['hostname']
        res = requests.get(LOOKUP_ENDPOINT.format(hostname), headers=headers)
        if res.status_code == 200:
            machine_data = res.json()
            machine_id = machine_data['id']
            logging.info(f"✅ Machine already registered: {hostname} (ID: {machine_id})")
        else:
            raise Exception("Not found")
    except:
        logging.info("🛰️  Registering machine to server...")
        try:
            res = requests.post(CHECKIN_ENDPOINT, json=machine_info, headers=headers)
            res.raise_for_status()
            machine_data = res.json()
            machine_id = machine_data['id']
            logging.info(f"✅ Check-in successful: {hostname} (ID: {machine_id})")
        except Exception as e:
            logging.info(f"❌ Check-in failed: {e}")
            return

    # Step 2: Department assigned?
    if not machine_data.get("department"):
        logging.info("❌ Department is not yet assigned. Please assign this machine via dashboard before proceeding.")
        return

    # Step 3: Fetch assigned tools
    try:
        logging.info("📦 Fetching assigned tools...")
        res = requests.get(TASKS_ENDPOINT.format(machine_id=machine_id), headers=headers)
        res.raise_for_status()
        task_data = res.json()
        tools = task_data.get("required_tools", []) + task_data.get("optional_tools_assigned", [])
    except Exception as e:
        logging.info(f"❌ Failed to fetch tasks: {e}")
        return

    # Step 4: Install each tool
    installed = []
    for tool in tools:
        if install_tool(tool):
            installed.append(tool['name'])

    # Step 5: Report completion
    try:
        payload = {
            "machine_id": machine_id,
            "status": "completed",
            "installed_tools": installed
        }
        res = requests.post(REPORT_ENDPOINT, json=payload, headers=headers)
        res.raise_for_status()
        logging.info("✅ Installation report sent successfully.")
    except Exception as e:
        logging.info(f"❌ Failed to report installation status: {e}")

# --- Entrypoint ---
def main():
    run_agent()
    logging.info("🎉 Agent finished. Press Enter to exit.")
    input()

if __name__ == "__main__":
    main()
