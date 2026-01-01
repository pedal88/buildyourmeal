import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

EXPECTED_FILES = [
    'constraints/pantry.json',
    'constraints/diets.json',
    'constraints/difficulty.json',
    'constraints/main_protein.json',
    'constraints/meal_types.json',
    'post_processing/cuisines.json',
    'post_processing/cooking_methods.json',
    'post_processing/taste.json',
    'post_processing/cleanup_factors.json',
    'post_processing/time_intervals.json',
    'agents/chefs.json',
    'agents/photographer.json'
]

def check_files():
    print(f"Checking files in {DATA_DIR}...")
    all_exist = True
    for relative_path in EXPECTED_FILES:
        full_path = os.path.join(DATA_DIR, relative_path)
        if os.path.exists(full_path):
            print(f"[OK] {relative_path}")
        else:
            print(f"[MISSING] {relative_path}")
            all_exist = False
    
    if all_exist:
        print("\nSUCCESS: All files found in new locations.")
    else:
        print("\nFAILURE: Some files are missing.")
        exit(1)

if __name__ == "__main__":
    check_files()
