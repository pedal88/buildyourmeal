# The AI Kitchen 🍳

> **Transform your pantry staples into 5-star visual masterpieces using the power of Generative AI.**

The AI Kitchen is a next-generation recipe application that doesn't just tell you what to cook—it shows you. By combining advanced Large Language Models (Gemini 1.5) for culinary logic with state-of-the-art Image Generation models (Imagen 3), it creates a seamless, visual, and highly personalized cooking experience.

---

## 🌟 Core Features

*   **👨‍🍳 AI Chef Personas**: Choose your culinary guide—from a rustic Italian Nonna to a Michelin Star Innovator. Each chef has a unique voice, philosophy, and cooking style.
*   **📸 Visual Architect**: Every recipe generates a stunning, high-resolution realization of the final dish using Google's Imagen 3 technology. No generic stock photos.
*   **🧠 Pantry Intelligence**: Uses a "Human-in-the-Loop" architecture to validate AI-generated recipes against your *actual* real-world inventory.
*   **🏷️ Smart Classification**: Automatically categorizes meals by Cuisine, Diet, Difficulty, Protein Type, and Occasion (Meal Types) for easy organization.

## 🚀 How It Works

1.  **Draft**: Tell the AI what you're craving (e.g., "Something spicy with the chicken in my fridge"). The AI parses your request and selects the best ingredients from your pantry.
2.  **Architect**: The **Generative Engine** (Gemini 1.5) constructs a structured recipe, ensuring cooking times, techniques, and dietary rules are respected.
3.  **Visualize**: The **Visual Engine** (Imagen 3) reads the recipe's "DNA"—ingredients, plating style, mood—and generates a hyper-realistic photo of the dish before you even start cooking.

## ⚡ Quick Start

### Prerequisites
*   Python 3.10+
*   A Google Cloud API Key (with access to Gemini and Imagen)

### Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/your-username/the-ai-kitchen.git
    cd the-ai-kitchen
    ```

2.  **Install Dependencies**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Configure Environment**
    Create a `.env` file in the root directory:
    ```bash
    GOOGLE_API_KEY=your_api_key_here
    ```

4.  **Run the Kitchen**
    ```bash
    python app.py
    ```
    Open your browser to `http://127.0.0.1:8000` and start cooking!

---
*Built with Flask, TailwindCSS, and Google Gemini.*
