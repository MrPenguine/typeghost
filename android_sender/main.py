import socket
import json
import threading
import time
import platform
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle, Line

# Set phone-friendly preview window size for desktop testing
Window.size = (380, 680)
Window.clearcolor = (0.13, 0.145, 0.165, 1)  # #22252A Slate Dark

DISCOVERY_PORT = 45454
TCP_COMM_PORT = 45455
MAGIC_HEADER = "TYPEGHOST_BEACON"

class AndroidSenderNetwork:
    def __init__(self, message_callback, status_callback):
        self.message_callback = message_callback
        self.status_callback = status_callback
        self.device_name = "Android Phone"
        self.running = True
        self.client_socket = None
        self.client_thread = None
        self.discovery_thread = None
        self.connected_pc_name = None
        self.connected_pc_ip = None

    def start(self):
        self.status_callback("Searching for PC on Wi-Fi...", "warning")
        self.discovery_thread = threading.Thread(target=self._run_discovery, daemon=True)
        self.discovery_thread.start()

    def _run_discovery(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", DISCOVERY_PORT))
        except Exception as e:
            self.status_callback(f"Bind error: {e}", "danger")
            return

        sock.settimeout(2.0)
        while self.running and not self.client_socket:
            try:
                data, addr = sock.recvfrom(2048)
                msg = json.loads(data.decode("utf-8"))
                if msg.get("magic") == MAGIC_HEADER and msg.get("role") == "Receiver":
                    target_ip = addr[0]
                    target_name = msg.get("name", "PC Receiver")
                    target_port = msg.get("port", TCP_COMM_PORT)
                    self.status_callback(f"Found [{target_name}]. Connecting...", "info")
                    self._connect_to_pc(target_ip, target_port, target_name)
                    break
            except socket.timeout:
                continue
            except Exception:
                continue
        try:
            sock.close()
        except Exception:
            pass

    def _connect_to_pc(self, ip, port, pc_name):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(4.0)
            sock.connect((ip, port))
            sock.settimeout(None)
            
            # Send initial Handshake
            handshake = json.dumps({"type": "HANDSHAKE", "name": self.device_name}) + "\n"
            sock.sendall(handshake.encode("utf-8"))
            
            self.client_socket = sock
            self.connected_pc_name = pc_name
            self.connected_pc_ip = ip
            self.status_callback(f"Connected to [{pc_name}]", "success")
            
            self.client_thread = threading.Thread(target=self._listen_to_pc, daemon=True)
            self.client_thread.start()
        except Exception:
            self.client_socket = None
            self.status_callback("Retrying Wi-Fi discovery...", "warning")
            if self.running:
                self.discovery_thread = threading.Thread(target=self._run_discovery, daemon=True)
                self.discovery_thread.start()

    def _listen_to_pc(self):
        buffer = ""
        sock = self.client_socket
        while self.running and sock and self.client_socket == sock:
            try:
                data = sock.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        try:
                            msg = json.loads(line)
                            self.message_callback(msg)
                        except Exception:
                            pass
            except Exception:
                break

        if self.client_socket == sock:
            self.client_socket = None
            self.connected_pc_name = None
            self.connected_pc_ip = None
            if self.running:
                self.status_callback("Disconnected. Re-discovering PC...", "warning")
                self.discovery_thread = threading.Thread(target=self._run_discovery, daemon=True)
                self.discovery_thread.start()

    def send_packet(self, data_dict):
        if self.client_socket:
            try:
                payload = (json.dumps(data_dict) + "\n").encode("utf-8")
                self.client_socket.sendall(payload)
            except Exception:
                pass

    def stop(self):
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()
            except Exception:
                pass
            self.client_socket = None


class TypeGhostMobileApp(App):
    def build(self):
        self.title = "TypeGhost Remote"
        self.current_pct = 0

        # Network Manager
        self.network = AndroidSenderNetwork(
            message_callback=self.on_network_message,
            status_callback=self.update_status
        )

        # Root Layout
        root = BoxLayout(orientation='vertical', padding=14, spacing=10)
        with root.canvas.before:
            Color(0.13, 0.145, 0.165, 1) # #22252A
            self.bg_rect = RoundedRectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda obj, val: setattr(self.bg_rect, 'pos', val),
                  size=lambda obj, val: setattr(self.bg_rect, 'size', val))

        # --- 1. Header (Brand & Status) ---
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=45)
        title_label = Label(
            text="⚡ TYPEGHOST",
            font_size='18sp',
            bold=True,
            color=(0, 0.74, 0.55, 1), # #00BC8C Emerald
            size_hint_x=0.5,
            halign='left',
            valign='middle'
        )
        title_label.bind(size=title_label.setter('text_size'))
        header.add_widget(title_label)

        self.status_label = Label(
            text="● Searching...",
            font_size='11sp',
            bold=True,
            color=(0.95, 0.61, 0.07, 1), # Amber
            size_hint_x=0.5,
            halign='right',
            valign='middle'
        )
        self.status_label.bind(size=self.status_label.setter('text_size'))
        header.add_widget(self.status_label)
        root.add_widget(header)

        # --- 2. Parameters Card (WPM & Accuracy) ---
        params_card = GridLayout(cols=2, spacing=10, size_hint_y=None, height=75)

        # WPM
        wpm_box = BoxLayout(orientation='vertical', spacing=2)
        wpm_box.add_widget(Label(text="SPEED (WPM)", font_size='10sp', color=(0.6, 0.63, 0.67, 1), size_hint_y=None, height=18))
        self.wpm_input = TextInput(
            text="100",
            multiline=False,
            font_size='16sp',
            halign='center',
            background_color=(0.12, 0.13, 0.15, 1),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(0, 0.74, 0.55, 1)
        )
        self.wpm_input.bind(text=self.on_text_or_params_changed)
        wpm_box.add_widget(self.wpm_input)
        params_card.add_widget(wpm_box)

        # Accuracy
        acc_box = BoxLayout(orientation='vertical', spacing=2)
        acc_box.add_widget(Label(text="ACCURACY (0.0-1.0)", font_size='10sp', color=(0.6, 0.63, 0.67, 1), size_hint_y=None, height=18))
        self.acc_input = TextInput(
            text="0.98",
            multiline=False,
            font_size='16sp',
            halign='center',
            background_color=(0.12, 0.13, 0.15, 1),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(0, 0.74, 0.55, 1)
        )
        self.acc_input.bind(text=self.on_text_or_params_changed)
        acc_box.add_widget(self.acc_input)
        params_card.add_widget(acc_box)

        root.add_widget(params_card)

        # --- 3. Live Text Buffer Card ---
        buffer_label = Label(
            text="TEXT TO PUSH TO PC (IN-MEMORY STREAM)",
            font_size='10sp',
            color=(0.6, 0.63, 0.67, 1),
            size_hint_y=None,
            height=20,
            halign='left'
        )
        buffer_label.bind(size=buffer_label.setter('text_size'))
        root.add_widget(buffer_label)

        self.text_editor = TextInput(
            hint_text="Paste or type text here...\nIt syncs live to the PC in memory without touching clipboard.",
            multiline=True,
            font_size='13sp',
            background_color=(0.1, 0.1, 0.12, 1),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(0, 0.74, 0.55, 1)
        )
        self.text_editor.bind(text=self.on_text_or_params_changed)
        root.add_widget(self.text_editor)

        # --- 4. Remote Action Control Buttons ---
        btn_grid = GridLayout(cols=2, spacing=10, size_hint_y=None, height=55)

        self.start_btn = Button(
            text="▶ START",
            font_size='14sp',
            bold=True,
            background_normal='',
            background_color=(0, 0.74, 0.55, 1), # Emerald
            color=(1, 1, 1, 1)
        )
        self.start_btn.bind(on_release=self.on_start_pressed)
        btn_grid.add_widget(self.start_btn)

        self.pause_btn = Button(
            text="⏸ PAUSE",
            font_size='14sp',
            bold=True,
            background_normal='',
            background_color=(0.95, 0.61, 0.07, 1), # Amber
            color=(1, 1, 1, 1)
        )
        self.pause_btn.bind(on_release=self.on_pause_pressed)
        btn_grid.add_widget(self.pause_btn)
        root.add_widget(btn_grid)

        self.clear_btn = Button(
            text="⏹ STOP & CLEAR PC (ESC)",
            font_size='13sp',
            bold=True,
            size_hint_y=None,
            height=45,
            background_normal='',
            background_color=(0.91, 0.3, 0.24, 1), # Crimson Red
            color=(1, 1, 1, 1)
        )
        self.clear_btn.bind(on_release=self.on_clear_pressed)
        root.add_widget(self.clear_btn)

        # Start network thread
        self.network.start()

        return root

    def on_text_or_params_changed(self, instance, value):
        text = self.text_editor.text.strip()
        wpm = self.wpm_input.text.strip() or "100"
        accuracy = self.acc_input.text.strip() or "0.98"
        self.network.send_packet({
            "type": "SYNC_DATA",
            "text": text,
            "wpm": wpm,
            "accuracy": accuracy
        })

    def on_start_pressed(self, instance):
        self.on_text_or_params_changed(None, None)
        self.network.send_packet({"type": "CMD_START"})

    def on_pause_pressed(self, instance):
        self.network.send_packet({"type": "CMD_PAUSE"})

    def on_clear_pressed(self, instance):
        self.network.send_packet({"type": "CMD_CLEAR"})
        self.text_editor.text = ""
        self.update_progress(0)

    def on_network_message(self, msg):
        msg_type = msg.get("type")
        if msg_type == "PROGRESS_UPDATE":
            pct = msg.get("percentage", 0)
            Clock.schedule_once(lambda dt: self.update_progress(pct))

    def update_progress(self, pct):
        self.current_pct = pct
        if pct > 0:
            self.start_btn.text = f"▶ TYPING [{pct}%]"
        else:
            self.start_btn.text = "▶ START"

    def update_status(self, text, kind="info"):
        color_map = {
            "success": (0, 0.74, 0.55, 1),
            "warning": (0.95, 0.61, 0.07, 1),
            "danger": (0.91, 0.3, 0.24, 1),
            "info": (0.2, 0.6, 1, 1)
        }
        col = color_map.get(kind, (1, 1, 1, 1))
        Clock.schedule_once(lambda dt: self._apply_status(text, col))

    def _apply_status(self, text, col):
        self.status_label.text = f"● {text}"
        self.status_label.color = col

    def on_stop(self):
        if self.network:
            self.network.stop()


if __name__ == '__main__':
    TypeGhostMobileApp().run()
