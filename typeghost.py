import tkinter as tk
from tkinter import scrolledtext, ttk
import threading
import random
import pyautogui
from pynput import keyboard

class TypingSimulatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Typing Simulator')
        self.configure(bg="#f0f0f0")
        self.geometry("1280x720")
        self.typing_thread = None
        self.stop_typing = threading.Event()
        self.is_paused = threading.Event()
        self.typing_items = []
        self.current_item_index = 0

        self.create_widgets()

        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

    def create_widgets(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        self.sidebar_frame = ttk.Frame(self, padding="10")
        self.sidebar_frame.grid(row=0, column=1, sticky="nsew")
        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        self.sidebar_frame.grid_rowconfigure(1, weight=1)

        self.create_main_content()
        self.create_sidebar_content()

    def create_main_content(self):
        input_frame = ttk.Frame(self.main_frame)
        input_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        input_frame.grid_columnconfigure(1, weight=1)
        input_frame.grid_columnconfigure(3, weight=1)

        ttk.Label(input_frame, text='WPM:').grid(row=0, column=0, padx=(0, 5))
        self.wpm_input = ttk.Entry(input_frame, width=10)
        self.wpm_input.grid(row=0, column=1, sticky="ew", padx=(0, 20))
        self.wpm_input.insert(0, '100')

        ttk.Label(input_frame, text='Accuracy:').grid(row=0, column=2, padx=(0, 5))
        self.accuracy_input = ttk.Entry(input_frame, width=10)
        self.accuracy_input.grid(row=0, column=3, sticky="ew")
        self.accuracy_input.insert(0, '0.98')

        button_frame = ttk.Frame(input_frame)
        button_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        button_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.start_button = ttk.Button(button_frame, text="Start", command=self.startTyping)
        self.start_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.pause_button = ttk.Button(button_frame, text="Pause", command=self.pauseTyping)
        self.pause_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.clear_button = ttk.Button(button_frame, text="Clear", command=self.stopAndReset)
        self.clear_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        self.text_editor = scrolledtext.ScrolledText(self.main_frame, wrap=tk.WORD, padx=10, pady=10)
        self.text_editor.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        ttk.Label(self.main_frame, text="ESC: Clear | ←: Pause | →: Start/Continue", foreground="gray").grid(row=2, column=0, pady=(10, 0))

    def create_sidebar_content(self):
        ttk.Label(self.sidebar_frame, text="Typing Items", font=("TkDefaultFont", 12, "bold")).grid(row=0, column=0, pady=(0, 10))

        self.item_listbox = tk.Listbox(self.sidebar_frame)
        self.item_listbox.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.item_listbox.bind('<<ListboxSelect>>', self.on_item_select)

        button_frame = ttk.Frame(self.sidebar_frame)
        button_frame.grid(row=2, column=0, sticky="ew")
        button_frame.grid_columnconfigure((0, 1), weight=1)

        add_button = ttk.Button(button_frame, text="Add Item", command=self.add_item)
        add_button.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        remove_button = ttk.Button(button_frame, text="Remove Selected", command=self.remove_item)
        remove_button.grid(row=0, column=1, padx=(5, 0), sticky="ew")

    def on_item_select(self, event):
        selected = self.item_listbox.curselection()
        if selected:
            index = selected[0]
            item = self.typing_items[index]
            self.text_editor.delete("1.0", tk.END)
            self.text_editor.insert(tk.END, item['text'])
            self.wpm_input.delete(0, tk.END)
            self.wpm_input.insert(0, item['wpm'])
            self.accuracy_input.delete(0, tk.END)
            self.accuracy_input.insert(0, item['accuracy'])

    def add_item(self):
        text = self.text_editor.get("1.0", tk.END).strip()
        if text:
            wpm = self.wpm_input.get()
            accuracy = self.accuracy_input.get()
            item = {
                'text': text,
                'wpm': wpm,
                'accuracy': accuracy
            }
            self.typing_items.append(item)
            item_name = self.generate_item_name(text)
            self.item_listbox.insert(tk.END, item_name)
            self.text_editor.delete("1.0", tk.END)

    def generate_item_name(self, text):
        words = text.split()
        if len(words) <= 5:
            return ' '.join(words)
        return ' '.join(words[:5]) + '...'

    def remove_item(self):
        selected = self.item_listbox.curselection()
        if selected:
            index = selected[0]
            self.item_listbox.delete(index)
            del self.typing_items[index]

    def startTyping(self):
        self.is_paused.clear()
        self.stop_typing.clear()
        if not self.typing_thread or not self.typing_thread.is_alive():
            self.typing_thread = threading.Thread(target=self.typingProcess)
            self.typing_thread.start()

    def pauseTyping(self):
        self.is_paused.set()

    def stopAndReset(self):
        self.stop_typing.set()
        if self.typing_thread and self.typing_thread.is_alive():
            self.typing_thread.join()
        self.text_editor.delete("1.0", tk.END)
        self.is_paused.clear()
        self.current_item_index = 0

    def typingProcess(self):
        while self.current_item_index < len(self.typing_items):
            item = self.typing_items[self.current_item_index]
            text_to_type = item['text']
            wpm = float(item['wpm'])
            accuracy = float(item['accuracy'])
            
            self.text_editor.delete("1.0", tk.END)
            self.text_editor.insert(tk.END, text_to_type)
            self.global_typoer(text_to_type, wpm, accuracy)
            
            if self.stop_typing.is_set():
                break
            
            self.current_item_index += 1
            self.is_paused.set()  # Pause at the end of each item

    def global_typoer(self, text, wpm, accuracy):
        chars_per_minute = wpm * 5
        interval = 60.0 / chars_per_minute
        correction_interval = interval / 2

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
                    return

                while self.is_paused.is_set():
                    if self.stop_typing.is_set():
                        return
                    continue

                if random.random() > accuracy and i < len(line.strip()) - 1:
                    wrong_char = random.choice('abcdefghijklmnopqrstuvwxyz')
                    pyautogui.typewrite(wrong_char, interval=interval)
                    pyautogui.press('backspace', interval=correction_interval)
                    pyautogui.typewrite(char, interval=correction_interval)
                else:
                    pyautogui.typewrite(char, interval=interval)
            
            if line != lines[-1]:
                pyautogui.press('enter', interval=interval)

    def on_press(self, key):
        if key == keyboard.Key.esc:
            self.stopAndReset()
        elif key == keyboard.Key.left:
            self.pauseTyping()
        elif key == keyboard.Key.right:
            if self.is_paused.is_set():
                self.is_paused.clear()
                if self.current_item_index < len(self.typing_items):
                    self.startTyping()
            else:
                self.startTyping()

    def on_closing(self):
        self.stop_typing.set()
        if self.typing_thread and self.typing_thread.is_alive():
            self.typing_thread.join()
        if self.listener and self.listener.running:
            self.listener.stop()
        self.destroy()

if __name__ == '__main__':
    app = TypingSimulatorApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()