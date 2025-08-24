import sys
import os
import json
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
import subprocess
from datetime import datetime
import webbrowser
import winsound
import threading

# Pillow is used for image manipulation
try:
    from PIL import Image, ImageTk, ImageDraw, __version__ as PILLOW_VERSION
    Resampling = Image.Resampling
except AttributeError:
    # For older versions of Pillow
    Resampling = Image

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))

    return os.path.join(base_path, relative_path)

def app_path():
    """Return the directory containing the running script or executable."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.dirname(__file__))

class ToolTip:
    """ Creates a tooltip for a given widget. """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        if self.tip_window or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tooltip(self, event):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

class PixelPruner:
    def __init__(self, master):
        self.master = master
        self.master.title("MaskPruner - Mosaic Tool")

        self.showing_popup = False  # Flag to track if popup is already shown

        # --- Menu Bar ---
        self.menu_bar = tk.Menu(master)
        master.config(menu=self.menu_bar)

        # File Menu
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Set Input Folder", command=self.select_input_folder)
        self.file_menu.add_command(label="Set Output Folder", command=self.select_output_folder)
        self.file_menu.add_command(label="Open Current Input Folder", command=self.open_input_folder)
        self.file_menu.add_command(label="Open Current Output Folder", command=self.open_output_folder)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=master.quit)

        # Settings Menu
        self.settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Settings", menu=self.settings_menu)
        self.auto_advance_var = tk.BooleanVar(value=True)
        self.crop_sound_var = tk.BooleanVar(value=True)
        self.safe_mode_var = tk.BooleanVar(value=False)
        self.default_input_folder = ""
        self.default_output_folder = ""
        self.settings_menu.add_checkbutton(label="Auto-advance", variable=self.auto_advance_var, command=self.save_settings)
        self.settings_menu.add_checkbutton(label="Modification Sound", variable=self.crop_sound_var, command=self.save_settings)
        # Help Menu
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Help", menu=self.help_menu)
        self.help_menu.add_command(label="About", command=self.show_about)

        # --- Control Frame ---
        control_frame = tk.Frame(master)
        control_frame.pack(fill=tk.X, side=tk.TOP, pady=5)

        tk.Label(control_frame, text="Use Mouse Wheel to change selection size.").pack(side=tk.LEFT, padx=(10, 20))

        self.prev_button = tk.Button(control_frame, text="< Prev", command=self.load_previous_image)
        self.prev_button.pack(side=tk.LEFT, padx=(10, 2))
        ToolTip(self.prev_button, "Load the previous image (S)")

        self.next_button = tk.Button(control_frame, text="Next >", command=self.load_next_image)
        self.next_button.pack(side=tk.LEFT, padx=(10, 2))
        ToolTip(self.next_button, "Load the next image (W)")

        # Load icons for buttons
        try:
            self.rotate_left_image = tk.PhotoImage(file=resource_path("rotate_left.png"))
            self.rotate_right_image = tk.PhotoImage(file=resource_path("rotate_right.png"))
            self.delete_image = tk.PhotoImage(file=resource_path("delete_image.png"))
            self.input_folder_icon = tk.PhotoImage(file=resource_path("input_folder.png"))
            self.output_folder_icon = tk.PhotoImage(file=resource_path("output_folder.png"))
            self.open_output_folder_icon = tk.PhotoImage(file=resource_path("open_folder.png"))
        except Exception as e:
            print(f"Error loading icon images: {e}")
            # Create placeholder images if loading fails
            self.rotate_left_image = self.rotate_right_image = self.delete_image = tk.PhotoImage()
            self.input_folder_icon = self.output_folder_icon = self.open_output_folder_icon = tk.PhotoImage()

        self.rotate_left_button = tk.Button(control_frame, image=self.rotate_left_image, command=lambda: self.rotate_image(90))
        self.rotate_left_button.pack(side=tk.LEFT, padx=(10, 2))
        ToolTip(self.rotate_left_button, "Rotate image counterclockwise (A)")

        self.rotate_right_button = tk.Button(control_frame, image=self.rotate_right_image, command=lambda: self.rotate_image(-90))
        self.rotate_right_button.pack(side=tk.LEFT, padx=(10, 2))
        ToolTip(self.rotate_right_button, "Rotate image clockwise (D)")

        self.delete_button = tk.Button(control_frame, image=self.delete_image, command=self.delete_current_image)
        self.delete_button.pack(side=tk.LEFT, padx=(10, 2))
        ToolTip(self.delete_button, "Delete the current image (Delete)")

        self.input_folder_button = tk.Button(control_frame, image=self.input_folder_icon, command=self.select_input_folder)
        self.input_folder_button.pack(side=tk.LEFT, padx=(10, 2))
        ToolTip(self.input_folder_button, "Set the input folder")

        self.output_folder_button = tk.Button(control_frame, image=self.output_folder_icon, command=self.select_output_folder)
        self.output_folder_button.pack(side=tk.LEFT, padx=(10, 2))
        ToolTip(self.output_folder_button, "Set the output folder")

        self.open_output_button = tk.Button(control_frame, image=self.open_output_folder_icon, command=self.open_output_folder)
        self.open_output_button.pack(side=tk.LEFT, padx=(10, 2))
        ToolTip(self.open_output_button, "Open the current output folder")

        self.image_counter_label = tk.Label(control_frame, text="Viewing 0 of 0")
        self.image_counter_label.pack(side=tk.RIGHT, padx=(10, 20))

        # --- Main Frame & Canvas ---
        self.main_frame = tk.Frame(master)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.main_frame, cursor="cross", bg="gray")
        self.canvas.pack(side=tk.LEFT, fill="both", expand=True)

        # --- Status Bar ---
        self.status_bar = tk.Frame(master, bd=1, relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_label = tk.Label(self.status_bar, text="Welcome to MaskPruner - Mosaic Tool", anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, padx=10)
        self.modified_images_label = tk.Label(self.status_bar, text="Images Modified: 0", anchor=tk.E)
        self.modified_images_label.pack(side=tk.RIGHT, padx=10)

        # --- Instance Variables ---
        self.folder_path = None
        self.images = []
        self.image_index = 0
        self.current_image = None
        self.image_scale = 1
        self.selection_oval = None
        self.image_offset_x = 0
        self.image_offset_y = 0
        self.output_folder = None
        self.selection_radius = 256  # Default radius in pixels of the original image
        self.modification_counter = 0

        # Enable drag-and-drop for the main frame
        self.main_frame.drop_target_register(DND_FILES)
        self.main_frame.dnd_bind('<<Drop>>', self.on_drop)

        self.master.update_idletasks()
        self.canvas.update_idletasks()

        # --- Bindings ---
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.last_state = self.master.state()
        self.master.bind("<Configure>", self.on_window_resize)
        self.master.minsize(1000, 700)
        self.master.bind("w", lambda event: self.load_next_image())
        self.master.bind("s", lambda event: self.load_previous_image())
        self.master.bind("a", lambda event: self.rotate_image(90))
        self.master.bind("d", lambda event: self.rotate_image(-90))
        self.master.bind("<Delete>", lambda event: self.delete_current_image())
        master.focus_set()

        # --- Initialization ---
        self.load_settings()
        self.update_safe_mode_ui()
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)
        self.center_window()
        
        self.load_images_from_folder()


    def center_window(self):
        """Centers the main window on the screen."""
        self.master.update_idletasks()
        window_width = self.master.winfo_width()
        window_height = self.master.winfo_height()
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.master.geometry(f'{window_width}x{window_height}+{x}+{y}')

    def update_status(self, message):
        self.status_label.config(text=message)

    def update_image_counter(self):
        self.image_counter_label.config(text=f"Viewing {self.image_index + 1} of {len(self.images)}")

    def update_modified_images_counter(self):
        self.modified_images_label.config(text=f"Images Modified: {self.modification_counter}")

    def show_info_message(self, title, message):
        if not self.showing_popup:
            self.showing_popup = True
            messagebox.showinfo(title, message)
            self.showing_popup = False

    def update_safe_mode_ui(self):
        """Enable or disable delete-related widgets based on safe mode."""
        state = tk.DISABLED if self.safe_mode_var.get() else tk.NORMAL
        self.delete_button.config(state=state)

    def on_window_resize(self, event):
        """Redraw the image when the window is resized or state changes."""
        if event.widget is self.master and self.current_image:
            state = self.master.state()
            if state != self.last_state or event.width != self.canvas.winfo_width() or event.height != self.canvas.winfo_height():
                self.last_state = state
                self.display_image()

    def load_image(self):
        """Loads the current image based on self.image_index."""
        if not self.folder_path and not self.images:
            self.show_info_message("Information", "Please select an input folder.")
            return
        if 0 <= self.image_index < len(self.images):
            try:
                image_path = self.images[self.image_index]
                self.current_image = Image.open(image_path)
                self.display_image()
            except IOError:
                messagebox.showerror("Error", f"Failed to load image: {image_path}")
                return

    def display_image(self):
        """Displays the current image on the canvas, scaled to fit."""
        aspect_ratio = self.current_image.width / self.current_image.height
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        # Scale image to fit canvas
        if self.current_image.width / canvas_w > self.current_image.height / canvas_h:
            self.scaled_width = canvas_w
            self.scaled_height = int(self.scaled_width / aspect_ratio)
        else:
            self.scaled_height = canvas_h
            self.scaled_width = int(self.scaled_height * aspect_ratio)

        self.tkimage = ImageTk.PhotoImage(self.current_image.resize((self.scaled_width, self.scaled_height), Resampling.LANCZOS))

        # Center the image
        self.image_offset_x = (canvas_w - self.scaled_width) // 2
        self.image_offset_y = (canvas_h - self.scaled_height) // 2

        self.canvas.delete("all")
        self.canvas.create_image(self.image_offset_x, self.image_offset_y, anchor="nw", image=self.tkimage)
        self.image_scale = self.current_image.width / self.scaled_width

        # Create the circular selection tool
        scaled_radius = self.selection_radius / self.image_scale
        x, y = self.image_offset_x + scaled_radius, self.image_offset_y + scaled_radius
        self.selection_oval = self.canvas.create_oval(x - scaled_radius, y - scaled_radius, x + scaled_radius, y + scaled_radius, outline='red', width=2)
        
        self.update_image_counter()

    def rotate_image(self, angle):
        """Rotates the current image."""
        if not self.current_image:
            self.show_info_message("Information", "Please load an image first.")
            return
        self.current_image = self.current_image.rotate(angle, expand=True)
        self.display_image()
        self.update_status(f"Image rotated by {angle} degrees")

    def on_mouse_move(self, event):
        """Moves the selection oval with the mouse cursor."""
        if self.selection_oval:
            scaled_radius = self.selection_radius / self.image_scale
            
            # Clamp the center of the oval to be within the image boundaries
            x = max(self.image_offset_x + scaled_radius, min(event.x, self.image_offset_x + self.scaled_width - scaled_radius))
            y = max(self.image_offset_y + scaled_radius, min(event.y, self.image_offset_y + self.scaled_height - scaled_radius))
            
            self.canvas.coords(self.selection_oval, x - scaled_radius, y - scaled_radius, x + scaled_radius, y + scaled_radius)

    def on_button_release(self, event):
        """Triggers the blackout process on mouse click release."""
        self.apply_modification()

    def on_mouse_wheel(self, event):
        """Adjusts the size of the selection oval."""
        if self.selection_oval:
            # Adjust radius based on scroll direction
            increment = 20 * (event.delta / 120)
            new_radius = self.selection_radius + increment
            
            # Set min/max radius
            min_radius = 20
            max_radius_on_image = min(self.current_image.width, self.current_image.height) / 2
            self.selection_radius = max(min_radius, min(new_radius, max_radius_on_image))
            
            # Redraw the oval with the new size
            coords = self.canvas.coords(self.selection_oval)
            cx = (coords[0] + coords[2]) / 2
            cy = (coords[1] + coords[3]) / 2
            scaled_radius = self.selection_radius / self.image_scale
            self.canvas.coords(self.selection_oval, cx - scaled_radius, cy - scaled_radius, cx + scaled_radius, cy + scaled_radius)

    def apply_modification(self):
        """Applies a black circle to the selected area of the image."""
        if not self.current_image:
            self.show_info_message("Information", "Please load an image first.")
            return

        # Ensure output folder is set
        if not self.output_folder:
            self.select_output_folder()
            if not self.output_folder:
                self.show_info_message("Information", "Output folder not set. Cannot save modified image.")
                return

        # Get oval coordinates from canvas
        oval_coords = self.canvas.coords(self.selection_oval)

        # Convert canvas coordinates to original image coordinates
        real_x1 = (oval_coords[0] - self.image_offset_x) * self.image_scale
        real_y1 = (oval_coords[1] - self.image_offset_y) * self.image_scale
        real_x2 = (oval_coords[2] - self.image_offset_x) * self.image_scale
        real_y2 = (oval_coords[3] - self.image_offset_y) * self.image_scale

        # Create a copy of the image to modify
        modified_image = self.current_image.copy().convert("RGBA")
        
        # Create a drawing context
        draw = ImageDraw.Draw(modified_image)
        
        # Draw the black ellipse
        draw.ellipse([real_x1, real_y1, real_x2, real_y2], fill=(0, 0, 0, 255))

        # Generate a unique filename
        self.modification_counter += 1
        image_path = self.images[self.image_index]
        base_filename = os.path.basename(image_path)
        filename, ext = os.path.splitext(base_filename)
        modified_filename = f"{filename}.png"
        modified_filepath = os.path.join(self.output_folder, modified_filename)
        
        # Save the modified image
        modified_image.save(modified_filepath, "PNG")
        self.update_modified_images_counter()
        
        # Play sound if enabled
        if self.crop_sound_var.get():
            winsound.PlaySound(resource_path("click.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC)

        self.update_status(f"Saved modified image to {os.path.normpath(modified_filepath)}")

        # Auto-advance to the next image if enabled
        if self.auto_advance_var.get():
            self.load_next_image()

    def load_next_image(self):
        if not self.images:
            self.show_info_message("Information", "No images loaded.")
            return
        self.image_index = (self.image_index + 1) % len(self.images)
        self.load_image()

    def load_previous_image(self):
        if not self.images:
            self.show_info_message("Information", "No images loaded.")
            return
        self.image_index = (self.image_index - 1 + len(self.images)) % len(self.images)
        self.load_image()

    def select_input_folder(self):
        selected_folder = filedialog.askdirectory(title="Select Input Folder", initialdir=self.default_input_folder or None)
        if selected_folder:
            self.folder_path = selected_folder
            self.default_input_folder = selected_folder
            self.load_images_from_folder()
        else:
            self.update_status("Input folder selection cancelled.")

    def select_output_folder(self):
        selected_folder = filedialog.askdirectory(title="Select Output Folder", initialdir=self.default_output_folder or None)
        if selected_folder:
            self.output_folder = selected_folder
            self.default_output_folder = selected_folder
            self.update_status(f"Output folder set to: {selected_folder}")
        else:
            self.update_status("Output folder selection cancelled.")

    def open_input_folder(self):
        if self.folder_path and os.path.isdir(self.folder_path):
            subprocess.Popen(['explorer', os.path.normpath(self.folder_path)])
        else:
            self.show_info_message("Information", "Input folder is not set or does not exist.")

    def open_output_folder(self):
        if self.output_folder and os.path.isdir(self.output_folder):
            subprocess.Popen(['explorer', os.path.normpath(self.output_folder)])
        else:
            self.show_info_message("Information", "Output folder is not set or does not exist.")

    def load_images_from_folder(self):
        """Loads all valid image files from the selected folder."""
        if not self.folder_path:
            return
        self.images = [os.path.join(self.folder_path, f) for f in os.listdir(self.folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        if not self.images:
            messagebox.showerror("Error", "No valid images found in the selected directory.")
            return
        self.image_index = 0
        self.load_image()
        self.update_status(f"Loaded {len(self.images)} images from {self.folder_path}")

    def load_images_from_list(self, file_list):
        """Loads images from a list of file paths (e.g., from drag-and-drop)."""
        self.images = [f for f in file_list if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        if not self.images:
            messagebox.showerror("Error", "No valid images found in the dropped files.")
            return
        self.folder_path = os.path.dirname(self.images[0]) # Set folder path from first image
        self.image_index = 0
        self.load_image()
        self.update_status(f"Loaded {len(self.images)} images from dropped files")

    def on_drop(self, event):
        """Handles file drop events."""
        file_list = self.master.tk.splitlist(event.data)
        self.load_images_from_list(file_list)

    def delete_current_image(self):
        """Deletes the currently viewed image from the disk."""
        if self.safe_mode_var.get():
            self.show_info_message("Safe Mode", "Safe Mode is enabled. Delete operations are disabled.")
            return
        if not self.images:
            return
        if messagebox.askyesno("Delete Image", "Are you sure you want to permanently delete this image?"):
            image_path = self.images.pop(self.image_index)
            try:
                os.remove(image_path)
                self.update_status(f"Deleted image: {os.path.basename(image_path)}")
            except OSError as e:
                messagebox.showerror("Error", f"Could not delete file: {e}")
                self.images.insert(self.image_index, image_path) # Add it back if delete fails
                return
            
            if not self.images:
                self.canvas.delete("all")
                self.current_image = None
                self.update_image_counter()
            else:
                if self.image_index >= len(self.images):
                    self.image_index = 0
                self.load_image()

    def show_about(self):
        about_text = (
            "MaskPruner - Mosaic Tool\n\n"
            "Modified version of PixelPruner.\n"
            "Original by TheAlly and GPT4o.\n\n"
            "This version applies a circular black area to images."
        )
        messagebox.showinfo("About", about_text)

    def load_settings(self):
        """Loads user settings from a JSON file."""
        self.settings_path = os.path.join(app_path(), "usersettings.json")
        defaults = {
            "auto_advance": True, "crop_sound": True,
            "safe_mode": False, "default_input_folder": "", "default_output_folder": ""
        }
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r") as f:
                    self.settings = json.load(f)
            else:
                self.settings = defaults
        except (json.JSONDecodeError, IOError):
            self.settings = defaults

        self.auto_advance_var.set(self.settings.get("auto_advance", True))
        self.crop_sound_var.set(self.settings.get("crop_sound", True))
        self.safe_mode_var.set(self.settings.get("safe_mode", False))
        self.default_input_folder = self.settings.get("default_input_folder", "")
        self.default_output_folder = self.settings.get("default_output_folder", "")
        self.folder_path = self.default_input_folder
        self.output_folder = self.default_output_folder

    def save_settings(self):
        """Saves current settings to a JSON file."""
        self.settings = {
            "auto_advance": self.auto_advance_var.get(),
            "crop_sound": self.crop_sound_var.get(),
            "safe_mode": self.safe_mode_var.get(),
            "default_input_folder": self.default_input_folder,
            "default_output_folder": self.default_output_folder,
        }
        try:
            with open(self.settings_path, "w") as f:
                json.dump(self.settings, f, indent=4)
        except IOError as e:
            print(f"Failed to save settings: {e}")

    def on_close(self):
        """Handles application close event."""
        self.save_settings()
        self.master.destroy()

def main():
    root = TkinterDnD.Tk()
    app = PixelPruner(root)
    root.mainloop()

if __name__ == "__main__":
    main()