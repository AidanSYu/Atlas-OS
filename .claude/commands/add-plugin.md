Create a new Atlas plugin. The user will provide: $ARGUMENTS

Steps:
1. Create a new directory under `src/backend/plugins/<plugin-name>/`
2. Create `manifest.json` with the plugin's name, description, version, and tool schemas
3. Create `wrapper.py` implementing the plugin logic following the Universal Plugin Protocol
4. Verify the plugin loads by checking the catalog endpoint
5. Follow the patterns in existing plugins under `src/backend/plugins/`