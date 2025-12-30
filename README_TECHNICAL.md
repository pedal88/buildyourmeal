# Technical Documentation ⚙️

**Audience**: Developers, System Architects, Maintainers.

The AI Kitchen is a full-stack Flask application that leverages a "Human-in-the-Loop" AI architecture. It strictly separates **Generative Logic** (Text/Recipe Data) from **Visual Logic** (Image Generation) to ensure data consistency and validity.

## 1. Architecture Overview

The application follows a Service-Oriented Architecture (SOA) purely within a monolith structure:

*   **Frontend**: Server-side rendered Jinja2 templates styled with TailwindCSS.
*   **Backend**: Flask (Python 3.13) serving as the controller and API gateway.
*   **AI Layer**: a centralized `ai_engine.py` abstracts all interactions with Google Gemini 1.5 Flash.
*   **Visual Layer**: A dedicated `photographer_service.py` handles prompt engineering and interaction with the Imagen 3 model.
*   **Data Layer**: SQLite (via SQLAlchemy) for relational data (Recipes) + JSON for static configuration (Pantry, Taxonomies).

## 2. Data Flow

The following diagram illustrates how a user request is transformed into a finalized recipe with an image.

```mermaid
graph TD
    A[User Input: "Spicy Chicken"] -->|POST /generate| B[App Controller]
    B -->|Context: Pantry + Chef Persona| C[AI Engine: Gemini 1.5]
    C -->|Draft Recipe JSON| D{Validation Logic}
    D -- Invalid --> C
    D -- Valid --> E[Database: Recipe Record]
    E --> F[UI: Recipe Preview]
    
    subgraph "Visual Pipeline"
    F -->|User Clicks 'Studio/Snap Photo'| G[Photographer Service]
    G -->|Extract Visual DNA| H[Prompt Engineer]
    H -->|Enhanced Prompt| I[Imagen 3: Image Engine]
    I -->|Raw Bytes| J[Image Processor: PIL]
    J -->|File Save| K[Static Assets]
    end
    
    K --> L[Final UI: High-Res Dish Photo]
```

## 3. Directory Structure

```text
/
├── app.py                 # Application Entry Point & Route Logic
├── ai_engine.py           # Gemini Wrapper & Recipe Validation
├── data/                  # Static Configuration (JSON)
│   ├── chefs.json         # AI Persona Definitions
│   ├── meal_types.json    # Classification Taxonomies
│   ├── protein_types.json # Hierarchical Protein Data
│   └── ...
├── database/
│   └── models.py          # SQLAlchemy Models (Recipe, Ingredient)
├── services/
│   ├── photographer_service.py # Image Generation Logic
│   └── pantry_service.py       # Ingredient Context Logic
├── static/
│   ├── recipes/           # Generated Recipe Images
│   └── pantry/            # Static Ingredient Assets
└── templates/             # Jinja2 HTML Templates
```

## 4. API Strategy

### System Prompts
System prompts are not hardcoded strings. They are dynamic constructs assembled at runtime:
1.  **Role**: Defined in `chefs.json`.
2.  **Context**: The verified `pantry.json` data is injected to prevent hallucinated ingredients.
3.  **Rules**: Strict strict JSON schema constraints (Pydantic validation) are appended to ensure the AI output can be parsed programmatically.

### Image Generation
We do not simply ask for "an image of the dish." The `photographer_service.py` constructs a "Visual Prompt" that describes:
*   **Subject**: The gathered list of verified ingredients or a reference image analysis.
*   **Lighting**: Defined by the photographer persona.
*   **Composition**: 1:1 Aspect Ratio, Macro Food Photography styles.

### Vision Capabilities
The studio now supports **Gemini Vision (1.5/2.0 Flash)** to analyze uploaded reference images. The system extracts style, lighting, and plating details from the user's photo to generate a matching prompt.

## 5. Development Setup

### Environment Variables
The application requires the following strictly defined environment variables in `.env`:

*   `GOOGLE_API_KEY`: Required. Must have permissions for `gemini-1.5-flash` and `imagen-3.0-generate-001` (or higher).

### Testing Protocols
*   **Unit Tests**: Run `python -m unittest` to verify core logic.
*   **Diagnostics**: Use `verify_setup.py` to check path integrity and API connections.
*   **Mocking**: The Photographer service typically requires live API calls; use the placeholder generator for offline dev work.
