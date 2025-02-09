import os
import time
import threading

import pymem
import win32api
import win32con
import win32gui

import tkinter as tk
import keyboard


RESOURCE_CONFIG = {
    "hp": {
         "base": 0x03BA8868,
         "offsets": [0x98, 0x68, 0x474],
         "default_threshold": 400
    },
    "mp": {
         "base": 0x03CCF4F8,
         "offsets": [0x58, 0x0, 0x110, 0xF8, 0x1A0, 0x19C],
         "default_threshold": 1000
    },
    "ms": {
         "base": 0x038AD5B8,
         "offsets": [0xC8, 0x18, 0x110, 0xF8, 0x1A0, 0x1A0],
         "default_threshold": 10
    }
}


class Resource:
    def __init__(self, name, base, offsets, default_threshold):
        self.name = name
        self.base = base
        self.offsets = offsets
        self.threshold = default_threshold

    def calculate_address(self, pm, process_name):
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
    def __init__(self, start_monitor, stop_monitor):
        self.root = tk.Tk()
        self.root.title("PoE2 Chicken Bot")
        self.root.geometry("275x180")
        self.root.grid_columnconfigure(4, weight=1)
        self.root.grid_rowconfigure(3, weight=1)

        self.create_menubar()

        self.selected_resource = tk.StringVar(value="hp")
        self.escape_status_label = None
        self.setting_file = "poe2_chicken_bot.config"
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

    def create_radiobutton(self, idx, text, resource_key):
        rb = tk.Radiobutton(self.root, text=text, value=resource_key, variable=self.selected_resource)
        rb.grid(row=0, column=idx+1, sticky='nw', padx=5)

    def create_label_and_entry(self, idx, resource_key):
        label = tk.Label(self.root, text="0")
        label.grid(row=1, column=idx+1, sticky='nw', padx=5, pady=5)
        self.current_value_labels[resource_key] = label

        entry = tk.Entry(self.root, width=5)
        entry.grid(row=2, column=idx+1, sticky='nw', padx=5, pady=5)
        self.threshold_entries[resource_key] = entry

    def create_escape_status_label(self):
        tk.Label(self.root, text="Escaped?: ").grid(row=3, column=0, sticky='nw', padx=10, pady=5, columnspan=2)
        self.escape_status_label = tk.Label(self.root, text="No")
        self.escape_status_label.grid(row=3, column=1, sticky='nw', padx=5, pady=5)

    def load_settings(self):
        if os.path.isfile(self.setting_file):
            with open(self.setting_file, 'r') as f:
                settings = f.read().split(',')
            for resource_key, setting in zip(self.resource_config.keys(), settings):
                try:
                    self.resource_config[resource_key].threshold = int(setting)
                except ValueError:
                    self.resource_config[resource_key].threshold = 0
                self.threshold_entries[resource_key].delete(0, tk.END)
                self.threshold_entries[resource_key].insert(0, setting)

    def save_settings(self):
        with open(self.setting_file, "w") as f:
            line = ",".join([self.threshold_entries[key].get() if self.threshold_entries[key].get() else "0"
                             for key in self.threshold_entries])
            f.write(line)

    def exit_app(self):
        self.root.quit()

    def update_monitor_button(self, is_monitoring):
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
        color_map = {
            'warn': 'orange',
            'err': 'red',
            'info': 'black'
        }
        self.info_label.config(text=msg, fg=color_map.get(msg_type, 'black'))

    def get_selected_resource(self):
        return self.selected_resource.get()

    def get_threshold_entry_value(self):
        res = self.get_selected_resource()
        return self.threshold_entries[res].get()

    def set_current_value(self, value):
        self.current_value_labels[self.get_selected_resource()].config(text=str(value))

    def set_escape_status(self, status):
        self.escape_status_label.config(text=status)

    def get_resource_threshold(self, resource_key):
        return self.resource_config[resource_key].threshold

    def get_resource_base(self, resource_key):
        return self.resource_config[resource_key].base

    def get_resource_offsets(self, resource_key):
        return self.resource_config[resource_key].offsets

    def draw(self):
        self.root.mainloop()


class ChickenBot:
    def __init__(self):
        self.PROCESS_NAME = "PathOfExileSteam.exe"
        self.ESCAPED = False
        self.is_monitoring = False

        self.gui = GUI(self.run_monitor, self.stop_monitor)

        self.pointer = None
        self.pm = None
        self.hwnd = None

    def _setup_backend(self):
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
        self.is_monitoring = False
        self.gui.send_info("")
        self.gui.update_monitor_button(is_monitoring=False)

    def update_current_resource_display(self, value):
        self.gui.set_current_value(value)

    def update_escape_status(self):
        status = "Yes" if self.ESCAPED else "No"
        self.gui.set_escape_status(status)

    def get_threshold(self):
        try:
            threshold = int(self.gui.get_threshold_entry_value())
        except ValueError:
            res = self.gui.get_selected_resource()
            threshold = int(self.gui.get_resource_threshold(res))
        return threshold

    def resource_monitor_loop(self):
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
            if (resource_int == 0 or resource_int >= 20000 or self.ESCAPED) and (current_time - last_backend_setup > backend_interval):
                print("Waiting for memory data...")
                try:
                    self._setup_backend()
                    last_backend_setup = current_time
                except Exception:
                    pass

            time.sleep(0.05)

    def setup_pointer(self):
        res_key = self.gui.get_selected_resource()
        resource_obj = self.gui.resource_config[res_key]
        self.pointer = resource_obj.calculate_address(self.pm, self.PROCESS_NAME)

    def run_monitor(self):
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
        try:
            win32api.PostMessage(self.hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
            self._kb_panic()
            self.ESCAPED = True
        except Exception:
            self.gui.send_info("Game window not found!", "err")
            exit(1)

    @staticmethod
    def _kb_panic():
        keyboard.block_key('esc')
        keyboard.block_key('space')
        timer = threading.Timer(2.0, lambda: (keyboard.unblock_key('esc'), keyboard.unblock_key('space')))
        timer.start()

    def read_resource_value(self, addr):
        try:
            return self.pm.read_int(addr)
        except Exception:
            return 0


if __name__ == '__main__':
    chicken_bot = ChickenBot()
    chicken_bot.gui.draw()
