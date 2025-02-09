"""
Description:
    A simple bot for Path of Exile 2 that monitors the player's health, mana, or shield values.
    The bot will send an escape key press to the game window if the player's selected resource falls below a certain
    threshold.

    The bot will also block the escape and space keys for 2 seconds after sending the escape key press to prevent
    accidental double presses.

    Requirements:
        - Python 3.9+
        - pymem
        - pywin32
        - keyboard
        - tkinter
"""


import os
import time
import threading

import pymem
import win32api
import win32con
import win32gui  # pywin32

import tkinter as tk
import keyboard


# Resource configuration
# Base and offsets are used to calculate the memory address of the resource value. This is specific to the game's
# memory layout and may, unfortunately, change with game updates.
# TODO: Add a way to automatically find the base and offsets.
RESOURCE_CONFIG = {
    "hp": {
         "base": 0x03BA8868,
         "offsets": [0x98, 0x68, 0x474],
         "default_threshold": 500
    },
    "mp": {
         "base": 0x03CCF4F8,
         "offsets": [0x58, 0x0, 0x110, 0xF8, 0x1A0, 0x19C],
         "default_threshold": 500
    },
    "ms": {
         "base": 0x038AD5B8,
         "offsets": [0xC8, 0x18, 0x110, 0xF8, 0x1A0, 0x1A0],
         "default_threshold": 10
    }
}


class Resource:
    """
    Resource class to store the base address, offsets, and default threshold for a resource.
    """
    def __init__(self, name: str, base: int, offsets: list, default_threshold: int):
        self.name = name
        self.base = base
        self.offsets = offsets
        self.threshold = default_threshold

    def calculate_address(self, pm: pymem.Pymem, process_name: str):
        """
        Calculate the memory address of the resource value.
        :param pm:
        :param process_name:
        :return:
        """
        module = pymem.process.module_from_name(pm.process_handle, process_name)
        base_address = module.lpBaseOfDll
        addr = base_address + self.base
        for offset in self.offsets:
            try:
                addr = pm.read_longlong(addr) + offset
            except pymem.exception.MemoryReadError:
                pass
        return addr


