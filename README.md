# Typing Simulator Application

This is a Python application that simulates typing using the `tkinter` library for the GUI and `pyautogui` for typing automation. The application allows users to input text, set typing speed (WPM), and accuracy. It also includes features like pausing, resuming, and clearing the typing process.

## Features

- **Typing Simulation**: Simulate typing with customizable WPM and accuracy.
- **Sidebar Menu**: Add, remove, and select text items for typing.
- **Fullscreen Mode**: Toggle fullscreen mode with F11 and exit with Escape.
- **Keyboard Shortcuts**: ESC to clear, Left Arrow to pause, Right Arrow to start/continue.
- **Dark Theme**: Uses `ttkbootstrap` for a dark theme.

## Installation

### Prerequisites

- Python 3.x

### Dependencies

- `tkinter`
- `pyautogui`
- `pynput`
- `ttkbootstrap`

You can install the required dependencies using pip:

```sh
pip install pyautogui pynput ttkbootstrap
```
# Typing Simulator Application

## Usage

### Running the Application

1. Clone the repository or download the script.
2. Navigate to the directory containing the script.
3. Run the script using Python:

# Typing Simulator Application

## Usage

### Running the Application

1. Clone the repository or download the script.
2. Navigate to the directory containing the script.
3. Run the script using Python:

```sh
python typing_simulator.py
```

# Typing Simulator Application

## Usage

### Keyboard Shortcuts

- **F11**: Toggle fullscreen mode.
- **Escape**: Exit fullscreen mode.
- **ESC**: Clear the typing process.
- **Left Arrow**: Pause the typing process.
- **Right Arrow**: Start/continue the typing process.

### Adding and Managing Text Items

- **Add Item**: Enter the text in the text editor, set the WPM and accuracy, and click "Add Item".
- **Remove Item**: Select an item from the list and click "Remove".
- **Select Item**: Click on an item in the list to load it into the text editor.

### Typing Simulation

- **Start Typing**: Click the "Start" button to begin the typing simulation.
- **Pause Typing**: Click the "Pause" button or press the Left Arrow key to pause the typing process.
- **Clear**: Click the "Clear" button or press the ESC key to stop and reset the typing process.

## Code Overview

The main components of the application are:

- **TypingSimulatorApp Class**: The main application class that initializes the GUI and handles user interactions.
- **create_widgets**: Method to create the main and sidebar frames.
- **create_main_content**: Method to create the main content area with input fields and buttons.
- **create_sidebar_content**: Method to create the sidebar with the item list and buttons.
- **toggle_sidebar**: Method to toggle the visibility of the sidebar.
- **toggle_fullscreen**: Method to toggle fullscreen mode.
- **end_fullscreen**: Method to exit fullscreen mode.
- **on_item_select**: Method to handle item selection from the list.
- **add_item**: Method to add a new item to the list.
- **remove_item**: Method to remove the selected item from the list.
- **startTyping**: Method to start the typing process.
- **pauseTyping**: Method to pause the typing process.
- **stopAndReset**: Method to stop and reset the typing process.
- **typingProcess**: Method to handle the typing process.
- **global_typoer**: Method to simulate typing with the specified WPM and accuracy.
- **on_press**: Method to handle keyboard shortcuts.
- **on_closing**: Method to handle the application closing event.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request if you have any suggestions or improvements.

## License

This project is licensed under the MIT License.

---

Feel free to reach out if you have any questions or need further assistance!

