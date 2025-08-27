import sys
import os
import json
import tkinter as tk
from tkinter import filedialog, ttk, messagebox, colorchooser
from tkinterdnd2 import TkinterDnD, DND_FILES
import subprocess
import winsound

# Pillow is used for image manipulation
try:
    from PIL import Image, ImageTk, ImageDraw, ImageFilter, __version__ as PILLOW_VERSION
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

class MaskPruner:
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
        self.file_menu.add_command(label="Save Current Settings as Default", command=self.save_settings_with_feedback)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=master.quit)

        # Settings Menu
        self.settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Settings", menu=self.settings_menu)
        self.auto_advance_var = tk.BooleanVar(value=False) # Default set to False
        self.crop_sound_var = tk.BooleanVar(value=True)
        self.settings_menu.add_checkbutton(label="Auto-advance", variable=self.auto_advance_var, command=self.save_settings)
        self.settings_menu.add_checkbutton(label="Modification Sound", variable=self.crop_sound_var, command=self.save_settings)
        
        # Help Menu
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Help", menu=self.help_menu)
        self.help_menu.add_command(label="About", command=self.show_about)

        # --- Control Frame ---
        control_frame = tk.Frame(master)
        control_frame.pack(fill=tk.X, side=tk.TOP, pady=5)

        tk.Label(control_frame, text="Mouse Wheel: Change selection size.").pack(side=tk.LEFT, padx=(10, 5))

        self.prev_button = tk.Button(control_frame, text="< Prev", command=self.load_previous_image)
        self.prev_button.pack(side=tk.LEFT, padx=(5, 2))
        ToolTip(self.prev_button, "Load the previous image (S)")

        self.next_button = tk.Button(control_frame, text="Next >", command=self.load_next_image)
        self.next_button.pack(side=tk.LEFT, padx=(2, 10))
        ToolTip(self.next_button, "Load the next image (W)")

        # Load icons for buttons
        try:
            self.rotate_left_image = tk.PhotoImage(file=resource_path("rotate_left.png"))
            self.rotate_right_image = tk.PhotoImage(file=resource_path("rotate_right.png"))
            self.input_folder_icon = tk.PhotoImage(file=resource_path("input_folder.png"))
            self.output_folder_icon = tk.PhotoImage(file=resource_path("output_folder.png"))
            self.open_folder_icon = tk.PhotoImage(file=resource_path("open_folder.png"))
        except Exception as e:
            print(f"Error loading icon images: {e}")
            # Create placeholder images if loading fails
            self.rotate_left_image = self.rotate_right_image = tk.PhotoImage()
            self.input_folder_icon = self.output_folder_icon = self.open_folder_icon = tk.PhotoImage()

        self.rotate_left_button = tk.Button(control_frame, image=self.rotate_left_image, command=lambda: self.rotate_image(90))
        self.rotate_left_button.pack(side=tk.LEFT, padx=(10, 2))
        ToolTip(self.rotate_left_button, "Rotate image counterclockwise (A)")

        self.rotate_right_button = tk.Button(control_frame, image=self.rotate_right_image, command=lambda: self.rotate_image(-90))
        self.rotate_right_button.pack(side=tk.LEFT, padx=(2, 10))
        ToolTip(self.rotate_right_button, "Rotate image clockwise (D)")

        self.input_folder_button = tk.Button(control_frame, image=self.input_folder_icon, command=self.select_input_folder)
        self.input_folder_button.pack(side=tk.LEFT, padx=(20, 2))
        ToolTip(self.input_folder_button, "Set the input folder")
        
        self.open_input_button = tk.Button(control_frame, image=self.open_folder_icon, command=self.open_input_folder)
        self.open_input_button.pack(side=tk.LEFT, padx=(2, 10))
        ToolTip(self.open_input_button, "Open the current input folder")

        self.output_folder_button = tk.Button(control_frame, image=self.output_folder_icon, command=self.select_output_folder)
        self.output_folder_button.pack(side=tk.LEFT, padx=(10, 2))
        ToolTip(self.output_folder_button, "Set the output folder")

        self.open_output_button = tk.Button(control_frame, image=self.open_folder_icon, command=self.open_output_folder)
        self.open_output_button.pack(side=tk.LEFT, padx=(2, 10))
        ToolTip(self.open_output_button, "Open the current output folder")

        # --- Masking Controls ---
        mask_frame = tk.Frame(control_frame)
        mask_frame.pack(side=tk.LEFT, padx=(20, 5))
        
        tk.Label(mask_frame, text="Mask Type:").pack(side=tk.LEFT)
        self.mask_type_var = tk.StringVar(value="Color")
        self.mask_type_combo = ttk.Combobox(mask_frame, textvariable=self.mask_type_var, values=["Color", "Mosaic"], width=8)
        self.mask_type_combo.pack(side=tk.LEFT, padx=5)
        self.mask_type_combo.bind("<<ComboboxSelected>>", self.update_mask_controls)

        self.color_button = tk.Button(mask_frame, text="Choose Color", command=self.choose_color)
        self.color_button.pack(side=tk.LEFT, padx=5)
        self.color_swatch = tk.Label(mask_frame, bg="#000000", width=2, relief="sunken")
        self.color_swatch.pack(side=tk.LEFT)
        self.mask_color = "#000000"

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
        self.output_folder = None
        self.images = []
        self.image_index = 0
        self.current_image = None
        self.modified_image = None # This will hold the image with masks applied
        self.is_modified = False # Flag to track if the current image has been modified
        self.image_scale = 1
        self.selection_oval = None
        self.image_offset_x = 0
        self.image_offset_y = 0
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
        master.focus_set()

        # --- Initialization ---
        self.load_settings()
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)
        self.center_window()

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
        if not self.images:
            self.image_counter_label.config(text="Viewing 0 of 0")
        else:
            self.image_counter_label.config(text=f"Viewing {self.image_index + 1} of {len(self.images)}")

    def update_modified_images_counter(self):
        self.modified_images_label.config(text=f"Images Modified: {self.modification_counter}")

    def show_info_message(self, title, message):
        if not self.showing_popup:
            self.showing_popup = True
            messagebox.showinfo(title, message)
            self.showing_popup = False

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
                # Reset modification state for the new image
                self.modified_image = None
                self.is_modified = False
                self.display_image()
                self.update_status(f"Loaded: {os.path.basename(image_path)}")
            except IOError:
                messagebox.showerror("Error", f"Failed to load image: {image_path}")
                return

    def display_image(self):
        """Displays the current or modified image on the canvas, scaled to fit."""
        image_to_display = self.modified_image if self.is_modified else self.current_image
        if not image_to_display:
            return

        aspect_ratio = image_to_display.width / image_to_display.height
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        if image_to_display.width / canvas_w > image_to_display.height / canvas_h:
            self.scaled_width = canvas_w
            self.scaled_height = int(self.scaled_width / aspect_ratio)
        else:
            self.scaled_height = canvas_h
            self.scaled_width = int(self.scaled_height * aspect_ratio)

        self.tkimage = ImageTk.PhotoImage(image_to_display.resize((self.scaled_width, self.scaled_height), Resampling.LANCZOS))

        self.image_offset_x = (canvas_w - self.scaled_width) // 2
        self.image_offset_y = (canvas_h - self.scaled_height) // 2

        self.canvas.delete("all")
        self.canvas.create_image(self.image_offset_x, self.image_offset_y, anchor="nw", image=self.tkimage)
        self.image_scale = self.current_image.width / self.scaled_width

        scaled_radius = self.selection_radius / self.image_scale
        x, y = self.master.winfo_pointerx() - self.master.winfo_rootx(), self.master.winfo_pointery() - self.master.winfo_rooty()
        self.selection_oval = self.canvas.create_oval(x - scaled_radius, y - scaled_radius, x + scaled_radius, y + scaled_radius, outline='red', width=2)
        
        self.update_image_counter()

    def rotate_image(self, angle):
        """Rotates the current image."""
        if not self.current_image:
            self.show_info_message("Information", "Please load an image first.")
            return
        
        self.current_image = self.current_image.rotate(angle, expand=True)
        if self.is_modified:
            self.modified_image = self.modified_image.rotate(angle, expand=True)

        self.display_image()
        self.update_status(f"Image rotated by {angle} degrees")

    def on_mouse_move(self, event):
        """Moves the selection oval with the mouse cursor."""
        if self.selection_oval:
            scaled_radius = self.selection_radius / self.image_scale
            
            min_x = self.image_offset_x + scaled_radius
            max_x = self.image_offset_x + self.scaled_width - scaled_radius
            min_y = self.image_offset_y + scaled_radius
            max_y = self.image_offset_y + self.scaled_height - scaled_radius
            
            x = max(min_x, min(event.x, max_x))
            y = max(min_y, min(event.y, max_y))
            
            self.canvas.coords(self.selection_oval, x - scaled_radius, y - scaled_radius, x + scaled_radius, y + scaled_radius)

    def on_button_release(self, event):
        """Triggers the masking process on mouse click release."""
        self.apply_modification()

    def on_mouse_wheel(self, event):
        """Adjusts the size of the selection oval."""
        if self.selection_oval and self.current_image:
            increment = 20 * (event.delta / 120)
            new_radius = self.selection_radius + increment
            
            min_radius = 20
            max_radius_on_image = min(self.current_image.width, self.current_image.height) / 2
            self.selection_radius = max(min_radius, min(new_radius, max_radius_on_image))
            
            coords = self.canvas.coords(self.selection_oval)
            cx = (coords[0] + coords[2]) / 2
            cy = (coords[1] + coords[3]) / 2
            scaled_radius = self.selection_radius / self.image_scale
            self.canvas.coords(self.selection_oval, cx - scaled_radius, cy - scaled_radius, cx + scaled_radius, cy + scaled_radius)

    def apply_modification(self):
        """Applies the selected mask to the in-memory image."""
        if not self.current_image:
            self.show_info_message("Information", "Please load an image first.")
            return

        if not self.is_modified:
            self.modified_image = self.current_image.copy().convert("RGBA")
            self.is_modified = True

        oval_coords = self.canvas.coords(self.selection_oval)

        real_x1 = (oval_coords[0] - self.image_offset_x) * self.image_scale
        real_y1 = (oval_coords[1] - self.image_offset_y) * self.image_scale
        real_x2 = (oval_coords[2] - self.image_offset_x) * self.image_scale
        real_y2 = (oval_coords[3] - self.image_offset_y) * self.image_scale
        
        mask_type = self.mask_type_var.get()
        
        if mask_type == "Color":
            draw = ImageDraw.Draw(self.modified_image)
            draw.ellipse([real_x1, real_y1, real_x2, real_y2], fill=self.mask_color)
        elif mask_type == "Mosaic":
            box = (int(real_x1), int(real_y1), int(real_x2), int(real_y2))
            region = self.current_image.crop(box)

            pixel_size = 16 
            small_region = region.resize(
                (max(1, region.width // pixel_size), max(1, region.height // pixel_size)),
                Resampling.NEAREST
            )
            mosaic_region = small_region.resize(region.size, Resampling.NEAREST)

            mask = Image.new('L', region.size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, region.width, region.height), fill=255)

            self.modified_image.paste(mosaic_region, box, mask)

        if self.crop_sound_var.get():
            winsound.PlaySound(resource_path("click.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC)

        self.update_status("Mask applied. Click again to add more, or navigate to save.")
        self.display_image()

        if self.auto_advance_var.get():
            is_last_image = self.image_index >= len(self.images) - 1
            self.load_next_image()
            if is_last_image:
                self.show_info_message("End of Queue", "You have reached the last image and looped to the start.")

    def save_if_modified(self):
        """Saves the image to the output folder if it has been modified."""
        if not self.is_modified:
            return

        if not self.output_folder:
            self.select_output_folder()
            if not self.output_folder:
                self.show_info_message("Information", "Output folder not set. Cannot save modified image.")
                return

        self.modification_counter += 1
        image_path = self.images[self.image_index]
        base_filename = os.path.basename(image_path)
        filename, ext = os.path.splitext(base_filename)
        modified_filename = f"{filename}.png"
        modified_filepath = os.path.join(self.output_folder, modified_filename)
        
        try:
            self.modified_image.convert("RGB").save(modified_filepath, "PNG")
            self.update_modified_images_counter()
            self.update_status(f"Saved modified image to {os.path.normpath(modified_filepath)}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save the image:\n{e}")
        
        self.is_modified = False
        self.modified_image = None

    def load_next_image(self):
        if not self.images:
            self.show_info_message("Information", "No images loaded.")
            return
        self.save_if_modified()
        self.image_index = (self.image_index + 1) % len(self.images)
        self.load_image()

    def load_previous_image(self):
        if not self.images:
            self.show_info_message("Information", "No images loaded.")
            return
        self.save_if_modified()
        self.image_index = (self.image_index - 1 + len(self.images)) % len(self.images)
        self.load_image()

    def select_input_folder(self):
        selected_folder = filedialog.askdirectory(title="Select Input Folder", initialdir=self.folder_path or None)
        if selected_folder:
            self.folder_path = selected_folder
            self.load_images_from_folder()
        else:
            self.update_status("Input folder selection cancelled.")

    def select_output_folder(self):
        selected_folder = filedialog.askdirectory(title="Select Output Folder", initialdir=self.output_folder or None)
        if selected_folder:
            self.output_folder = selected_folder
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
        self.folder_path = os.path.dirname(self.images[0])
        self.image_index = 0
        self.load_image()
        self.update_status(f"Loaded {len(self.images)} images from dropped files")

    def on_drop(self, event):
        """Handles file drop events."""
        file_list = self.master.tk.splitlist(event.data)
        self.load_images_from_list(file_list)
    
    def choose_color(self):
        """Opens a color chooser dialog and sets the mask color."""
        color_code = colorchooser.askcolor(title="Choose mask color", initialcolor=self.mask_color)
        if color_code and color_code[1]:
            self.mask_color = color_code[1]
            self.color_swatch.config(bg=self.mask_color)

    def update_mask_controls(self, event=None):
        """Shows or hides the color chooser button based on mask type."""
        if self.mask_type_var.get() == "Color":
            self.color_button.pack(side=tk.LEFT, padx=5)
            self.color_swatch.pack(side=tk.LEFT)
        else:
            self.color_button.pack_forget()
            self.color_swatch.pack_forget()

    def show_about(self):
        about_text = (
            "MaskPruner - Mosaic Tool\n\n"
            "Modified version of PixelPruner.\n"
            "Original by TheAlly and GPT4o.\n\n"
            "This version applies a circular color or mosaic mask to images."
        )
        messagebox.showinfo("About", about_text)

    def load_settings(self):
        """Loads user settings from a JSON file."""
        self.settings_path = os.path.join(app_path(), "usersettings.json")
        defaults = {
            "auto_advance": False, "crop_sound": True,
            "input_folder": "", "output_folder": "",
            "mask_type": "Color", "mask_color": "#000000"
        }
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r") as f:
                    self.settings = json.load(f)
            else:
                self.settings = defaults
        except (json.JSONDecodeError, IOError):
            self.settings = defaults

        self.auto_advance_var.set(self.settings.get("auto_advance", False))
        self.crop_sound_var.set(self.settings.get("crop_sound", True))
        self.folder_path = self.settings.get("input_folder", "")
        self.output_folder = self.settings.get("output_folder", "")
        
        mask_type = self.settings.get("mask_type", "Color")
        self.mask_type_var.set(mask_type)
        self.mask_color = self.settings.get("mask_color", "#000000")
        self.color_swatch.config(bg=self.mask_color)
        self.update_mask_controls()

    def save_settings(self):
        """Saves current settings to a JSON file."""
        self.settings = {
            "auto_advance": self.auto_advance_var.get(),
            "crop_sound": self.crop_sound_var.get(),
            "input_folder": self.folder_path or "",
            "output_folder": self.output_folder or "",
            "mask_type": self.mask_type_var.get(),
            "mask_color": self.mask_color,
        }
        try:
            with open(self.settings_path, "w") as f:
                json.dump(self.settings, f, indent=4)
        except IOError as e:
            print(f"Failed to save settings: {e}")

    def save_settings_with_feedback(self):
        """Saves settings and provides user feedback."""
        self.save_settings()
        self.update_status("Settings saved as default.")

    def on_close(self):
        """Handles application close event."""
        self.save_if_modified()
        self.save_settings()
        self.master.destroy()

def main():
    root = TkinterDnD.Tk()
    app = MaskPruner(root)
    root.mainloop()

if __name__ == "__main__":
    main()
