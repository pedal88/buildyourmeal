from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Boolean, Text, Float, ForeignKey
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class Ingredient(db.Model):
    __tablename__ = 'ingredient'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    food_id: Mapped[str] = mapped_column(String, unique=True, index=True) # Must preserve leading zeros (e.g., "000322")
    name: Mapped[str] = mapped_column(String, index=True) # Display name (e.g., "Avocado")

    # Classification
    main_category: Mapped[str] = mapped_column(String, nullable=True)
    sub_category: Mapped[str] = mapped_column(String, nullable=True)
    tags: Mapped[str] = mapped_column(String, nullable=True) # A comma-separated string for attributes like "keto,vegan,perishable"

    # Physics (Smart Units)
    default_unit: Mapped[str] = mapped_column(String, default='g')
    average_g_per_unit: Mapped[float] = mapped_column(Float, nullable=True) # The weight of 1 unit in grams.

    # Intelligence
    aliases: Mapped[str] = mapped_column(Text, default='[]') # JSON list of synonyms
    is_basic_ingredient: Mapped[bool] = mapped_column(Boolean, default=False) # User preference: Staple ingredient?
    is_original: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String, nullable=True) # ISO format date string

    # Payload (Flattened)
    image_url: Mapped[str] = mapped_column(String, nullable=True)
    image_prompt: Mapped[str] = mapped_column(Text, nullable=True)

    # Nutrition Columns
    calories_per_100g: Mapped[float] = mapped_column(Float, nullable=True)
    kj_per_100g: Mapped[float] = mapped_column(Float, nullable=True)
    protein_per_100g: Mapped[float] = mapped_column(Float, nullable=True)
    carbs_per_100g: Mapped[float] = mapped_column(Float, nullable=True)
    fat_per_100g: Mapped[float] = mapped_column(Float, nullable=True)
    fat_saturated_per_100g: Mapped[float] = mapped_column(Float, nullable=True)
    sugar_per_100g: Mapped[float] = mapped_column(Float, nullable=True)
    fiber_per_100g: Mapped[float] = mapped_column(Float, nullable=True)
    sodium_mg_per_100g: Mapped[float] = mapped_column(Float, nullable=True)

    recipe_ingredients: Mapped[list["RecipeIngredient"]] = relationship(back_populates="ingredient")

class Chef(db.Model):
    __tablename__ = 'chef'
    id: Mapped[str] = mapped_column(String, primary_key=True) # e.g. "french_classic"
    name: Mapped[str] = mapped_column(String, nullable=False)
    archetype: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    image_filename: Mapped[str] = mapped_column(String)
    
    # Store complex JSON constraints as strings for now
    constraints: Mapped[str] = mapped_column(Text, default='{}') 
    diet_preferences: Mapped[str] = mapped_column(Text, default='[]')
    cooking_style: Mapped[str] = mapped_column(Text, default='{}')
    ingredient_logic: Mapped[str] = mapped_column(Text, default='{}')
    instruction_style: Mapped[str] = mapped_column(Text, default='{}')

    recipes: Mapped[list["Recipe"]] = relationship(back_populates="chef")

class RecipeMealType(db.Model):
    __tablename__ = 'recipe_meal_type'
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"), primary_key=True)
    meal_type: Mapped[str] = mapped_column(String, primary_key=True)

class Recipe(db.Model):
    __tablename__ = 'recipe'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    cuisine: Mapped[str] = mapped_column(String)
    diet: Mapped[str] = mapped_column(String)
    difficulty: Mapped[str] = mapped_column(String)
    protein_type: Mapped[str] = mapped_column(String, nullable=True)
    image_filename: Mapped[str] = mapped_column(String, nullable=True)

    # New Metadata
    chef_id: Mapped[str] = mapped_column(ForeignKey("chef.id"), nullable=True)
    taste_level: Mapped[int] = mapped_column(Integer, nullable=True) # 1-5
    prep_time_mins: Mapped[int] = mapped_column(Integer, nullable=True) # snapped to time.json
    cleanup_factor: Mapped[int] = mapped_column(Integer, nullable=True)

    # Nutrition Totals (Calculated)
    total_calories: Mapped[float] = mapped_column(Float, nullable=True)
    total_protein: Mapped[float] = mapped_column(Float, nullable=True)
    total_carbs: Mapped[float] = mapped_column(Float, nullable=True)
    total_fat: Mapped[float] = mapped_column(Float, nullable=True)
    total_fiber: Mapped[float] = mapped_column(Float, nullable=True)
    total_sugar: Mapped[float] = mapped_column(Float, nullable=True)

    instructions: Mapped[list["Instruction"]] = relationship(back_populates="recipe", cascade="all, delete-orphan")
    ingredients: Mapped[list["RecipeIngredient"]] = relationship(back_populates="recipe", cascade="all, delete-orphan")
    chef: Mapped["Chef"] = relationship(back_populates="recipes")
    meal_types: Mapped[list["RecipeMealType"]] = relationship(cascade="all, delete-orphan")

    @property
    def meal_types_list(self):
        return [fmt.meal_type for fmt in self.meal_types]

class Instruction(db.Model):
    __tablename__ = 'instruction'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"), nullable=False)
    phase: Mapped[str] = mapped_column(String, nullable=False) # "Prep", "Cook", "Serve"
    component: Mapped[str] = mapped_column(String(100), nullable=False, default="Main Dish") # NEW: e.g., "The Steak", "The Sauce"
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    recipe: Mapped["Recipe"] = relationship(back_populates="instructions")

class RecipeIngredient(db.Model):
    __tablename__ = 'recipe_ingredient'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"), nullable=False)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredient.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String)
    component: Mapped[str] = mapped_column(String, default="Main", nullable=False)

    recipe: Mapped["Recipe"] = relationship(back_populates="ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="recipe_ingredients")

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

