import os
import glob
import trimesh
import numpy as np
from PIL import Image, ImageOps
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import UnityPy
import tempfile

def reconstruct_unity_normal(img):
    """
    Converts Unity's packed DXT5nm (pink/green) normal maps to standard RGB (blue) normals.
    Unity stores X in Alpha and Y in Green for better compression.
    """
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    data = np.array(img).astype(float) / 255.0
    
    # Unity standard: X is in Alpha (idx 3), Y is in Green (idx 1)
    x = data[:,:,3] * 2.0 - 1.0
    y = data[:,:,1] * 2.0 - 1.0
    
    # Calculate Z: sqrt(1 - x^2 - y^2)
    z = np.sqrt(np.clip(1.0 - (x**2 + y**2), 0, 1))
    
    # Pack back into standard RGB (Blue-tinted)
    new_r = ((x + 1.0) / 2.0 * 255).astype(np.uint8)
    new_g = ((y + 1.0) / 2.0 * 255).astype(np.uint8)
    new_b = ((z + 1.0) / 2.0 * 255).astype(np.uint8)
    
    return Image.fromarray(np.stack([new_r, new_g, new_b], axis=2), 'RGB')

def process_metal_roughness(img):
    """
    Converts Unity Metallic/Smoothness to GLB Metallic/Roughness.
    Unity: Metallic (R) + Smoothness (A)
    GLB: Metallic (B) + Roughness (G) where Roughness = 1.0 - Smoothness
    """
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    r, g, b, a = img.split()
    
    # GLB PBR expects Metallic in Blue and Roughness in Green
    metallic = r
    roughness = ImageOps.invert(a)
    
    # Create the combined map (Red is usually unused in GLB OcclusionRoughnessMetallic)
    empty = Image.new('L', img.size, 0)
    return Image.merge('RGB', (empty, roughness, metallic))

def process_unity_to_glb(input_file, log_callback):
    def log(message):
        print(message)
        log_callback(message + "\n")

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    output_dir = os.path.dirname(input_file)
    final_output_path = os.path.join(output_dir, f"{base_name}.glb")

    # Use a temporary directory to store the raw extraction
    with tempfile.TemporaryDirectory() as temp_dir:
        # ==========================================
        # PHASE 1: EXTRACTION
        # ==========================================
        log(f"Loading Unity file: {os.path.basename(input_file)}...")
        try:
            env = UnityPy.load(input_file)
            
            # Map Container Paths to Object IDs for robust naming
            container_names = {}
            for path, obj in env.container.items():
                clean_name = os.path.splitext(os.path.basename(path))[0]
                container_names[obj.path_id] = clean_name
                
            extracted_count = 0
            for obj in env.objects:
                if obj.type.name in ["Texture2D", "Mesh"]:
                    data = obj.read()
                    
                    # Name Resolution
                    name = container_names.get(obj.path_id)
                    if not name: name = getattr(data, "name", "")
                    if not name: name = getattr(data, "m_Name", "")
                    if not name: name = f"{obj.type.name}_{obj.path_id}"
                    name = name.replace('/', '_').replace('\\', '_').replace(':', '_')

                    if obj.type.name == "Texture2D":
                        data.image.save(os.path.join(temp_dir, f"{name}.png"))
                        extracted_count += 1
                        
                    elif obj.type.name == "Mesh":
                        with open(os.path.join(temp_dir, f"{name}.obj"), "w", encoding="utf-8") as f:
                            f.write(data.export())
                        extracted_count += 1
                        
            if extracted_count == 0:
                log("Error: No Texture2D or Mesh assets found in this file.")
                return
            log(f" -> Extracted {extracted_count} raw assets to temporary storage.")

        except Exception as e:
            log(f"Extraction failed: {e}")
            messagebox.showerror("Extraction Error", str(e))
            return

        # ==========================================
        # PHASE 2: GLB ASSEMBLY
        # ==========================================
        log("\nScanning extracted assets for GLB assembly...")

        mesh_files = glob.glob(os.path.join(temp_dir, "**/*.obj"), recursive=True)
        if not mesh_files:
            mesh_files = glob.glob(os.path.join(temp_dir, "**/*.fbx"), recursive=True)

        if not mesh_files:
            log("Error: No .obj or .fbx found after extraction.")
            return

        mesh_path = mesh_files[0]
        log(f" -> Mesh locked in.")

        png_files = glob.glob(os.path.join(temp_dir, "**/*.png"), recursive=True)
        tex_maps = {"diffuse": None, "normal": None, "metal": None, "emissive": None, "ao": None}

        for png in png_files:
            name = os.path.basename(png).lower()
            img = Image.open(png)
            
            if any(x in name for x in ["diffuse", "color", "albedo"]):
                tex_maps["diffuse"] = img.convert("RGB")
            elif "normal" in name:
                log(" -> Fixing Normal Map details...")
                tex_maps["normal"] = reconstruct_unity_normal(img)
            elif "metal" in name:
                log(" -> Converting Smoothness map...")
                tex_maps["metal"] = process_metal_roughness(img)
            elif "emissive" in name:
                tex_maps["emissive"] = img
            elif "occlusion" in name or "ao" in name:
                tex_maps["ao"] = img

        if not tex_maps["diffuse"]:
            log("Warning: No diffuse/color texture found. Model may be blank.")

        log("Assembling PBR model...")
        try:
            loaded = trimesh.load(mesh_path, process=False)
            if isinstance(loaded, trimesh.Scene):
                geoms = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
                mesh = trimesh.util.concatenate(geoms)
            else:
                mesh = loaded

            # Orientation fix
            mesh.apply_transform(trimesh.transformations.rotation_matrix(np.radians(-90), [1, 0, 0]))

            # Matte finish setup
            mat = trimesh.visual.material.PBRMaterial(
                baseColorTexture=tex_maps["diffuse"],
                normalTexture=tex_maps["normal"],
                metallicRoughnessTexture=tex_maps["metal"],
                emissiveTexture=tex_maps["emissive"],
                occlusionTexture=tex_maps["ao"],
                roughnessFactor=1.0, 
                metallicFactor=1.0 if tex_maps["metal"] else 0.1
            )
            
            mesh.visual = trimesh.visual.TextureVisuals(uv=mesh.visual.uv, material=mat)
            
            # Export to the final location next to the Unity file
            mesh.export(final_output_path, file_type='glb')
            
            log(f"\nSuccess! GLB saved as:\n{os.path.basename(final_output_path)}")
            messagebox.showinfo("Success", f"Converted successfully!\n\nFile saved to:\n{final_output_path}")

        except Exception as e:
            log(f"GLB Assembly failed: {e}")
            messagebox.showerror("Assembly Error", str(e))


class OneClickConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Unity3D to GLB Converter")
        self.root.geometry("520x400")
        self.root.configure(bg="#f0f0f0")
        
        self.input_file = tk.StringVar()

        # UI Styling
        title_font = ("Arial", 14, "bold")
        main_font = ("Arial", 10)
        
        tk.Label(root, text=".unity3d \u2192 .glb Converter", font=title_font, bg="#f0f0f0").pack(pady=20)
        
        frame = tk.LabelFrame(root, text=" Select Unity Asset File ", font=main_font, padx=10, pady=10, bg="#f0f0f0")
        frame.pack(fill="x", padx=20, pady=5)
        
        tk.Entry(frame, textvariable=self.input_file, state="readonly", width=42).pack(side="left", padx=5)
        tk.Button(frame, text="Browse", command=self.select_file).pack(side="right")

        self.btn = tk.Button(root, text="Convert", command=self.start, bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), height=2, width=25)
        self.btn.pack(pady=20)

        self.log_box = tk.Text(root, height=10, width=60, state="disabled", bg="#ffffff", font=("Consolas", 8))
        self.log_box.pack(padx=20, pady=10)

    def select_file(self):
        path = filedialog.askopenfilename(title="Select Unity File", filetypes=[("Unity Files", "*.unity3d *.bundle *.assets"), ("All Files", "*.*")])
        if path:
            self.input_file.set(path)

    def start(self):
        if not self.input_file.get():
            messagebox.showwarning("Warning", "Please select a Unity file to convert.")
            return
        self.btn.config(state="disabled", text="Processing...")
        threading.Thread(target=self.work, daemon=True).start()

    def work(self):
        process_unity_to_glb(self.input_file.get(), self.update_log)
        self.root.after(0, lambda: self.btn.config(state="normal", text="Convert"))

    def update_log(self, msg):
        self.log_box.config(state="normal")
        self.log_box.insert(tk.END, msg)
        self.log_box.see(tk.END)
        self.log_box.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    app = OneClickConverterApp(root)
    root.mainloop()