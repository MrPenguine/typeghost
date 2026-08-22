import tkinter as tk
from tkinter import scrolledtext
import threading
import socket
import json
import time
import random
import platform
import os
import sys
import ctypes
import pyautogui
from pynput import keyboard

# High DPI awareness for ultra-sharp fonts on Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

DISCOVERY_PORT = 45454
TCP_COMM_PORT = 45455
MAGIC_HEADER = "TYPEGHOST_BEACON"

# Original Sleek Dark Palette
BG_ROOT = "#22252A"         # Sleek dark slate canvas
BG_PANEL = "#2C3038"        # Card / panel background
BG_INPUT = "#1E2227"        # Deep input background
BORDER_COLOR = "#3A3F4B"    # Subtle elegant border outline
TEXT_MAIN = "#FFFFFF"       # Crisp White text
TEXT_MUTED = "#9AA0AC"      # Muted silver-gray subtitle
ACCENT_GREEN = "#00BC8C"    # Success Emerald Green
ACCENT_RED = "#E74C3C"      # Danger Crimson Red
ACCENT_YELLOW = "#F39C12"   # Warning Amber
BORDER_WIDTH = 2

class NetworkManager:
    def __init__(self, role_change_callback, message_callback, status_callback):
        self.role = "Standalone"  # Standalone, Sender, Receiver
        self.role_change_callback = role_change_callback
        self.message_callback = message_callback
        self.status_callback = status_callback
        
        self.device_name = platform.node() or "TypeGhost-Device"
        self.running = True
        
        self.tcp_server = None
        self.server_thread = None
        self.broadcast_thread = None
        self.discovery_thread = None
        
        self.active_receiver_conn = None
        self.client_socket = None
        self.client_thread = None
        self.connected_peer_name = None
        self.connected_peer_ip = None
        self.manual_ip = None

    def get_all_broadcast_ips(self):
        """Retrieve broadcast IPs for all active interfaces on this machine."""
        ips = ["255.255.255.255", "<broadcast>"]
        try:
            host_ips = socket.gethostbyname_ex(socket.gethostname())[2]
            for hip in host_ips:
                if not hip.startswith("127."):
                    parts = hip.split(".")
                    if len(parts) == 4:
                        ips.append(f"{parts[0]}.{parts[1]}.{parts[2]}.255")
        except Exception:
            pass
        return list(set(ips))

































































































        

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "127.0.0.1"

    def set_device_name(self, new_name):
        clean_name = new_name.strip()
        if clean_name:
            self.device_name = clean_name
            if self.role == "Receiver":
                self.status_callback(f"RECEIVER [{self.device_name}] ({self.get_local_ip()})", ACCENT_GREEN)
            elif self.role == "Sender" and not self.client_socket:
                self.status_callback(f"[{self.device_name}] SEARCHING LAN...", ACCENT_YELLOW)

    def set_role(self, new_role):
        if self.role == new_role:
            return
        self.stop_networking()
        self.role = new_role
        
        if self.role == "Receiver":
            self.start_receiver_mode()
        elif self.role == "Sender":
            self.start_sender_mode()
        else:
            self.status_callback("STANDALONE MODE (LOCAL)", ACCENT_GREEN)

    def start_receiver_mode(self):
        self.status_callback(f"RECEIVER [{self.device_name}] ({self.get_local_ip()})", ACCENT_GREEN)
        self.server_thread = threading.Thread(target=self._run_tcp_server, daemon=True)
        self.server_thread.start()

        self.broadcast_thread = threading.Thread(target=self._run_udp_broadcast, daemon=True)
        self.broadcast_thread.start()

    def start_sender_mode(self):
        self.status_callback(f"SEARCHING FOR RECEIVER...", ACCENT_YELLOW)
        self.discovery_thread = threading.Thread(target=self._run_udp_discovery, daemon=True)
        self.discovery_thread.start()

    def connect_manual_ip(self, ip_str):
        clean_ip = ip_str.strip()
        if clean_ip:
            self.manual_ip = clean_ip
            self.status_callback(f"CONNECTING TO {clean_ip}...", ACCENT_YELLOW)
            threading.Thread(target=self._connect_to_receiver, args=(clean_ip, TCP_COMM_PORT, f"PC ({clean_ip})"), daemon=True).start()

    def _run_udp_broadcast(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        sock.settimeout(1.0)
        
        broadcast_targets = self.get_all_broadcast_ips()

        while self.running and self.role == "Receiver":
            try:
                beacon_data = {
                    "magic": MAGIC_HEADER,
                    "name": self.device_name,
                    "ip": self.get_local_ip(),
                    "port": TCP_COMM_PORT,
                    "role": "Receiver"
                }
                payload = json.dumps(beacon_data).encode("utf-8")
                for target in broadcast_targets:
                    try:
                        sock.sendto(payload, (target, DISCOVERY_PORT))
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(1.0)
        try:
            sock.close()
        except Exception:
            pass

    def _run_udp_discovery(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        if hasattr(socket, 'SO_BROADCAST'):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        try:
            # Bind to 0.0.0.0 for cross-platform LAN listening
            sock.bind(("0.0.0.0", DISCOVERY_PORT))
        except Exception as e:
            try:
                sock.bind(("", DISCOVERY_PORT))
            except Exception:
                self.status_callback("DISCOVERY ERROR - USE MANUAL IP", ACCENT_YELLOW)
                return

        sock.settimeout(1.5)
        while self.running and self.role == "Sender" and not self.client_socket:
            try:
                data, addr = sock.recvfrom(2048)
                msg = json.loads(data.decode("utf-8"))
                if msg.get("magic") == MAGIC_HEADER and msg.get("role") == "Receiver":
                    target_ip = msg.get("ip") or addr[0]
                    target_name = msg.get("name", "RECEIVER")
                    target_port = msg.get("port", TCP_COMM_PORT)
                    self.status_callback(f"FOUND [{target_name}]. PAIRING...", ACCENT_YELLOW)
                    self._connect_to_receiver(target_ip, target_port, target_name)
                    break
            except socket.timeout:
                continue
            except Exception:
                continue
        try:
            sock.close()
        except Exception:
            pass

    def _run_tcp_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        try:
            server.bind(("0.0.0.0", TCP_COMM_PORT))
            server.listen(5)
            server.settimeout(1.5)
            self.tcp_server = server
        except Exception as e:
            self.status_callback(f"SERVER ERROR: {e}", ACCENT_RED)
            return

        while self.running and self.role == "Receiver":
            try:
                conn, addr = server.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.connected_peer_ip = addr[0]
                self.active_receiver_conn = conn
                self._handle_receiver_connection(conn)
            except socket.timeout:
                continue
            except Exception:
                break

    def _handle_receiver_connection(self, conn):
        try:
            conn.settimeout(None)
            greeting = json.dumps({"type": "HANDSHAKE", "name": self.device_name}) + "\n"
            conn.sendall(greeting.encode("utf-8"))
            
            buffer = ""
            while self.running and self.role == "Receiver":
                data = conn.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        try:
                            msg = json.loads(line)
                            if msg.get("type") == "HANDSHAKE":
                                self.connected_peer_name = msg.get("name", "Sender")
                                self.status_callback(f"PAIRED: [{self.connected_peer_name}] ({self.connected_peer_ip})", ACCENT_GREEN)
                            else:
                                self.message_callback(msg)
                        except Exception:
                            pass
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
            self.active_receiver_conn = None
            self.connected_peer_name = None
            self.connected_peer_ip = None
            if self.role == "Receiver" and self.running:
                self.status_callback(f"RECEIVER [{self.device_name}] ({self.get_local_ip()})", ACCENT_GREEN)

    def _connect_to_receiver(self, ip, port, peer_name):
        try:
            if self.client_socket:
                try:
                    self.client_socket.close()
                except Exception:
                    pass
                self.client_socket = None

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(4.0)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.connect((ip, port))
            sock.settimeout(None)
            
            handshake = json.dumps({"type": "HANDSHAKE", "name": self.device_name}) + "\n"
            sock.sendall(handshake.encode("utf-8"))
            
            self.client_socket = sock
            self.connected_peer_name = peer_name
            self.connected_peer_ip = ip
            self.status_callback(f"PAIRED: [{peer_name}] ({ip})", ACCENT_GREEN)
            
            self.client_thread = threading.Thread(target=self._run_client_listener, daemon=True)
            self.client_thread.start()
        except Exception as e:
            self.client_socket = None
            self.status_callback(f"RETRYING LAN DISCOVERY...", ACCENT_YELLOW)
            if self.role == "Sender" and self.running and not self.manual_ip:
                self.discovery_thread = threading.Thread(target=self._run_udp_discovery, daemon=True)
                self.discovery_thread.start()

    def _run_client_listener(self):
        buffer = ""
        sock = self.client_socket
        while self.running and self.role == "Sender" and sock:
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
                            if msg.get("type") == "HANDSHAKE":
                                self.connected_peer_name = msg.get("name", self.connected_peer_name)
                                self.status_callback(f"PAIRED: [{self.connected_peer_name}] ({self.connected_peer_ip})", ACCENT_GREEN)
                            else:
                                self.message_callback(msg)
                        except Exception:
                            pass
            except Exception:
                break

        if self.client_socket == sock:
            self.client_socket = None
            self.connected_peer_name = None
            self.connected_peer_ip = None
            if self.role == "Sender" and self.running:
                self.status_callback(f"DISCONNECTED. RE-DISCOVERING...", ACCENT_YELLOW)
                self.discovery_thread = threading.Thread(target=self._run_udp_discovery, daemon=True)
                self.discovery_thread.start()

    def send_packet(self, data_dict):
        try:
            payload = (json.dumps(data_dict) + "\n").encode("utf-8")
            if self.role == "Sender" and self.client_socket:
                self.client_socket.sendall(payload)
            elif self.role == "Receiver" and self.active_receiver_conn:
                self.active_receiver_conn.sendall(payload)
        except Exception:
            pass

    def stop_networking(self):
        self.manual_ip = None
        if self.client_socket:
            try:
                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()
            except Exception:
                pass
            self.client_socket = None

        if self.active_receiver_conn:
            try:
                self.active_receiver_conn.shutdown(socket.SHUT_RDWR)
                self.active_receiver_conn.close()
            except Exception:
                pass
            self.active_receiver_conn = None

        if self.tcp_server:
            try:
                self.tcp_server.close()
            except Exception:
                pass
            self.tcp_server = None

        self.connected_peer_name = None
        self.connected_peer_ip = None

    def close(self):
        self.running = False
        self.stop_networking()


class TypingSimulatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('TypeGhost')
        self.geometry("920x680")
        self.minsize(740, 540)
        self.configure(bg=BG_ROOT)
        
        pyautogui.PAUSE = 0.0
        pyautogui.FAILSAFE = False

        self.typing_thread = None
        self.stop_typing = threading.Event()
        self.is_paused = threading.Event()
        self.is_fullscreen = False
        self._updating_text_programmatically = False
        self.current_percentage = 0
        self.current_layout_mode = None
        self._resize_debounce_job = None

        icon_path = os.path.join(getattr(sys, '_MEIPASS', os.path.abspath(".")), "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = "icon.ico"
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.network = NetworkManager(
            role_change_callback=self.on_role_change,
            message_callback=self.on_network_message,
            status_callback=self.update_network_status
        )

        self.create_widgets()

        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.end_fullscreen)
        self.bind("<Configure>", self.on_window_resize)

    def create_widgets(self):
        self.root_container = tk.Frame(self, bg=BG_ROOT, padx=8, pady=8)
        self.root_container.pack(fill="both", expand=True)

        # ==========================================
        # 1. HEADER (Original Dark Slate & Emerald Theme)
        # ==========================================
        self.header = tk.Frame(self.root_container, bg=BG_PANEL, highlightthickness=BORDER_WIDTH, highlightbackground=BORDER_COLOR, padx=14, pady=8)
        self.header.pack(fill="x", side="top", pady=(0, 8))

        # Brand
        brand_frame = tk.Frame(self.header, bg=BG_PANEL)
        brand_frame.pack(side="left", padx=(0, 16))
        
        bolt_label = tk.Label(brand_frame, text="⚡", font=("Segoe UI Emoji", 18, "bold"), fg=ACCENT_GREEN, bg=BG_PANEL)
        bolt_label.pack(side="left", padx=(0, 6))
        
        brand_titles = tk.Frame(brand_frame, bg=BG_PANEL)
        brand_titles.pack(side="left")
        tk.Label(brand_titles, text="TYPEGHOST", font=("Inter", 15, "bold"), fg=TEXT_MAIN, bg=BG_PANEL).pack(anchor="w")
        tk.Label(brand_titles, text="STEALTH LAN TYPING SIMULATOR", font=("JetBrains Mono", 8, "bold"), fg=ACCENT_GREEN, bg=BG_PANEL).pack(anchor="w")

        # Device Name
        dev_frame = tk.Frame(self.header, bg=BG_PANEL)
        dev_frame.pack(side="left", padx=(6, 12))
        tk.Label(dev_frame, text="DEVICE NAME", font=("JetBrains Mono", 8, "bold"), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w")
        
        self.device_name_entry = tk.Entry(
            dev_frame,
            font=("JetBrains Mono", 9, "bold"),
            bg=BG_INPUT,
            fg=TEXT_MAIN,
            insertbackground=ACCENT_GREEN,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            relief="flat",
            width=12
        )
        self.device_name_entry.insert(0, self.network.device_name)
        self.device_name_entry.pack(anchor="w", pady=(2, 0))
        self.device_name_entry.bind("<KeyRelease>", self.on_device_name_changed)

        # Network Role Selector - Selected role turns bright/light with glowing green border
        role_frame = tk.Frame(self.header, bg=BG_PANEL)
        role_frame.pack(side="left", padx=(4, 8))
        tk.Label(role_frame, text="NETWORK ROLE", font=("JetBrains Mono", 8, "bold"), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w")
        
        self.role_buttons_box = tk.Frame(role_frame, bg=BG_PANEL)
        self.role_buttons_box.pack(anchor="w", pady=(2, 0))
        
        self.role_buttons = {}
        roles = [("STANDALONE", "Standalone"), ("SENDER (CONTROLLER)", "Sender"), ("RECEIVER (TYPING TARGET)", "Receiver")]
        for text, val in roles:
            btn = tk.Button(
                self.role_buttons_box,
                text=text,
                font=("JetBrains Mono", 8, "bold"),
                relief="flat",
                highlightthickness=2,
                padx=6,
                pady=2,
                cursor="hand2",
                command=lambda v=val: self.select_role(v)
            )
            btn.pack(side="left", padx=(0, 5))
            self.role_buttons[val] = btn
        self.update_role_buttons_ui("Standalone")

        # Direct IP Connect Frame (Useful for complex subnets or AP isolation)
        self.manual_connect_frame = tk.Frame(self.header, bg=BG_PANEL)
        tk.Label(self.manual_connect_frame, text="CONNECT IP", font=("JetBrains Mono", 8, "bold"), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w")
        ip_row = tk.Frame(self.manual_connect_frame, bg=BG_PANEL)
        ip_row.pack(anchor="w", pady=(2, 0))
        
        self.manual_ip_entry = tk.Entry(
            ip_row,
            font=("JetBrains Mono", 8, "bold"),
            bg=BG_INPUT,
            fg=TEXT_MAIN,
            insertbackground=ACCENT_GREEN,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            relief="flat",
            width=12
        )
        self.manual_ip_entry.insert(0, "192.168.")
        self.manual_ip_entry.pack(side="left", padx=(0, 3))
        
        self.connect_ip_btn = tk.Button(
            ip_row,
            text="LINK",
            font=("JetBrains Mono", 7, "bold"),
            bg=ACCENT_GREEN,
            fg="#FFFFFF",
            relief="flat",
            cursor="hand2",
            command=self.on_manual_ip_connect,
            padx=4,
            pady=1
        )
        self.connect_ip_btn.pack(side="left")

        # Network Status Pill
        status_frame = tk.Frame(self.header, bg=BG_INPUT, highlightthickness=1, highlightbackground=BORDER_COLOR, padx=8, pady=4)
        status_frame.pack(side="right")
        
        tk.Label(status_frame, text="STATUS", font=("JetBrains Mono", 8, "bold"), fg=TEXT_MUTED, bg=BG_INPUT).pack(side="left", padx=(0, 5))
        self.status_dot = tk.Label(status_frame, text="■", font=("Segoe UI", 8, "bold"), fg=ACCENT_GREEN, bg=BG_INPUT)
        self.status_dot.pack(side="left", padx=(0, 4))
        
        self.status_label = tk.Label(
            status_frame,
            text="STANDALONE (LOCAL)",
            font=("JetBrains Mono", 8, "bold"),
            fg=TEXT_MAIN,
            bg=BG_INPUT
        )
        self.status_label.pack(side="left")

        # ==========================================
        # 2. MAIN RESPONSIVE CONTAINER
        # ==========================================
        self.content_container = tk.Frame(self.root_container, bg=BG_ROOT)
        self.content_container.pack(fill="both", expand=True, side="top", pady=(0, 8))

        # Top Parameters Frame (Compact / Small Window Mode)
        self.top_control_panel = tk.Frame(self.content_container, bg=BG_PANEL, highlightthickness=BORDER_WIDTH, highlightbackground=BORDER_COLOR, padx=14, pady=10)

        # Editor Card
        self.main_editor_card = tk.Frame(self.content_container, bg=BG_PANEL, highlightthickness=BORDER_WIDTH, highlightbackground=BORDER_COLOR, padx=14, pady=10)
        self.main_editor_card.grid_columnconfigure(0, weight=1)
        self.main_editor_card.grid_rowconfigure(1, weight=1)

        tk.Label(
            self.main_editor_card, 
            text="LIVE TEXT BUFFER (DIRECT IN-MEMORY NETWORK STREAM)", 
            font=("JetBrains Mono", 8, "bold"), 
            fg=TEXT_MUTED, 
            bg=BG_PANEL
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        editor_box = tk.Frame(self.main_editor_card, bg=BG_INPUT, highlightthickness=1, highlightbackground=BORDER_COLOR)
        editor_box.grid(row=1, column=0, sticky="nsew")
        editor_box.grid_columnconfigure(0, weight=1)
        editor_box.grid_rowconfigure(0, weight=1)

        self.text_editor = scrolledtext.ScrolledText(
            editor_box,
            wrap=tk.WORD,
            padx=14,
            pady=14,
            font=('Consolas', 12),
            bg="#181A1F",
            fg="#FFFFFF",
            insertbackground="#00BC8C",
            selectbackground="#00BC8C",
            selectforeground="#000000",
            relief="flat",
            borderwidth=0
        )
        self.text_editor.grid(row=0, column=0, sticky="nsew")
        self.text_editor.bind("<<Paste>>", self.on_text_pasted)
        self.text_editor.bind("<KeyRelease>", self.on_text_changed)

        # Right Sidebar Frame (Fullscreen / Wide Window Mode)
        self.sidebar_panel = tk.Frame(self.content_container, bg=BG_PANEL, highlightthickness=BORDER_WIDTH, highlightbackground=BORDER_COLOR, width=300, padx=14, pady=14)

        self.create_controls_widgets()

        # ==========================================
        # 3. FOOTER
        # ==========================================
        footer = tk.Frame(self.root_container, bg=BG_PANEL, highlightthickness=BORDER_WIDTH, highlightbackground=BORDER_COLOR, padx=14, pady=8)
        footer.pack(fill="x", side="bottom")
        footer.grid_columnconfigure((0, 1, 2), weight=1)

        f1 = tk.Label(footer, text="⚡ ESC: STOP / CLEAR", font=("JetBrains Mono", 9, "bold"), fg=ACCENT_RED, bg=BG_PANEL)
        f1.grid(row=0, column=0, sticky="w")

        f2 = tk.Label(footer, text="⏸  ← (LEFT ARROW): PAUSE", font=("JetBrains Mono", 9, "bold"), fg=ACCENT_YELLOW, bg=BG_PANEL)
        f2.grid(row=0, column=1)

        f3 = tk.Label(footer, text="▶  → (RIGHT ARROW): START / RESUME", font=("JetBrains Mono", 9, "bold"), fg=ACCENT_GREEN, bg=BG_PANEL)
        f3.grid(row=0, column=2, sticky="e")

        self.apply_layout('stacked')

    def create_controls_widgets(self):
        # 1. Top Panel Sub-Containers
        self.top_wpm_box = tk.Frame(self.top_control_panel, bg=BG_PANEL)
        tk.Label(self.top_wpm_box, text="SPEED (WPM)", font=("JetBrains Mono", 8, "bold"), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w")
        self.wpm_top_entry = tk.Entry(
            self.top_wpm_box,
            font=("JetBrains Mono", 14, "bold"),
            bg=BG_INPUT,
            fg=TEXT_MAIN,
            insertbackground=ACCENT_GREEN,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            relief="flat",
            justify="center",
            width=6
        )
        self.wpm_top_entry.insert(0, '100')
        self.wpm_top_entry.pack(side="left", pady=(2, 0))
        self.wpm_top_entry.bind("<KeyRelease>", lambda e: self.sync_inputs('wpm', self.wpm_top_entry.get()))

        self.top_acc_box = tk.Frame(self.top_control_panel, bg=BG_PANEL)
        tk.Label(self.top_acc_box, text="ACCURACY (0-1.0)", font=("JetBrains Mono", 8, "bold"), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w")
        self.acc_top_entry = tk.Entry(
            self.top_acc_box,
            font=("JetBrains Mono", 14, "bold"),
            bg=BG_INPUT,
            fg=TEXT_MAIN,
            insertbackground=ACCENT_GREEN,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            relief="flat",
            justify="center",
            width=6
        )
        self.acc_top_entry.insert(0, '0.98')
        self.acc_top_entry.pack(side="left", pady=(2, 0))
        self.acc_top_entry.bind("<KeyRelease>", lambda e: self.sync_inputs('acc', self.acc_top_entry.get()))

        self.start_top_btn = tk.Button(
            self.top_control_panel,
            text="▶  START TYPING (→)",
            font=("Inter", 10, "bold"),
            bg=ACCENT_GREEN,
            fg="#FFFFFF",
            activebackground="#00D8A1",
            activeforeground="#FFFFFF",
            highlightthickness=0,
            relief="flat",
            cursor="hand2",
            command=self.handle_start_action,
            pady=8
        )

        self.clear_top_btn = tk.Button(
            self.top_control_panel,
            text="⏹  STOP & CLEAR (ESC)",
            font=("Inter", 10, "bold"),
            bg=ACCENT_RED,
            fg="#FFFFFF",
            activebackground="#FF6B6B",
            activeforeground="#FFFFFF",
            highlightthickness=0,
            relief="flat",
            cursor="hand2",
            command=self.handle_clear_action,
            pady=8
        )

        # 2. Sidebar Panel Sub-Containers
        self.sidebar_content = tk.Frame(self.sidebar_panel, bg=BG_PANEL)
        
        tk.Label(self.sidebar_content, text="TYPING SPEED", font=("JetBrains Mono", 9, "bold"), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w", pady=(0, 2))
        tk.Frame(self.sidebar_content, bg=BORDER_COLOR, height=1).pack(fill="x", pady=(0, 8))
        
        w_row = tk.Frame(self.sidebar_content, bg=BG_PANEL)
        w_row.pack(fill="x", pady=(0, 16))
        self.wpm_side_entry = tk.Entry(
            w_row,
            font=("JetBrains Mono", 16, "bold"),
            bg=BG_INPUT,
            fg=TEXT_MAIN,
            insertbackground=ACCENT_GREEN,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            relief="flat",
            justify="center",
            width=6
        )
        self.wpm_side_entry.insert(0, '100')
        self.wpm_side_entry.pack(fill="x", side="left", expand=True)
        self.wpm_side_entry.bind("<KeyRelease>", lambda e: self.sync_inputs('wpm', self.wpm_side_entry.get()))
        tk.Label(w_row, text=" WPM", font=("JetBrains Mono", 10, "bold"), fg=TEXT_MAIN, bg=BG_PANEL).pack(side="left", padx=(6, 0))

        tk.Label(self.sidebar_content, text="HUMAN ACCURACY", font=("JetBrains Mono", 9, "bold"), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w", pady=(0, 2))
        tk.Frame(self.sidebar_content, bg=BORDER_COLOR, height=1).pack(fill="x", pady=(0, 8))
        self.acc_side_entry = tk.Entry(
            self.sidebar_content,
            font=("JetBrains Mono", 16, "bold"),
            bg=BG_INPUT,
            fg=TEXT_MAIN,
            insertbackground=ACCENT_GREEN,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            relief="flat",
            justify="center",
            width=6
        )
        self.acc_side_entry.insert(0, '0.98')
        self.acc_side_entry.pack(fill="x", pady=(0, 2))
        self.acc_side_entry.bind("<KeyRelease>", lambda e: self.sync_inputs('acc', self.acc_side_entry.get()))
        tk.Label(self.sidebar_content, text="(0.0 - 1.0)", font=("JetBrains Mono", 8, "bold"), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="e", pady=(0, 16))

        tk.Frame(self.sidebar_content, bg=BG_PANEL).pack(fill="both", expand=True)

        self.start_side_btn = tk.Button(
            self.sidebar_content,
            text="▶  START TYPING (→)",
            font=("Inter", 10, "bold"),
            bg=ACCENT_GREEN,
            fg="#FFFFFF",
            activebackground="#00D8A1",
            activeforeground="#FFFFFF",
            highlightthickness=0,
            relief="flat",
            cursor="hand2",
            command=self.handle_start_action,
            pady=10
        )
        self.start_side_btn.pack(fill="x", pady=(0, 10))

        self.clear_side_btn = tk.Button(
            self.sidebar_content,
            text="⏹  STOP & CLEAR (ESC)",
            font=("Inter", 10, "bold"),
            bg=ACCENT_RED,
            fg="#FFFFFF",
            activebackground="#FF6B6B",
            activeforeground="#FFFFFF",
            highlightthickness=0,
            relief="flat",
            cursor="hand2",
            command=self.handle_clear_action,
            pady=10
        )
        self.clear_side_btn.pack(fill="x")

    def on_manual_ip_connect(self):
        ip = self.manual_ip_entry.get().strip()
        if ip:
            self.network.connect_manual_ip(ip)

    def sync_inputs(self, kind, val):
        if kind == 'wpm':
            if self.wpm_top_entry.get() != val:
                self.wpm_top_entry.delete(0, tk.END)
                self.wpm_top_entry.insert(0, val)
            if self.wpm_side_entry.get() != val:
                self.wpm_side_entry.delete(0, tk.END)
                self.wpm_side_entry.insert(0, val)
        elif kind == 'acc':
            if self.acc_top_entry.get() != val:
                self.acc_top_entry.delete(0, tk.END)
                self.acc_top_entry.insert(0, val)
            if self.acc_side_entry.get() != val:
                self.acc_side_entry.delete(0, tk.END)
                self.acc_side_entry.insert(0, val)
        self.on_params_changed()

    def get_wpm_val(self):
        return self.wpm_top_entry.get().strip() or "100"

    def get_acc_val(self):
        return self.acc_top_entry.get().strip() or "0.98"

    def set_wpm_val(self, val):
        self.wpm_top_entry.delete(0, tk.END)
        self.wpm_top_entry.insert(0, str(val))
        self.wpm_side_entry.delete(0, tk.END)
        self.wpm_side_entry.insert(0, str(val))

    def set_acc_val(self, val):
        self.acc_top_entry.delete(0, tk.END)
        self.acc_top_entry.insert(0, str(val))
        self.acc_side_entry.delete(0, tk.END)
        self.acc_side_entry.insert(0, str(val))

    def select_role(self, role):
        self.network.set_role(role)
        self.update_role_buttons_ui(role)
        self.update_start_button_text()
        
        # Show Direct IP Connect field in Sender mode
        if role == "Sender":
            self.manual_connect_frame.pack(side="left", padx=(6, 12))
        else:
            self.manual_connect_frame.pack_forget()

    def update_role_buttons_ui(self, active_role):
        for role_val, btn in self.role_buttons.items():
            if role_val == active_role:
                btn.configure(
                    bg="#FFFFFF",
                    fg="#1A1A1A",
                    activebackground="#FFFFFF",
                    activeforeground="#000000",
                    highlightbackground=ACCENT_GREEN,
                    highlightthickness=2
                )
            else:
                btn.configure(
                    bg=BG_INPUT,
                    fg=TEXT_MUTED,
                    activebackground="#252A30",
                    activeforeground=TEXT_MAIN,
                    highlightbackground=BORDER_COLOR,
                    highlightthickness=1
                )

    def on_window_resize(self, event):
        if event.widget == self:
            if self._resize_debounce_job:
                self.after_cancel(self._resize_debounce_job)
            self._resize_debounce_job = self.after(50, self._check_resize_layout)

    def _check_resize_layout(self):
        width = self.winfo_width()
        if width >= 1100 or self.is_fullscreen:
            if self.current_layout_mode != 'sidebar':
                self.apply_layout('sidebar')
        else:
            if self.current_layout_mode != 'stacked':
                self.apply_layout('stacked')

    def apply_layout(self, mode):
        self.current_layout_mode = mode
        
        self.top_control_panel.grid_forget()
        self.main_editor_card.grid_forget()
        self.sidebar_panel.grid_forget()
        self.sidebar_content.pack_forget()

        if mode == 'stacked':
            self.content_container.grid_columnconfigure(0, weight=1)
            self.content_container.grid_columnconfigure(1, weight=0)
            self.content_container.grid_rowconfigure(0, weight=0)
            self.content_container.grid_rowconfigure(1, weight=1)

            self.top_control_panel.grid(row=0, column=0, sticky="ew", pady=(0, 8))
            self.top_control_panel.grid_columnconfigure((0, 1, 2, 3), weight=1)
            
            self.top_wpm_box.grid(row=0, column=0, padx=8, sticky="w")
            self.top_acc_box.grid(row=0, column=1, padx=8, sticky="w")
            self.start_top_btn.grid(row=0, column=2, padx=6, sticky="ew")
            self.clear_top_btn.grid(row=0, column=3, padx=6, sticky="ew")

            self.main_editor_card.grid(row=1, column=0, sticky="nsew")

        else:
            self.content_container.grid_columnconfigure(0, weight=1)
            self.content_container.grid_columnconfigure(1, weight=0)
            self.content_container.grid_rowconfigure(0, weight=1)
            self.content_container.grid_rowconfigure(1, weight=0)

            self.main_editor_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
            self.sidebar_panel.grid(row=0, column=1, sticky="nsew")
            self.sidebar_panel.grid_propagate(False)
            self.sidebar_content.pack(fill="both", expand=True)

        self.update_start_button_text()

    def update_start_button_text(self, pct=None):
        if pct is not None:
            self.current_percentage = int(pct)
        
        p_str = f" [{self.current_percentage}%]" if self.current_percentage > 0 else ""
        role = self.network.role
        
        if role == "Receiver":
            if self.current_percentage > 0:
                txt = f"RECEIVER TYPING...{p_str}"
            else:
                txt = "RECEIVER ACTIVE (LISTENING)"
        elif role == "Sender":
            if self.current_percentage > 0:
                txt = f"▶  REMOTE TYPING...{p_str} (→)"
            else:
                txt = "▶  SEND & START (→)"
        else:
            if self.current_percentage > 0:
                txt = f"▶  TYPING...{p_str} (→)"
            else:
                txt = "▶  START TYPING (→)"

        self.start_top_btn.configure(text=txt)
        self.start_side_btn.configure(text=txt)

    def on_device_name_changed(self, event=None):
        new_name = self.device_name_entry.get().strip()
        if new_name:
            self.network.set_device_name(new_name)
            if self.network.role == "Standalone":
                self.status_label.configure(text=f"STANDALONE ({new_name})")

    def update_network_status(self, text, color=ACCENT_GREEN):
        def update():
            self.status_label.configure(text=text.upper())
            self.status_dot.configure(fg=color)
        self.after(0, update)

    def on_role_change(self, role):
        pass

    def on_text_pasted(self, event=None):
        self.after(20, self.on_text_changed)

    def on_text_changed(self, event=None):
        if self._updating_text_programmatically:
            return
        if self.network.role == "Sender":
            text = self.text_editor.get("1.0", tk.END).strip()
            wpm = self.get_wpm_val()
            accuracy = self.get_acc_val()
            self.network.send_packet({
                "type": "SYNC_DATA",
                "text": text,
                "wpm": wpm,
                "accuracy": accuracy
            })

    def on_params_changed(self, event=None):
        self.on_text_changed()

    def on_network_message(self, msg):
        msg_type = msg.get("type")
        if msg_type == "SYNC_DATA":
            text = msg.get("text", "")
            wpm = msg.get("wpm", "100")
            accuracy = msg.get("accuracy", "0.98")
            
            def apply_remote_sync():
                self._updating_text_programmatically = True
                self.text_editor.delete("1.0", tk.END)
                self.text_editor.insert(tk.END, text)
                self.set_wpm_val(wpm)
                self.set_acc_val(accuracy)
                self._updating_text_programmatically = False

            self.after(0, apply_remote_sync)

        elif msg_type == "CMD_START":
            self.after(0, self.startTyping)

        elif msg_type == "CMD_PAUSE":
            self.after(0, self.pauseTyping)

        elif msg_type == "CMD_RESUME":
            self.after(0, self.resumeTyping)

        elif msg_type == "CMD_CLEAR":
            self.after(0, self.stopAndReset)

        elif msg_type == "PROGRESS_UPDATE":
            pct = msg.get("percentage", 0)
            self.after(0, lambda: self.update_start_button_text(pct))

    def handle_start_action(self):
        if self.network.role == "Sender":
            self.on_text_changed()
            self.network.send_packet({"type": "CMD_START"})
        else:
            self.startTyping()

    def handle_pause_action(self):
        if self.network.role == "Sender":
            self.network.send_packet({"type": "CMD_PAUSE"})
        else:
            self.pauseTyping()

    def handle_clear_action(self):
        if self.network.role == "Sender":
            self.network.send_packet({"type": "CMD_CLEAR"})
        self.stopAndReset()

    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        if self.is_fullscreen:
            self.apply_layout('sidebar')
        else:
            self.apply_layout('stacked')
        return "break"

    def end_fullscreen(self, event=None):
        self.is_fullscreen = False
        self.attributes("-fullscreen", False)
        self.apply_layout('stacked')
        return "break"

    def startTyping(self):
        self.is_paused.clear()
        self.stop_typing.clear()
        if not self.typing_thread or not self.typing_thread.is_alive():
            self.typing_thread = threading.Thread(target=self.typingProcess, daemon=True)
            self.typing_thread.start()

    def pauseTyping(self):
        self.is_paused.set()

    def resumeTyping(self):
        self.is_paused.clear()
        if not self.typing_thread or not self.typing_thread.is_alive():
            self.startTyping()

    def stopAndReset(self):
        self.stop_typing.set()
        if self.typing_thread and self.typing_thread.is_alive():
            self.typing_thread.join(timeout=0.1)
        self._updating_text_programmatically = True
        self.text_editor.delete("1.0", tk.END)
        self._updating_text_programmatically = False
        self.is_paused.clear()
        self.current_percentage = 0
        self.update_start_button_text(0)

    def typingProcess(self):
        text_to_type = self.text_editor.get("1.0", tk.END).strip()
        if not text_to_type:
            return

        try:
            wpm = float(self.get_wpm_val())
        except ValueError:
            wpm = 100.0

        try:
            accuracy = float(self.get_acc_val())
        except ValueError:
            accuracy = 0.98

        self.global_typoer(text_to_type, wpm, accuracy)

    def global_typoer(self, text, wpm, accuracy):
        chars_per_minute = max(wpm * 5, 1)
        interval = 60.0 / chars_per_minute
        correction_interval = interval * 0.5

        total_chars = max(len(text), 1)
        chars_typed = 0
        last_reported_pct = -1

        lines = text.split('\n')
        current_indent = 0
        typo_chars = 'abcdefghijklmnopqrstuvwxyz'

        for line in lines:
            line_indent = len(line) - len(line.lstrip())
            
            if line_indent > current_indent:
                for _ in range((line_indent - current_indent) // 4):
                    pyautogui.press('tab', interval=0)
            elif line_indent < current_indent:
                pyautogui.press('enter', interval=0)
                for _ in range((current_indent - line_indent) // 4):
                    pyautogui.press('backspace', interval=0)
            
            current_indent = line_indent
            stripped_line = line.strip()
            line_len = len(stripped_line)

            for i, char in enumerate(stripped_line):
                if self.stop_typing.is_set():
                    self.after(0, lambda: self.update_start_button_text(0))
                    return

                while self.is_paused.is_set():
                    if self.stop_typing.is_set():
                        self.after(0, lambda: self.update_start_button_text(0))
                        return
                    time.sleep(0.01)

                if random.random() > accuracy and i < line_len - 1:
                    wrong_char = random.choice(typo_chars)
                    pyautogui.typewrite(wrong_char, interval=0)
                    time.sleep(interval)
                    pyautogui.press('backspace', interval=0)
                    time.sleep(correction_interval)
                    pyautogui.typewrite(char, interval=0)
                    time.sleep(correction_interval)
                else:
                    pyautogui.typewrite(char, interval=0)
                    time.sleep(interval)

                chars_typed += 1
                pct = int((chars_typed / total_chars) * 100)
                if pct != last_reported_pct:
                    last_reported_pct = pct
                    self.after(0, lambda p=pct: self.update_start_button_text(p))
                    if self.network.role == "Receiver":
                        self.network.send_packet({"type": "PROGRESS_UPDATE", "percentage": pct})
            
            if line != lines[-1]:
                pyautogui.press('enter', interval=0)
                time.sleep(interval)
                chars_typed += 1
                pct = int((chars_typed / total_chars) * 100)
                if pct != last_reported_pct:
                    last_reported_pct = pct
                    self.after(0, lambda p=pct: self.update_start_button_text(p))
                    if self.network.role == "Receiver":
                        self.network.send_packet({"type": "PROGRESS_UPDATE", "percentage": pct})

        self.after(0, lambda: self.update_start_button_text(100))
        if self.network.role == "Receiver":
            self.network.send_packet({"type": "PROGRESS_UPDATE", "percentage": 100})

    def on_press(self, key):
        if key == keyboard.Key.esc:
            self.handle_clear_action()
        elif key == keyboard.Key.left:
            self.handle_pause_action()
        elif key == keyboard.Key.right:
            if self.network.role == "Sender":
                self.network.send_packet({"type": "CMD_RESUME"})
            else:
                self.resumeTyping()

    def on_closing(self):
        self.stop_typing.set()
        if self.network:
            self.network.close()
        if self.typing_thread and self.typing_thread.is_alive():
            self.typing_thread.join(timeout=0.1)
        if self.listener and self.listener.running:
            self.listener.stop()
        self.destroy()

if __name__ == '__main__':
    app = TypingSimulatorApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()