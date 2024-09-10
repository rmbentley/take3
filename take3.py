import numpy as np
import sounddevice as sd
import requests
from scipy.signal import butter, lfilter
from threading import Thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time
from collections import deque
from multiprocessing import Value

# Audio stream configuration
CHUNK = 1024
RATE = 44100
DEVICE_INDEX = 0
CHANNELS = 2

# Shared variables
spotify_bpm = Value('f', 120.0)
current_volume_level = Value('f', 0.0)
current_is_beat_drop = Value('i', 0)
current_energy_level = Value('i', -1)
beat_drop_timestamp = Value('d', 0.0)
strip_colors = [Value('i', 0xFFFFFF) for _ in range(4)]
color_mode = Value('i', 0)

# Spotify API credentials
SPOTIFY_ACCESS_TOKEN = 'your_spotify_access_token'
SPOTIFY_API_URL = 'https://api.spotify.com/v1/me/player/currently-playing'


# Bandpass filter function remains the same as before...
def butter_bandpass(lowcut, highcut, fs, order=5):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return b, a


def bandpass_filter(data, lowcut, highcut, fs, order=5):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = lfilter(b, a, data)
    return y


# Real-time audio analysis remains unchanged
def analyze_audio():
    last_volume_levels = deque(maxlen=int(RATE / CHUNK))

    def audio_callback(indata, frames, time_info, status):
        if status:
            print(status)
        audio_data = np.mean(indata, axis=1)
        volume = np.mean(np.abs(audio_data)) * 2
        last_volume_levels.append(volume)
        avg_last_volume = np.mean(last_volume_levels)

        current_time = time.time()
        time_since_last_beat_drop = current_time - beat_drop_timestamp.value

        with current_is_beat_drop.get_lock():
            if (volume - avg_last_volume > 0.3) and volume > 0.35 and time_since_last_beat_drop >= 10:
                current_is_beat_drop.value = 1
                with beat_drop_timestamp.get_lock():
                    beat_drop_timestamp.value = current_time
            elif time_since_last_beat_drop <= 1:
                current_is_beat_drop.value = 1
            else:
                current_is_beat_drop.value = 0

        with current_energy_level.get_lock():
            if volume > 0.30:
                current_energy_level.value = 3
            elif volume > 0.20:
                current_energy_level.value = 2
            elif volume > 0.10:
                current_energy_level.value = 1
            elif volume > 0.01:
                current_energy_level.value = 0
            else:
                current_energy_level.value = -1

        with current_volume_level.get_lock():
            current_volume_level.value = volume

    with sd.InputStream(samplerate=RATE, channels=CHANNELS, device=DEVICE_INDEX, callback=audio_callback):
        while True:
            time.sleep(0.5)


# Function to fetch BPM from Spotify (remains unchanged)
def fetch_spotify_bpm():
    headers = {
        "Authorization": f"Bearer {SPOTIFY_ACCESS_TOKEN}"
    }

    while True:
        try:
            response = requests.get(SPOTIFY_API_URL, headers=headers, timeout=5)
            data = response.json()

            track_id = data['item']['id']
            track_features_url = f"https://api.spotify.com/v1/audio-features/{track_id}"
            response = requests.get(track_features_url, headers=headers, timeout=5)
            track_data = response.json()

            bpm = track_data['tempo']
            with spotify_bpm.get_lock():
                spotify_bpm.value = bpm

            print(f"Fetched BPM from Spotify: {bpm}")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching BPM from Spotify: {e}")
        except Exception as e:
            print(f"General error: {e}")

        time.sleep(20)


# Function to handle HTTP requests (webserver)
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('index.html', 'r') as f:
                self.wfile.write(f.read().encode('utf-8'))

        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            with spotify_bpm.get_lock():
                sp_bpm = spotify_bpm.value
            with current_volume_level.get_lock():
                volume_level = current_volume_level.value
            with current_is_beat_drop.get_lock():
                is_beat_drop = current_is_beat_drop.value
            with current_energy_level.get_lock():
                energy_level = current_energy_level.value

            colors = []
            for i in range(4):
                with strip_colors[i].get_lock():
                    colors.append('#{:06x}'.format(strip_colors[i].value))

            response = json.dumps({
                'spotify_bpm': sp_bpm,
                'volume_level': volume_level,
                'is_beat_drop': is_beat_drop,
                'energy_level': energy_level,
                'current_mode': color_mode.value,
                'colors': colors
            })
            self.wfile.write(response.encode())

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            data = json.loads(post_data)
            if self.path == '/set-mode':
                mode = data['mode']
                with color_mode.get_lock():
                    color_mode.value = mode

            elif self.path == '/set-color':
                mode = data['mode']
                if mode == 'static':
                    colors = data['colors']
                    for i in range(4):
                        r = int(colors[i][1:3], 16)
                        g = int(colors[i][3:5], 16)
                        b = int(colors[i][5:7], 16)
                        with strip_colors[i].get_lock():
                            strip_colors[i].value = (r << 16) | (g << 8) | b

                elif mode in ['full_spectrum', 'rave', 'halloween', 'boiler_room']:
                    with color_mode.get_lock():
                        color_mode.value = {'full_spectrum': 1, 'rave': 2, 'halloween': 3, 'boiler_room': 4}[mode]

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode())

        except Exception as e:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())


# Function to start the HTTP server
def start_server():
    httpd = ThreadingHTTPServer(('0.0.0.0', 8080), SimpleHTTPRequestHandler)
    print("Server started at http://0.0.0.0:8080")
    httpd.serve_forever()


if __name__ == '__main__':
    audio_thread = Thread(target=analyze_audio)
    audio_thread.start()

    spotify_thread = Thread(target=fetch_spotify_bpm)
    spotify_thread.start()

    start_server()
