import sys
import os
import winreg
import webbrowser

sys.path.insert(0, os.path.abspath("."))
import modules.apps as a

print("Testing app discovery for whatsapp, chatgpt, vscode, spotify:")
for app in ["whatsapp", "chatgpt", "vscode", "spotify", "my coding editor"]:
    key = a.normalize_app_name(app)
    print(f"Query: '{app}' -> Normalized Key: '{key}'")