class GUI:
    """
    GUI class for the bot.
    Description:
        - The GUI class is used to create the main window for the bot.
        - The window contains radio buttons to select the resource to monitor (HP, Mana, or Shield).
        - The window displays the current value of the selected resource.
        - The window allows the user to set a threshold value for the selected resource.
        - The window displays an "Escaped?" label to indicate if the bot has sent an escape key press to the game
          window.
        - The window contains a "Start" button to start monitoring the selected resource.
        - The window contains an "Exit" button to close the bot.
        - The window contains an info label to display messages to the user
    """
    def __init__(self, start_monitor: callable, stop_monitor: callable):
        """
        Initialize the GUI window.
        :param start_monitor: callable function to start the resource monitor
        :param stop_monitor: callable function to stop the resource monitor
        """
        self.root = tk.Tk()
        self.root.title("PoE2 Chicken Bot")
        self.root.geometry("275x180")
        self.root.grid_columnconfigure(4, weight=1)
        self.root.grid_rowconfigure(3, weight=1)

        self.create_menubar()

        self.selected_resource = tk.StringVar(value="hp")
        self.escape_status_label = None
        self.setting_file = "poe2-chicken-bot.config"
        self.start_monitor = start_monitor
        self.stop_monitor = stop_monitor

        self.current_value_labels = {}
        self.threshold_entries = {}

        self.resource_config = {
            key: Resource(key, cfg["base"], cfg["offsets"], cfg["default_threshold"])
            for key, cfg in RESOURCE_CONFIG.items()
        }

        self.monitor_button = None
        self.exit_button = None
        self.info_label = None

        self.create_widgets()
        self.load_settings()

    def create_menubar(self):
        menubar = tk.Menu(self.root, tearoff=0)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label='Save defaults', command=self.save_settings)
        menubar.add_cascade(label='File', menu=filemenu, underline=1)
        self.root.config(menu=menubar)

    def create_widgets(self):
        """
        Create the widgets for the GUI. This includes radio buttons, labels, entries, buttons, and info labels.
        :return:
        """
        options = [("HP", "hp"), ("Mana", "mp"), ("Shield", "ms")]
        for idx, (text, resource_key) in enumerate(options):
            self.create_radiobutton(idx, text, resource_key)

        tk.Label(self.root, text="Current:").grid(row=1, column=0, sticky='nw', padx=10, pady=5)
        for idx, (text, resource_key) in enumerate(options):
            self.create_label_and_entry(idx, resource_key)

        tk.Label(self.root, text="Threshold:").grid(row=2, column=0, sticky='nw', padx=10, pady=5)
        self.create_escape_status_label()

        self.exit_button = tk.Button(self.root, text="Exit", command=self.exit_app)
        self.exit_button.grid(row=4, column=0, sticky='we', padx=10, columnspan=1)

        self.info_label = tk.Label(self.root, text="")
        self.info_label.grid(row=5, column=0, sticky='we', padx=5, columnspan=5)

        self.update_monitor_button(is_monitoring=False)

    def create_radiobutton(self, idx: int, text: str, resource_key: str):
        """
        Create a radio button for the resource selection.
        :param idx:
        :param text:
        :param resource_key:
        :return:
        """
        rb = tk.Radiobutton(self.root, text=text, value=resource_key, variable=self.selected_resource)
        rb.grid(row=0, column=idx+1, sticky='nw', padx=5)

    def create_label_and_entry(self, idx: int, resource_key: str):
        """
        Create a label and entry for the current value and threshold of the selected resource.
        :param idx:
        :param resource_key:
        :return:
        """
        label = tk.Label(self.root, text="0")
        label.grid(row=1, column=idx+1, sticky='nw', padx=5, pady=5)
        self.current_value_labels[resource_key] = label

        entry = tk.Entry(self.root, width=5)
        entry.grid(row=2, column=idx+1, sticky='nw', padx=5, pady=5)
        self.threshold_entries[resource_key] = entry

    def create_escape_status_label(self):
        """
        Create a label to display the escape status.
        :return:
        """
        tk.Label(self.root, text="Escaped?: ").grid(row=3, column=0, sticky='nw', padx=10, pady=5, columnspan=2)
        self.escape_status_label = tk.Label(self.root, text="No")
        self.escape_status_label.grid(row=3, column=1, sticky='nw', padx=5, pady=5)

    def load_settings(self):
        """
        Load the settings from the config file. If the file does not exist, use the default values.
        :return:
        """
        if os.path.isfile(self.setting_file):
            with open(self.setting_file, 'r') as f:
                settings = f.read().split(',')
            for resource_key, setting in zip(self.resource_config.keys(), settings):
                try:
                    self.resource_config[resource_key].threshold = int(setting)
                except ValueError:
                    pass
                self.threshold_entries[resource_key].delete(0, tk.END)
                self.threshold_entries[resource_key].insert(0, setting)
        else:
            for resource_key, resource_obj in self.resource_config.items():
                self.threshold_entries[resource_key].delete(0, tk.END)
                self.threshold_entries[resource_key].insert(0, str(resource_obj.threshold))
            self.save_settings()

    def save_settings(self):
        """
        Save the current settings to the config file. The settings are the threshold values for each resource.
        :return:
        """
        with open(self.setting_file, "w") as f:
            line = ",".join(
                [self.threshold_entries[key].get() if self.threshold_entries[key].get() else "0"
                 for key in self.threshold_entries]
            )
            f.write(line)

    def exit_app(self):
        self.root.quit()

    def update_monitor_button(self, is_monitoring: bool):
        """
        Update the monitor button text and command based on the monitoring status.
        :param is_monitoring:
        :return:
        """
        if self.monitor_button:
            self.monitor_button.destroy()
        if is_monitoring:
            self.monitor_button = tk.Button(self.root, text="Stop", command=self.stop_monitor)
            self.send_info("Running...")
        else:
            self.monitor_button = tk.Button(self.root, text="Start", command=self.start_monitor)
            self.send_info("")
        self.monitor_button.grid(row=4, column=1, sticky='we', padx=5, columnspan=2, pady=5)

    def send_info(self, msg, msg_type='info'):
        """
        Send a message to the info label. The message type determines the color of the text.
        :param msg:
        :param msg_type:
        :return:
        """
        color_map = {
            'warn': 'orange',
            'err': 'red',
            'info': 'black'
        }
        self.info_label.config(text=msg, fg=color_map.get(msg_type, 'black'))

    def get_selected_resource(self):
        """
        Get the selected resource value.
        :return:
        """
        return self.selected_resource.get()

    def get_threshold_entry_value(self):
        """
        Get the threshold entry value for the selected resource.
        :return:
        """
        res = self.get_selected_resource()
        return self.threshold_entries[res].get()

    def set_current_value(self, value: int):
        """
        Set the current value label for the selected resource.
        :param value:
        :return:
        """
        self.current_value_labels[self.get_selected_resource()].config(text=str(value))

    def set_escape_status(self, status: str):
        """
        Set the escape status label. The status is either "Yes" or "No".
        :param status:
        :return:
        """
        self.escape_status_label.config(text=status)

    def get_resource_threshold(self, resource_key: str):
        """
        Get the threshold value for the selected resource.
        :param resource_key:
        :return:
        """
        return self.resource_config[resource_key].threshold

    def get_resource_base(self, resource_key: str):
        """
        Get the base address for the selected resource.
        :param resource_key:
        :return:
        """
        return self.resource_config[resource_key].base

    def get_resource_offsets(self, resource_key: str):
        """
        Get the offsets for the selected resource.
        :param resource_key:
        :return:
        """
        return self.resource_config[resource_key].offsets

    def draw(self):
        """
        Draw the GUI window.
        :return:
        """
        self.root.mainloop()


