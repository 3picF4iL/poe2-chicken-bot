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


import tkinter as tk

from os import path
from time import time, sleep, strftime, localtime
from pymem import pymem
from threading import Timer, Thread
from win32api import PostMessage
from win32con import VK_ESCAPE, WM_KEYDOWN
from win32gui import FindWindow  # pylint: disable=no-name-in-module
from keyboard import block_key, unblock_key

# Resource configuration
# Base and offsets are used to calculate the memory address of the resource value. This is specific to the game's
# memory layout and may, unfortunately, change with game updates.
# TODO: Add a way to automatically find the base and offsets.
RESOURCE_CONFIG = {
    "hp": {
         "base": 0x03B9AD28,
         "offsets": [0x98, 0x68, 0x474],
         "default_threshold": 500
    },
    "mp": {
         "base": 0x03B9AD28,
         "offsets": [0x58, 0x60, 0xF80],
         "default_threshold": 500
    },
    "ms": {
         "base": 0x03B9AD28,
         "offsets": [0x58, 0x60, 0x78C],
         "default_threshold": 10
    }
}

DEFAULT_WINDOW_GEOMETRY = "275x180"
ICON_BITMAP = "media/poe2-chicken-bot.ico"
ICON_PATH = path.join(path.dirname(__file__), ICON_BITMAP)


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
        self.root.geometry(DEFAULT_WINDOW_GEOMETRY)
        self.root.iconbitmap(ICON_PATH)
        self.root.grid_columnconfigure(4, weight=1)
        self.root.wm_minsize(*DEFAULT_WINDOW_GEOMETRY.split('x'))
        self.root.wm_maxsize(390, 370)

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
        self.console = None

        self.create_widgets()
        self.load_settings()

    def create_menubar(self):
        menubar = tk.Menu(self.root, tearoff=0)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label='Save defaults', command=self.save_settings)
        filemenu.add_separator()
        filemenu.add_command(label='Console', command=self.console_trigger)
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
        self.create_console()
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

    def create_console(self):
        """
        Create a console widget to display messages.
        :return:
        """
        self.console = tk.Text(self.root, height=10, width=50)
        self.console.grid(row=6, column=0, columnspan=5, padx=5, pady=5, sticky='nw')

        scrollbar = tk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.console.yview)
        scrollbar.grid(row=6, column=5, sticky='wns')
        self.console.config(yscrollcommand=scrollbar.set)
        self.console.insert(tk.END, "==== Console view ====\n")

        # Hide the console with scrollbar
        self.console.grid_remove()

    def console_trigger(self):
        """
        Change the view to the console.
        :return:
        """
        if self.console.winfo_ismapped():
            self.console.grid_remove()
            self.root.geometry(DEFAULT_WINDOW_GEOMETRY)

        else:
            self.console.grid()
            self.resize_window(15, 175)

    def write_to_console(self, msg: str):
        """
        Write a message to the console.
        :param msg:
        :return:
        """
        self.console.insert(tk.END, msg + "\n")
        self.console.see(tk.END)

    def resize_window(self, width: int, height: int):
        """
        Increase or decrease the window size.
        :param width:
        :param height:
        :return:
        """
        # Get the current window size
        _width = self.root.winfo_width()
        _height = self.root.winfo_height()

        self.root.geometry(f"{_width + width}x{_height + height}")

    def load_settings(self):
        if path.isfile(self.setting_file):
            with open(self.setting_file, 'r') as f:
                settings = f.read().split(',')
            for resource_key, setting in zip(self.resource_config.keys(), settings):
                try:
                    self.resource_config[resource_key].threshold = int(setting)
                except ValueError:
                    continue
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
            self.send_info("Running...", label_info=True)
        else:
            self.monitor_button = tk.Button(self.root, text="Start", command=self.start_monitor)
        self.monitor_button.grid(row=4, column=1, sticky='we', padx=5, columnspan=3, pady=5)

    def send_info(self, msg, msg_type='info', label_info=False):
        """
        Send a message to the info label. The message type determines the color of the text.
        Set the label_info param to True to display the message in the info label.
        :param msg:
        :param msg_type:
        :param label_info:
        :return:
        """

        color_map = {
            'warn': 'orange',
            'err': 'red',
            'info': 'black'
        }

        if label_info:
            self.info_label.config(text=msg, fg=color_map.get(msg_type, 'black'))

        if not msg:
            return

        timestamp = strftime("%H:%M:%S", localtime())
        _msg = f"{timestamp} - {msg}"
        self.write_to_console(_msg)

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
            self.gui.send_info("PoE2 process is not running", "err", label_info=True)
            return
        hwnd = FindWindow(None, "Path of Exile 2")
        if not hwnd:
            self.gui.send_info("Cannot find game window!", "err", label_info=True)
            return
        self.hwnd = hwnd
        self.gui.send_info("Connected to PoE2 process")
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
        self.ESCAPED = False
        self.unblock_keys()
        self.gui.send_info("Stopped.", label_info=True)
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
        last_backend_setup = time()
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
                self.gui.send_info(f"HP: {resource_int} below threshold ({threshold}). Panic mode")
                self.panic()
            elif resource_int > threshold and self.ESCAPED:
                self.gui.send_info("HP above threshold, reset escape status")
                self.ESCAPED = False

            current_time = time()
            if ((resource_int == 0 or resource_int >= 20000 or self.ESCAPED)
                    and (current_time - last_backend_setup > backend_interval)):
                self.gui.send_info("Waiting for memory data...")
                try:
                    self._setup_backend()
                    last_backend_setup = current_time
                except Exception:
                    pass
            sleep(0.05)
        self.gui.update_monitor_button(is_monitoring=False)

    def setup_pointer(self):
        """
        Setup the pointer to the resource value in the game's memory. The pointer is calculated based on the selected
        resource.
        :return:
        """
        res_key = self.gui.get_selected_resource()
        resource_obj = self.gui.resource_config[res_key]
        self.pointer = resource_obj.calculate_address(self.pm, self.PROCESS_NAME)
        self.gui.send_info(f"Pointer calculated: {hex(self.pointer)}")

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
            self.gui.send_info(f"Error setting up backend\n{e}", "err")
            return

        if self.pointer:
            self.gui.update_monitor_button(is_monitoring=True)
            monitor_thread = Thread(target=self.resource_monitor_loop, name="Monitor", daemon=True)
            monitor_thread.start()
        else:
            msg = f"Process {self.PROCESS_NAME} not found."
            self.gui.send_info(msg, "err")

    def panic(self):
        """
        Send an escape key press to the game window. The panic function will send an escape key press to the game window
        and set the ESCAPED flag to True.
        :return:
        """
        try:
            PostMessage(self.hwnd, WM_KEYDOWN, VK_ESCAPE, 0)
            self._kb_panic()
            self.ESCAPED = True
        except Exception:
            self.gui.send_info("Game window not found!", "err")
            self.is_monitoring = False

    def _kb_panic(self):
        """
        Block the escape and space keys for 2 seconds to prevent accidental game resuming (and probably death ^^).
        :return:
        """
        block_key('esc')
        block_key('space')
        timer = Timer(2.0, lambda: (self.unblock_keys()))
        timer.start()

    @staticmethod
    def unblock_keys():
        """
        Unblock the escape and space keys.
        Try to unblock the escape and space keys even if they are not blocked.
        This prevents keys from being blocked indefinitely.
        :return:
        """
        try:
            unblock_key('esc')
            unblock_key('space')
        except KeyError:
            pass

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
