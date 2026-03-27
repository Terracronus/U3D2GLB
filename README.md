# U3D2GLB
A fast, one-click Python GUI tool that extracts 3D assets from `.unity3d` files and automatically assembles them into a standard, ready-to-use `.glb` model.  This tool handles the extraction, material mapping, and cleanup all in the background.

## 📝 Compatibility Note
This tool was built to streamline Virtual Tabletop (VTT) workflows. If you have Unity-based VTT assets and need them in a universally supported `.glb` format for other engines, this tool ought to work.

## ✨ Features
* **One-Click Pipeline:** Select your Unity file, click "Convert", and get a `.glb` in the same folder.
* **Direct Extraction:** Uses `UnityPy` to rip Meshes and Texture2D files directly from the source.
* **Smart Material Assembly:** 
  * Automatically converts Unity's packed DXT5nm normal maps to standard RGB normal maps.
  * Splits Unity's Metallic/Smoothness maps into proper GLB Metallic/Roughness values.
  * Auto-assigns diffuse, normal, metal, emissive, and occlusion maps based on naming conventions.
* **Clean Workspace:** Uses a temporary hidden directory for extraction, meaning your folders don't get cluttered with intermediate `.obj` and `.png` files.

## 🛠️ Requirements
* Python 3 (includes Tkinter)
* `UnityPy`
* `trimesh`
* `numpy`
* `Pillow`

## 🚀 How to Use
1. Download or clone this repository.
2. Run the script from your terminal: `python unity_to_glb.py`
3. The GUI will pop up. Click **Browse** and select your target Hero Forge file (e.g., `model.unity3d`).
4. Click **Convert**.
5. Wait a moment for the background processing to finish. You'll get a success popup, and your shiny new `.glb` file will be sitting right next to your original Unity file!

## ⚠️ Legal Disclaimer
Users are solely responsible for ensuring they have the legal right to extract, convert, and modify the digital assets they process. 
Please respect the Terms of Service (ToS) and End User License Agreements (EULA) of the digital storefronts, VTT platforms, and independent creators you purchase assets from.
I assumes no liability for any misuse of this software.

## 📜 License and Credit
This project is licensed under the **MIT License** - see the LICENSE file for details.

**Credit:** If you use, modify, or include this tool in your own workflow or software, please provide credit to **Carlo Freiria/Terracronus** by keeping the copyright notice intact.