class ChickenBot:
    """
    ChickenBot class for the PoE2 Chicken Bot. This class is the main class for the bot and contains the main logic
    for monitoring the selected resource and sending an escape key press to the game window if the resource falls below
    a certain threshold.

    Description:
        - The ChickenBot class initializes
        - The ChickenBot class sets up the backend (pymem) to read the resource value from the game's memory.
        - The ChickenBot class starts the resource monitor loop.
        - The ChickenBot class updates the current resource display and escape status.
        - The ChickenBot class gets the threshold value from the GUI.
        - The ChickenBot class sets up the pointer to the resource value in the game's memory.
    """

    def __init__(self):
        self.PROCESS_NAME = "PathOfExileSteam.exe"
        self.ESCAPED = False
        self.is_monitoring = False
        self.gui = GUI(self.run_monitor, self.stop_monitor)
        self.pointer = None
        self.pm = None
        self.hwnd = None

    def _setup_backend(self):
        """
        Setup the backend (pymem) to read the resource value from the game's memory.
        Description:
            - Try to connect to the PoE2 process.
            - Get the game window handle.
            - Setup the pointer to the resource value in the game's memory.
        :return:
        """
        try:
            self.pm = pymem.Pymem(self.PROCESS_NAME)
        except Exception as e:
            self.gui.send_info("PoE2 process is not running", "err")
            raise Exception("PoE2 process is not running") from e
        hwnd = win32gui.FindWindow(None, "Path of Exile 2")
        if not hwnd:
            self.gui.send_info("Cannot find game window!", "err")
            raise Exception("Cannot find game window!")
        self.hwnd = hwnd
        self.setup_pointer()
        return True

    def stop_monitor(self):
        """
        Stop the resource monitor loop.
        Description:
            - Set the monitoring status to False.
            - Send an empty message to the info label.
            - Update the monitor button.
        :return:
        """
        self.is_monitoring = False
        self.gui.send_info("")
        self.gui.update_monitor_button(is_monitoring=False)

    def update_current_resource_display(self, value: int):
        """
        Update the current resource display in the GUI.
        :param value:
        :return:
        """
        self.gui.set_current_value(value)

    def update_escape_status(self):
        """
        Update the escape status in the GUI. The status is either "Yes" or "No".
        :return:
        """
        status = "Yes" if self.ESCAPED else "No"
        self.gui.set_escape_status(status)

    def get_threshold(self):
        """
        Get the threshold value from the GUI. If the threshold entry is empty, use the default threshold value.
        Description:
            - Try to get the threshold value from the GUI.
            - If the threshold value is not an integer, get the default threshold value for the selected resource.
        :return:
        """
        try:
            threshold = int(self.gui.get_threshold_entry_value())
        except ValueError:
            res = self.gui.get_selected_resource()
            threshold = int(self.gui.get_resource_threshold(res))
        return threshold

    def resource_monitor_loop(self):
        """
        Resource monitor loop to monitor the selected resource value. The loop will check the resource value against the
        threshold and send an escape key press to the game window if the resource falls below the threshold.
        Description:
            - Get the threshold value.
            - Get the current resource value.
            - Update the current resource display.
            - Update the escape status.
            - Check if the resource value is below the threshold and run panic if necessary.
            - Check if the resource value is above the threshold and reset the escape status.
            - Check if the resource value is 0, above 20000, or escaped.
            - Setup the backend every 2 seconds if the resource value is 0, above 20000, or escaped to prevent excessive
                memory reads.
            - Sleep for 0.05 seconds.
        :return:
        """
        self.is_monitoring = True
        threshold = self.get_threshold()
        last_backend_setup = time.time()
        backend_interval = 2.0

        while self.is_monitoring:
            resource_value = self.read_resource_value(self.pointer)
            try:
                resource_int = int(resource_value)
            except (ValueError, TypeError):
                resource_int = 0

            self.update_current_resource_display(resource_int)
            self.update_escape_status()

            if resource_int <= threshold and not self.ESCAPED:
                print(f"HP: {resource_int} below threshold ({threshold}). Panic mode!")
                self.panic()
            elif resource_int > threshold and self.ESCAPED:
                print("HP above threshold, reset escape status")
                self.ESCAPED = False

            current_time = time.time()
            if ((resource_int == 0 or resource_int >= 20000 or self.ESCAPED)
                    and (current_time - last_backend_setup > backend_interval)):
                print("Waiting for memory data...")
                try:
                    self._setup_backend()
                    last_backend_setup = current_time
                except Exception:
                    pass
            time.sleep(0.05)

    def setup_pointer(self):
        """
        Setup the pointer to the resource value in the game's memory. The pointer is calculated based on the selected
        resource.
        :return:
        """
        res_key = self.gui.get_selected_resource()
        resource_obj = self.gui.resource_config[res_key]
        self.pointer = resource_obj.calculate_address(self.pm, self.PROCESS_NAME)

    def run_monitor(self):
        """
        Run the resource monitor loop.
        Description:
            - Try to setup the backend.
            - If the pointer is found, update the monitor button and start the resource monitor loop.
            - If the pointer is not found, print an error message.
        :return:
        """
        try:
            self._setup_backend()
        except Exception as e:
            print(e)
            return

        if self.pointer:
            self.gui.update_monitor_button(is_monitoring=True)
            monitor_thread = threading.Thread(target=self.resource_monitor_loop, name="Monitor", daemon=True)
            monitor_thread.start()
        else:
            msg = f"Process {self.PROCESS_NAME} not found."
            self.gui.send_info(msg, "err")
            print(msg)

    def panic(self):
        """
        Send an escape key press to the game window. The panic function will send an escape key press to the game window
        and set the ESCAPED flag to True.
        :return:
        """
        try:
            win32api.PostMessage(self.hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
            self._kb_panic()
            self.ESCAPED = True
        except Exception:
            self.gui.send_info("Game window not found!", "err")
            exit(1)

    @staticmethod
    def _kb_panic():
        """
        Block the escape and space keys for 2 seconds to prevent accidental game resuming (and probably death ^^).
        :return:
        """
        keyboard.block_key('esc')
        keyboard.block_key('space')
        timer = threading.Timer(2.0, lambda: (keyboard.unblock_key('esc'), keyboard.unblock_key('space')))
        timer.start()

    def read_resource_value(self, addr: int):
        """
        Read the resource value from the game's memory.
        :param addr:
        :return:
        """
        try:
            return self.pm.read_int(addr)
        except Exception:
            return 0


if __name__ == '__main__':
    chicken_bot = ChickenBot()
    chicken_bot.gui.draw()
