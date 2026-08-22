import tkinter as tk
from tkinter import scrolledtext
import threading
import socket
import json
import time
import random
import platform
import os
import pyautogui
from pynput import keyboard
from ttkbootstrap import Style
from ttkbootstrap.constants import *
import ttkbootstrap as ttk

DISCOVERY_PORT = 45454
TCP_COMM_PORT = 45455
MAGIC_HEADER = "TYPEGHOST_BEACON"

class NetworkManager:
    def __init__(self, role_change_callback, message_callback, status_callback):
        self.role = "Standalone"  # Standalone, Sender, Receiver
        self.role_change_callback = role_change_callback
        self.message_callback = message_callback
        self.status_callback = status_callback
        
        self.device_name = platform.node() or "TypeGhost-Device"
        self.running = True
        
        # Sockets and connection state
        self.tcp_server = None
        self.server_thread = None
        self.broadcast_thread = None
        self.discovery_thread = None
        
        self.active_receiver_conn = None
        self.client_socket = None
        self.client_thread = None
        self.connected_peer_name = None
        self.connected_peer_ip = None

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def set_device_name(self, new_name):
        clean_name = new_name.strip()
        if clean_name:
            self.device_name = clean_name
            if self.role == "Receiver":
                self.status_callback(f"Listening as [{self.device_name}] on {self.get_local_ip()}:{TCP_COMM_PORT}", "success")
            elif self.role == "Sender" and not self.client_socket:
                self.status_callback(f"[{self.device_name}] Discovering receivers on LAN...", "warning")

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
            self.status_callback("Standalone Mode (Local Execution)", "secondary")

    def start_receiver_mode(self):
        self.status_callback(f"Receiver [{self.device_name}]: Starting listener...", "info")
        self.server_thread = threading.Thread(target=self._run_tcp_server, daemon=True)
        self.server_thread.start()

        self.broadcast_thread = threading.Thread(target=self._run_udp_broadcast, daemon=True)
        self.broadcast_thread.start()

    def start_sender_mode(self):
        self.status_callback(f"Sender [{self.device_name}]: Auto-discovering on LAN...", "warning")
        self.discovery_thread = threading.Thread(target=self._run_udp_discovery, daemon=True)
        self.discovery_thread.start()

    def _run_udp_broadcast(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1.0)
        
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
                sock.sendto(payload, ("<broadcast>", DISCOVERY_PORT))
            except Exception:
                pass
            time.sleep(1.5)
        try:
            sock.close()
        except Exception:
            pass

    def _run_udp_discovery(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", DISCOVERY_PORT))
        except Exception as e:
            self.status_callback(f"Discovery bind error: {e}", "danger")
            return

        sock.settimeout(2.0)
        while self.running and self.role == "Sender" and not self.client_socket:
            try:
                data, addr = sock.recvfrom(2048)
                msg = json.loads(data.decode("utf-8"))
                if msg.get("magic") == MAGIC_HEADER and msg.get("role") == "Receiver":
                    target_ip = addr[0]
                    target_name = msg.get("name", "Unknown Receiver")
                    target_port = msg.get("port", TCP_COMM_PORT)
                    self.status_callback(f"Found [{target_name}] ({target_ip}). Connecting...", "info")
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
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("0.0.0.0", TCP_COMM_PORT))
            server.listen(1)
            server.settimeout(1.5)
            self.tcp_server = server
            self.status_callback(f"Listening as [{self.device_name}] on {self.get_local_ip()}:{TCP_COMM_PORT}", "success")
        except Exception as e:
            self.status_callback(f"Server start failed: {e}", "danger")
            return

        while self.running and self.role == "Receiver":
            try:
                conn, addr = server.accept()
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
                                self.status_callback(f"Connected with Sender [{self.connected_peer_name}] ({self.connected_peer_ip})", "success")
                            else:
                                self.message_callback(msg)
                        except Exception as e:
                            print("Msg parse error:", e)
        except Exception as e:
            print("Connection error:", e)
        finally:
            conn.close()
            self.active_receiver_conn = None
            self.connected_peer_name = None
            self.connected_peer_ip = None
            if self.role == "Receiver" and self.running:
                self.status_callback(f"Receiver [{self.device_name}]: Waiting for Sender...", "warning")

    def _connect_to_receiver(self, ip, port, peer_name):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, port))
            handshake = json.dumps({"type": "HANDSHAKE", "name": self.device_name}) + "\n"
            sock.sendall(handshake.encode("utf-8"))
            
            self.client_socket = sock
            self.connected_peer_name = peer_name
            self.connected_peer_ip = ip
            self.status_callback(f"Paired with Receiver [{peer_name}] ({ip})", "success")
            
            self.client_thread = threading.Thread(target=self._run_client_listener, daemon=True)
            self.client_thread.start()
        except Exception as e:
            self.client_socket = None
            self.status_callback(f"Connection failed: {e}. Retrying...", "warning")
            if self.role == "Sender" and self.running:
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
                                self.status_callback(f"Paired with Receiver [{self.connected_peer_name}] ({self.connected_peer_ip})", "success")
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
                self.status_callback(f"Disconnected from Receiver. Re-discovering on LAN...", "warning")
                self.discovery_thread = threading.Thread(target=self._run_udp_discovery, daemon=True)
                self.discovery_thread.start()

    def send_packet(self, data_dict):
        try:
            payload = (json.dumps(data_dict) + "\n").encode("utf-8")
            if self.role == "Sender" and self.client_socket:
                self.client_socket.sendall(payload)
            elif self.role == "Receiver" and self.active_receiver_conn:
                self.active_receiver_conn.sendall(payload)
        except Exception as e:
            print("Failed to send packet:", e)

    def stop_networking(self):
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
        self.geometry("1120x800")
        self.minsize(920, 640)
        
        self.typing_thread = None
        self.stop_typing = threading.Event()
        self.is_paused = threading.Event()
        self.is_fullscreen = False
        self._updating_text_programmatically = False
        self.current_percentage = 0

        # Load modern window icon if present
        if os.path.exists("icon.ico"):
            try:
                self.iconbitmap("icon.ico")
            except Exception:
                pass

        # Premium Dark Styling & Color Theme
        self.style = Style(theme='darkly')
        
        # Configure refined typography and component styles
        self.style.configure('TButton', font=('Segoe UI', 11, 'bold'), borderwidth=0)
        self.style.configure('Start.TButton', font=('Segoe UI', 12, 'bold'), background='#00bc8c')
        self.style.configure('Stop.TButton', font=('Segoe UI', 12, 'bold'), background='#e74c3c')
        self.style.configure('TLabel', font=('Segoe UI', 10))
        self.style.configure('Brand.TLabel', font=('Segoe UI', 17, 'bold'), foreground='#00f2fe')
        self.style.configure('Tagline.TLabel', font=('Segoe UI', 9, 'italic'), foreground='#888888')
        self.style.configure('CardTitle.TLabel', font=('Segoe UI', 10, 'bold'), foreground='#38ef7d')
        self.style.configure('StatusBadge.TLabel', font=('Segoe UI', 10, 'bold'))

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

    def create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Root Outer Container
        self.main_frame = ttk.Frame(self, padding="24")
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=1)

        # --- 1. HEADER SECTION (Brand & Connection Dashboard) ---
        header_card = ttk.Frame(self.main_frame, padding="16", bootstyle="dark")
        header_card.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header_card.grid_columnconfigure(1, weight=1)

        # Brand Title
        brand_frame = ttk.Frame(header_card, bootstyle="dark")
        brand_frame.grid(row=0, column=0, sticky="w", padx=(0, 25))
        ttk.Label(brand_frame, text="⚡ TYPEGHOST", style='Brand.TLabel').pack(anchor="w")
        ttk.Label(brand_frame, text="Stealth LAN Typing Simulator", style='Tagline.TLabel').pack(anchor="w")

        # Network Controls & Device Name
        controls_group = ttk.Frame(header_card, bootstyle="dark")
        controls_group.grid(row=0, column=1, sticky="ew")
        controls_group.grid_columnconfigure(3, weight=1)

        # Device Name
        name_sub = ttk.Frame(controls_group, bootstyle="dark")
        name_sub.grid(row=0, column=0, padx=(0, 20), sticky="w")
        ttk.Label(name_sub, text="DEVICE NAME", font=('Segoe UI', 8, 'bold'), foreground='#7f8c8d').pack(anchor="w")
        self.device_name_entry = ttk.Entry(name_sub, width=15, font=('Segoe UI', 10))
        self.device_name_entry.insert(0, self.network.device_name)
        self.device_name_entry.pack(anchor="w", pady=(2, 0))
        self.device_name_entry.bind("<KeyRelease>", self.on_device_name_changed)

        # Mode Selection
        role_sub = ttk.Frame(controls_group, bootstyle="dark")
        role_sub.grid(row=0, column=1, padx=(0, 20), sticky="w")
        ttk.Label(role_sub, text="NETWORK ROLE", font=('Segoe UI', 8, 'bold'), foreground='#7f8c8d').pack(anchor="w")
        
        roles_box = ttk.Frame(role_sub, bootstyle="dark")
        roles_box.pack(anchor="w", pady=(2, 0))
        self.role_var = tk.StringVar(value="Standalone")
        roles = [("Standalone", "Standalone"), ("Sender (Controller)", "Sender"), ("Receiver (Typing Target)", "Receiver")]
        for text, value in roles:
            rb = ttk.Radiobutton(roles_box, text=text, value=value, variable=self.role_var, command=self.on_role_radio_changed)
            rb.pack(side="left", padx=5)

        # Status Pill Indicator
        status_sub = ttk.Frame(controls_group, bootstyle="dark")
        status_sub.grid(row=0, column=3, sticky="e")
        ttk.Label(status_sub, text="NETWORK STATUS", font=('Segoe UI', 8, 'bold'), foreground='#7f8c8d').pack(anchor="e")
        self.status_label = ttk.Label(
            status_sub, 
            text=f"● Standalone (Local)", 
            style='StatusBadge.TLabel', 
            bootstyle="secondary"
        )
        self.status_label.pack(anchor="e", pady=(2, 0))

        # --- 2. CONTROL DASHBOARD (Speed, Accuracy, Action Buttons) ---
        dash_frame = ttk.Frame(self.main_frame, padding="14", bootstyle="secondary")
        dash_frame.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        dash_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # WPM input
        wpm_box = ttk.Frame(dash_frame, bootstyle="secondary")
        wpm_box.grid(row=0, column=0, sticky="w", padx=10)
        ttk.Label(wpm_box, text="TYPING SPEED", font=('Segoe UI', 9, 'bold'), foreground='#adb5bd', bootstyle="inverse-secondary").pack(anchor="w")
        wpm_input_row = ttk.Frame(wpm_box, bootstyle="secondary")
        wpm_input_row.pack(anchor="w", pady=(3, 0))
        self.wpm_input = ttk.Entry(wpm_input_row, width=8, font=('Segoe UI', 12, 'bold'))
        self.wpm_input.pack(side="left")
        self.wpm_input.insert(0, '100')
        self.wpm_input.bind("<KeyRelease>", self.on_params_changed)
        ttk.Label(wpm_input_row, text=" WPM", font=('Segoe UI', 10, 'bold'), foreground='#adb5bd', bootstyle="inverse-secondary").pack(side="left")

        # Accuracy input
        acc_box = ttk.Frame(dash_frame, bootstyle="secondary")
        acc_box.grid(row=0, column=1, sticky="w", padx=10)
        ttk.Label(acc_box, text="HUMAN ACCURACY", font=('Segoe UI', 9, 'bold'), foreground='#adb5bd', bootstyle="inverse-secondary").pack(anchor="w")
        acc_input_row = ttk.Frame(acc_box, bootstyle="secondary")
        acc_input_row.pack(anchor="w", pady=(3, 0))
        self.accuracy_input = ttk.Entry(acc_input_row, width=8, font=('Segoe UI', 12, 'bold'))
        self.accuracy_input.pack(side="left")
        self.accuracy_input.insert(0, '0.98')
        self.accuracy_input.bind("<KeyRelease>", self.on_params_changed)
        ttk.Label(acc_input_row, text=" (0.0 - 1.0)", font=('Segoe UI', 9), foreground='#adb5bd', bootstyle="inverse-secondary").pack(side="left")

        # Action Buttons
        self.start_button = ttk.Button(
            dash_frame, 
            text="▶ Start Typing (→)", 
            command=self.handle_start_action, 
            style='success.TButton',
            padding=10
        )
        self.start_button.grid(row=0, column=2, padx=8, sticky="ew")

        self.clear_button = ttk.Button(
            dash_frame, 
            text="⏹ Stop & Clear (ESC)", 
            command=self.handle_clear_action, 
            style='danger.TButton',
            padding=10
        )
        self.clear_button.grid(row=0, column=3, padx=8, sticky="ew")

        # --- 3. TEXT EDITOR CARD ---
        editor_card = ttk.Labelframe(self.main_frame, text=" Live Text Buffer (Direct In-Memory Network Stream) ", padding="14")
        editor_card.grid(row=2, column=0, sticky="nsew", pady=(0, 14))
        editor_card.grid_columnconfigure(0, weight=1)
        editor_card.grid_rowconfigure(0, weight=1)

        self.text_editor = scrolledtext.ScrolledText(
            editor_card, 
            wrap=tk.WORD, 
            padx=18, 
            pady=18, 
            font=('Consolas', 13),
            bg="#181a1f",
            fg="#abb2bf",
            insertbackground="#528bff",
            selectbackground="#3e4451",
            relief="flat",
            borderwidth=0
        )
        self.text_editor.grid(row=0, column=0, sticky="nsew")
        
        self.text_editor.bind("<<Paste>>", self.on_text_pasted)
        self.text_editor.bind("<KeyRelease>", self.on_text_changed)

        # --- 4. MODERN FOOTER BAR ---
        footer_frame = ttk.Frame(self.main_frame)
        footer_frame.grid(row=3, column=0, sticky="ew")
        footer_frame.grid_columnconfigure((0, 1, 2), weight=1)

        f1 = ttk.Label(footer_frame, text="⚡ ESC: Stop / Clear", font=('Segoe UI', 9, 'bold'), foreground="#e74c3c")
        f1.grid(row=0, column=0, sticky="w")

        f2 = ttk.Label(footer_frame, text="⏸  ← (Left Arrow): Pause", font=('Segoe UI', 9, 'bold'), foreground="#f39c12")
        f2.grid(row=0, column=1)

        f3 = ttk.Label(footer_frame, text="▶  → (Right Arrow): Start / Resume", font=('Segoe UI', 9, 'bold'), foreground="#00bc8c")
        f3.grid(row=0, column=2, sticky="e")

    def update_start_button_text(self, pct=None):
        if pct is not None:
            self.current_percentage = int(pct)
        
        p_str = f" [{self.current_percentage}%]" if self.current_percentage > 0 else ""
        role = self.network.role
        
        if role == "Receiver":
            if self.current_percentage > 0:
                self.start_button.configure(text=f"● Receiver Typing...{p_str}")
            else:
                self.start_button.configure(text="● Receiver Active (Awaiting commands)")
        elif role == "Sender":
            if self.current_percentage > 0:
                self.start_button.configure(text=f"▶ Remote Typing...{p_str} (→)")
            else:
                self.start_button.configure(text="▶ Send & Start Remote Typing (→)")
        else:
            if self.current_percentage > 0:
                self.start_button.configure(text=f"▶ Typing...{p_str} (→)")
            else:
                self.start_button.configure(text="▶ Start Typing (→)")

    def on_device_name_changed(self, event=None):
        new_name = self.device_name_entry.get().strip()
        if new_name:
            self.network.set_device_name(new_name)
            if self.network.role == "Standalone":
                self.status_label.configure(text=f"● Standalone ({new_name})", bootstyle="secondary")

    def on_role_radio_changed(self):
        new_role = self.role_var.get()
        self.network.set_role(new_role)
        self.update_start_button_text()

    def update_network_status(self, text, style_badge="info"):
        def update():
            # Add dot indicator
            display_text = f"● {text}" if not text.startswith("●") else text
            self.status_label.configure(text=display_text, bootstyle=style_badge)
        self.after(0, update)

    def on_role_change(self, role):
        pass

    def on_text_pasted(self, event=None):
        self.after(50, self.on_text_changed)

    def on_text_changed(self, event=None):
        if self._updating_text_programmatically:
            return
        if self.network.role == "Sender":
            text = self.text_editor.get("1.0", tk.END).strip()
            wpm = self.wpm_input.get().strip()
            accuracy = self.accuracy_input.get().strip()
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
                self.wpm_input.delete(0, tk.END)
                self.wpm_input.insert(0, wpm)
                self.accuracy_input.delete(0, tk.END)
                self.accuracy_input.insert(0, accuracy)
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
        return "break"

    def end_fullscreen(self, event=None):
        self.is_fullscreen = False
        self.attributes("-fullscreen", False)
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
            self.typing_thread.join(timeout=0.5)
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
            wpm = float(self.wpm_input.get())
        except ValueError:
            wpm = 100.0

        try:
            accuracy = float(self.accuracy_input.get())
        except ValueError:
            accuracy = 0.98

        self.global_typoer(text_to_type, wpm, accuracy)

    def global_typoer(self, text, wpm, accuracy):
        chars_per_minute = max(wpm * 5, 1)
        interval = 60.0 / chars_per_minute
        correction_interval = interval / 2

        total_chars = max(len(text), 1)
        chars_typed = 0

        lines = text.split('\n')
        current_indent = 0

        for line in lines:
            line_indent = len(line) - len(line.lstrip())
            
            if line_indent > current_indent:
                for _ in range((line_indent - current_indent) // 4):
                    pyautogui.press('tab', interval=interval)
            elif line_indent < current_indent:
                pyautogui.press('enter', interval=interval)
                for _ in range((current_indent - line_indent) // 4):
                    pyautogui.press('backspace', interval=interval)
            
            current_indent = line_indent

            for i, char in enumerate(line.strip()):
                if self.stop_typing.is_set():
                    self.after(0, lambda: self.update_start_button_text(0))
                    return

                while self.is_paused.is_set():
                    if self.stop_typing.is_set():
                        self.after(0, lambda: self.update_start_button_text(0))
                        return
                    time.sleep(0.05)

                if random.random() > accuracy and i < len(line.strip()) - 1:
                    wrong_char = random.choice('abcdefghijklmnopqrstuvwxyz')
                    pyautogui.typewrite(wrong_char, interval=interval)
                    pyautogui.press('backspace', interval=correction_interval)
                    pyautogui.typewrite(char, interval=correction_interval)
                else:
                    pyautogui.typewrite(char, interval=interval)

                chars_typed += 1
                pct = int((chars_typed / total_chars) * 100)
                self.after(0, lambda p=pct: self.update_start_button_text(p))
                
                if self.network.role == "Receiver":
                    self.network.send_packet({"type": "PROGRESS_UPDATE", "percentage": pct})
            
            if line != lines[-1]:
                pyautogui.press('enter', interval=interval)
                chars_typed += 1
                pct = int((chars_typed / total_chars) * 100)
                self.after(0, lambda p=pct: self.update_start_button_text(p))
                if self.network.role == "Receiver":
                    self.network.send_packet({"type": "PROGRESS_UPDATE", "percentage": pct})

        # Completed
        time.sleep(0.2)
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
            self.typing_thread.join(timeout=0.5)
        if self.listener and self.listener.running:
            self.listener.stop()
        self.destroy()

if __name__ == '__main__':
    app = TypingSimulatorApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()