import sys
import os
sys.path.append(os.getcwd())
try:
    from services.vertex_image_service import VertexImageGenerator
except ImportError:
    # Handle case where imports might need package adjustment or we are not in root
    sys.path.append(os.path.join(os.getcwd(), '..'))
    from services.vertex_image_service import VertexImageGenerator

gen = VertexImageGenerator(root_path=os.getcwd())

# Test 1: With Visual Details
prompt_1 = gen.get_prompt("Cheddar Cheese", visual_details="Sharp, orange, block")
print(f"--- TEST 1: Details ---\n{prompt_1}\n")

# Test 2: Without Visual Details
prompt_2 = gen.get_prompt("Milk", visual_details="")
print(f"--- TEST 2: No Details ---\n{prompt_2}\n")
