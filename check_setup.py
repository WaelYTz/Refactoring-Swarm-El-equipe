import sys
import os

def check():
    print("🔍 VERIFICATION SETUP...")
    all_good = True
    
    # Check Python
    v = sys.version_info
    if v.major == 3 and v.minor in [10, 11]:
        print("✅ Python Version OK")
    else:
        print(f"❌ Python 3.10/3.11 requis. Actuel: {v.major}.{v.minor}")
        all_good = False

    # Check Libs
    try:
        import langchain
        import dotenv
        print("✅ Librairies installées")
    except ImportError:
        print("❌ Manque des librairies (pip install -r requirements.txt)")
        all_good = False

    if all_good: print("🚀 TOUT EST PRET")
    else: print("⚠️ CORRIGER LES ERREURS")

if __name__ == "__main__":
    check()