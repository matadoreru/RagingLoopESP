# Raging Loop Text Tool

A specialized tool designed to extract, translate, and repack **TextAssets** from the Unity game *Raging Loop*. This application streamlines the workflow for fan-translations and script editing.


## How to Use
1. **Launch the App:** Open the executable.
2. **Load Assets:**
   * Click on **"Open .assets"**.
   * Navigate to your game installation folder.
   * Enter the `ragingloop_Data` directory.
   * Open the `resource.assets` file.
3. **Locate TextAssets:**
   * The available files will appear on the **left panel**.
   * *Note: Initial game texts are located in `scenario01_start` (separate files for Japanese and English).*
4. **Translate:**
   * Select a **TextAsset** from the list.
   * Lines will appear in the **Script Lines** panel.
   * Select a line and start translating your text.

## Sessions
Sessions are used to keep track of translated parts. Every time you open the `.assets` file, make sure to **load your session file** to resume your progress.

## Apply changes
1. Click on **"Save .assets"**.
2. Select a location to save the new .assets file.
3. **Replace** the original `resource.assets` in the game folder with your newly created file.

## Future Roadmap
- [ ] Improved compatibility for additional TextAsset formats (keys...).
- [ ] Multi-language support for the UI.

## ⚠️ Important
Always create a backup of your original `resource.assets` file before replacing it.

## ⚖️ License
This tool is for fan-translation purposes only. Raging Loop is a trademark of its respective owners.
