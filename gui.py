import tkinter as tk
from tkinter import ttk
from tkinter.colorchooser import askcolor
from threading import Thread
import requests
import time
import socket


class SongAnalysisGUI:
    def __init__(self, root, start_server_func, detect_device_func):
        self.root = root
        self.root.title("Real-time Song Analysis")

        # IP and Port Setting
        self.ip_label = tk.Label(root, text="Server IP Address:")
        self.ip_label.grid(row=0, column=0, sticky='e')
        self.ip_entry = tk.Entry(root)
        self.ip_entry.grid(row=0, column=1)

        self.port_label = tk.Label(root, text="Server Port:")
        self.port_label.grid(row=1, column=0, sticky='e')
        self.port_entry = tk.Entry(root)
        self.port_entry.insert(0, "8080")
        self.port_entry.grid(row=1, column=1)

        self.start_server_button = tk.Button(root, text="Start Server", command=self.start_server)
        self.start_server_button.grid(row=2, columnspan=2)

        # Labels for real-time status
        self.song_status_label = tk.Label(root, text="Song Status: Loading...", font=('Arial', 12))
        self.song_status_label.grid(row=3, columnspan=2)

        self.current_mode_label = tk.Label(root, text="Current Mode: 0", font=('Arial', 12))
        self.current_mode_label.grid(row=4, columnspan=2)

        self.volume_chart_label = tk.Label(root, text="Real-time Volume Level", font=('Arial', 12))
        self.volume_chart_label.grid(row=5, columnspan=2)

        # Color Control
        self.color_label = tk.Label(root, text="Color Control", font=('Arial', 14, 'bold'))
        self.color_label.grid(row=6, columnspan=2)

        self.color_buttons = []
        for i in range(4):
            button = tk.Button(root, text=f"Strip {i + 1} Color", command=lambda i=i: self.select_color(i))
            button.grid(row=7, column=i)

        # Color Mode Buttons
        self.set_color_button = tk.Button(root, text="Set Colors", command=self.set_color)
        self.set_color_button.grid(row=8, column=0, padx=5)

        self.full_spectrum_button = tk.Button(root, text="Full Spectrum Mode",
                                              command=lambda: self.set_color_mode('full_spectrum'))
        self.full_spectrum_button.grid(row=8, column=1, padx=5)

        self.rave_mode_button = tk.Button(root, text="Rave Mode", command=lambda: self.set_color_mode('rave'))
        self.rave_mode_button.grid(row=8, column=2, padx=5)

        self.halloween_mode_button = tk.Button(root, text="Halloween Mode",
                                               command=lambda: self.set_color_mode('halloween'))
        self.halloween_mode_button.grid(row=8, column=3, padx=5)

        self.boiler_room_button = tk.Button(root, text="Boiler Room Mode",
                                            command=lambda: self.set_color_mode('boiler_room'))
        self.boiler_room_button.grid(row=8, column=4, padx=5)

        # Scene Mode Buttons
        self.scene_label = tk.Label(root, text="Scene Modes", font=('Arial', 14, 'bold'))
        self.scene_label.grid(row=9, columnspan=4)

        self.scene_buttons = []
        for i in range(1, 14):
            button = tk.Button(root, text=f"Effect {i}", command=lambda i=i: self.set_scene_mode(i))
            button.grid(row=10 + i // 4, column=i % 4)
            self.scene_buttons.append(button)

        # Start the device detection
        self.detect_device_func = detect_device_func
        Thread(target=self.detect_device_func).start()

        # Start the periodic update for the GUI
        self.update_gui()

    def start_server(self):
        ip_address = self.ip_entry.get()
        port = self.port_entry.get()
        Thread(target=self.start_server_func, args=(ip_address, port)).start()

    def select_color(self, index):
        color = askcolor()[1]
        self.color_buttons[index].configure(bg=color)

    def set_color(self):
        colors = [self.color_buttons[i].cget('bg') for i in range(4)]
        requests.post('http://localhost:8080/set-color', json={'mode': 'static', 'colors': colors})

    def set_color_mode(self, mode):
        requests.post('http://localhost:8080/set-color', json={'mode': mode})

    def set_scene_mode(self, mode):
        requests.post('http://localhost:8080/set-scene', json={'scene_mode': mode})

    def update_gui(self):
        try:
            response = requests.get('http://localhost:8080/status')
            data = response.json()
            self.song_status_label.config(
                text=f"Spotify BPM: {data['spotify_bpm']:.2f}, Energy Level: {data['energy_level']}, Beat Drop: {'Yes' if data['is_beat_drop'] else 'No'}")
            self.current_mode_label.config(text=f"Current Mode: {data['scene_mode']}")
        except requests.exceptions.RequestException:
            pass
        self.root.after(1000, self.update_gui)


def auto_detect_device():
    devices = sd.query_devices()
    for idx, device in enumerate(devices):
        if 'BlackHole 2ch' in device['name']:
            print(f"BlackHole 2ch detected and set as input device (ID: {idx})")
            return idx
    return None


if __name__ == '__main__':
    root = tk.Tk()
    gui = SongAnalysisGUI(root, start_web_server, auto_detect_device)
    root.mainloop()
