"""
This module provides a test library for running integration tests and scenes.
"""
import threading
import time
import requests
import psutil
from web_app import app
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def _run_app():
    """Runs the Flask app in a separate process."""
    # Note: debug=False is important for this to run in a separate process
    app.run(port=5001, debug=False, use_reloader=False)

def _shutdown_server():
    """Finds and terminates any process listening on port 5001."""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            p = psutil.Process(proc.info['pid'])
            for conn in p.connections(kind='inet'):
                if conn.laddr.port == 5001:
                    print(f"Found server process {proc.pid} ({proc.info['name']}). Terminating.")
                    p.terminate()
                    p.wait(timeout=5)
                    return
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    print("Could not find a server process to shut down.")

class TestHarness:
    """
    A test harness for running integration tests and scenes.
    """
    def __init__(self):
        self.server_thread = None
        self.driver = None
        self.server_url = "http://127.0.0.1:5001/"

    def setup(self):
        """Starts the server and the browser."""
        self.server_thread = threading.Thread(target=_run_app)
        self.server_thread.daemon = True
        self.server_thread.start()
        print("🚀 Starting server...")
        time.sleep(3)  # Wait for the server to start

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        print("🌐 Browser started.")
        self.driver.get(self.server_url)

    def teardown(self):
        """Shuts down the server and the browser."""
        if self.driver:
            self.driver.quit()
        _shutdown_server()
        print("\n🛑 Server and browser have been shut down.")

    def set_entity_data_dirs(self, data_dirs: list[str]):
        """Tells the running app to re-initialize its database from a new set of directories."""
        response = requests.post(f"{self.server_url}reinitialize_db", json={"data_dirs": data_dirs})
        if response.status_code == 200:
            print(f"✔️ DB re-initialized with data from: {data_dirs}")
        else:
            print(f"❌ Failed to re-initialize DB. Status: {response.status_code}, Response: {response.text}")

    def set_location(self, location_id: str):
        """Sets the player's location."""
        requests.post(f"{self.server_url}set_location", json={"location_id": location_id})
        print(f"📍 Location set to: {location_id}")
        # Reload the page to reflect the new location
        self.driver.get(self.server_url)

    def send_command(self, command: str) -> str:
        """Sends a command to the chat and returns the game's response."""
        chat_input = self.driver.find_element(By.ID, "chat-input")
        send_button = self.driver.find_element(By.ID, "send-button")
        
        # Get the number of messages before sending the new one
        initial_message_count = len(self.driver.find_elements(By.CSS_SELECTOR, "#chat-box .chat-message"))
        
        chat_input.send_keys(command)
        send_button.click()
        print(f"\n⌨️ Executed command: '{command}'")

        # Wait for the new message to appear
        wait = WebDriverWait(self.driver, 10)
        wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "#chat-box .chat-message")) >= initial_message_count + 2) # User and game message
        
        chat_messages = self.driver.find_elements(By.CSS_SELECTOR, "#chat-box .chat-message")
        game_response = chat_messages[-1].text
        print(f"🕵️ Game response: '{game_response}'")
        return game_response 