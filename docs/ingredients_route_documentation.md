# /ingredients Route Technical Documentation

**Date:** 2026-01-09
**Version:** 1.0
**Purpose:** Documentation of the `/ingredients` route (The Pantry) for archival and re-implementation purposes.

## 1. Overview
The `/ingredients` route serves as the "Pantry" view, displaying a visual grid of all available ingredients in the system. It features client-side searching and filtering by category, along with a "mini-matrix" of nutritional data on hover.

## 2. Backend Implementation

**File:** `app.py`

### Dependencies
- **Models:** `Ingredient` (from `database.models`)
- **Database:** `db` (SQLAlchemy)
- **Framework:** `Flask` (`render_template`)

### Route Definition
```python
@app.route('/ingredients')
def pantry_list():
    # 1. Fetch all ingredients
    # Sorts alphabetically by name for the initial display
    ingredients = db.session.execute(
        db.select(Ingredient).order_by(Ingredient.name)
    ).scalars().all()
    
    # 2. Get unique categories for filtering
    # Fetches distinct 'main_category' values to populate the dropdown
    categories = db.session.execute(
        db.select(Ingredient.main_category).distinct()
    ).scalars().all()
    
    # Filter out None values and sort
    categories = [c for c in categories if c]
    
    # 3. Render Template
    return render_template('pantry.html', 
                         ingredients=ingredients, 
                         categories=sorted(categories))
```

### Key Logic
*   **Data Retrieval**: Performs two database queries per request. One for the full ingredient list and one for the distinct categories.
*   **Sorting**: Ingredients are pre-sorted by `name` at the database level.
*   **Context**: Passes `ingredients` (list of Ingredient objects) and `categories` (list of strings) to the template.

## 3. Frontend Implementation

**File:** `templates/pantry.html`

### Dependencies
*   **Base Template:** Extends `base.html`
*   **Components:** Imports `components/typography.html` and `components/cards.html` (though `cards.html` is imported, the grid items currently use custom HTML structure).

### Structure

1.  **Header**: Standard page header using the typography component.
2.  **Sticky Control Bar (`div#controlBar`):**
    *   **Search Input (`#searchInput`):** Text input for filtering by name.
    *   **Category Filter (`#categorySelect`):** Dropdown populated by the `categories` context variable.
    *   **Reset Button:** Clears filters.
    *   **Count Display (`#countDisplay`):** Dynamic counter showing visible items.
3.  **Ingredient Grid (`div#pantryGrid`):**
    *   Responsive CSS Grid: `grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6`.
    *   **Item Structure:**
        *   Wrapper: `<div class="ingredient-item">` with `data-name` and `data-category` attributes for JS filtering.
        *   **Image Area:** Displays ingredient image (`/static/...`) or a fallback emoji (📦). Contains a hover-only ID badge.
        *   **Content Area:** Displays Category (small uppercase) and Name (CamelCase).
        *   **Nutrition Matrix (Hover):** A 2x2 grid showing Cal, Pro, Fat, Carb per 100g. Hidden by default (`opacity-60`), fully visible on group hover.

### Client-Side Logic (JavaScript)
The filtering is performed entirely client-side for immediate feedback (no API calls).

```javascript
// Key Elements
const searchInput = document.getElementById('searchInput');
const categorySelect = document.getElementById('categorySelect');
const items = document.querySelectorAll('.ingredient-item');

// Filter Logic
function filterItems() {
    const query = searchInput.value.toLowerCase();
    const category = categorySelect.value;
    
    items.forEach(item => {
        // Match against data attributes
        const name = item.dataset.name;
        const itemCategory = item.dataset.category;
        
        const matchesSearch = name.includes(query);
        const matchesCategory = category === 'all' || itemCategory === category;
        
        // Toggle Visibility
        if (matchesSearch && matchesCategory) {
            item.style.display = 'block';
        } else {
            item.style.display = 'none';
        }
    });
    // Update counters and empty state...
}
```

## 4. Re-implementation Guide

If this route is deleted and needs to be restored:

1.  **Restore Backend**:
    *   Open `app.py`.
    *   Import `Ingredient` from `database.models` if missing.
    *   Add the `pantry_list` function decorated with `@app.route('/ingredients')` as shown in Section 2.
    *   Ensure the template path matches `'pantry.html'`.

2.  **Restore Frontend**:
    *   Ensure `templates/pantry.html` exists.
    *   If the template was deleted, recreate it with the standard structure:
        *   Extend `base.html`.
        *   Loop through `ingredients`.
        *   Add `data-name` and `data-category` attributes to each item container for the JS to work.
        *   Include the `<script>` block at the bottom for the filtering logic.

3.  **Verify**:
    *   Visit `/ingredients`.
    *   Check that the grid loads.
    *   Test the Search bar (e.g., type "bacon").
    *   Test the Category dropdown.
