# client_agent.py

import requests
import socket
import platform
import json
import os

DJANGO_API_URL = "http://127.0.0.1:8000/api/agent/checkin/"
API_KEY = "2I40nUf9.7WAhdblmBeyxYnwukAKXSyNELLMO7W2F" # <--- REPLACE THIS WITH YOUR ACTUAL KEY!

def get_machine_info():
    """Gathers hostname and primary IP address of the machine."""
    hostname = platform.node() # More robust than socket.gethostname() for some cases
    ip_address = None
    try:
        ip_address = socket.gethostbyname(hostname)
    except socket.gaierror:
        print("Warning: Could not determine IP address for hostname.")
        # Fallback for systems where hostname might not resolve to an IP easily
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80)) # Connect to a public DNS server
            ip_address = s.getsockname()[0]
            s.close()
        except Exception as e:
            print(f"Warning: Failed to get IP address using fallback: {e}")
            ip_address = "N/A" # Indicate failure to get IP

    return {
        "hostname": hostname,
        "ip_address": ip_address
    }

def send_checkin_data(machine_info):
    """Sends machine information to the Django API."""
    headers = {
        "Authorization": f"Api-Key {API_KEY}", # Use 'Api-Key' prefix
        "Content-Type": "application/json"
    }

    print(f"Attempting to send data: {machine_info}")
    try:
        response = requests.post(DJANGO_API_URL, data=json.dumps(machine_info), headers=headers)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)

        response_data = response.json()
        print("Check-in successful!")
        print(f"Server response: {json.dumps(response_data, indent=2)}")
        return True
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - {response.text}")
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Connection error occurred: {conn_err}. Is the Django server running and accessible?")
    except requests.exceptions.Timeout as timeout_err:
        print(f"Timeout error occurred: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"An unexpected request error occurred: {req_err}")
    except json.JSONDecodeError:
        print(f"Failed to decode JSON response: {response.text}")

    return False

if __name__ == "__main__":
    if API_KEY == "YOUR_GENERATED_API_KEY_HERE":
        print("ERROR: Please replace 'YOUR_GENERATED_API_KEY_HERE' in client_agent.py with your actual API Key.")
    else:
        info = get_machine_info()
        send_checkin_data(info)