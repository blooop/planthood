import Link from 'next/link';
import { Recipe } from '@/lib/types';

interface RecipeCardProps {
  recipe: Recipe;
}

export default function RecipeCard({ recipe }: RecipeCardProps) {
  return (
    <Link href={`/recipe/${recipe.id}`} className="recipe-card">
      <div className="recipe-card-header">
        <h3 className="recipe-card-title">{recipe.title}</h3>
        {recipe.category && (
          <span className={`recipe-category ${recipe.category.toLowerCase()}`}>
            {recipe.category}
          </span>
        )}
      </div>

      <div className="recipe-card-meta">
        {recipe.week_label && (
          <div className="recipe-meta-item">
            <span className="recipe-meta-label">Week:</span>
            <span>{recipe.week_label}</span>
          </div>
        )}
        <div className="recipe-meta-item">
          <span className="recipe-meta-label">Total time:</span>
          <span>{recipe.total_time_min} min</span>
        </div>
        <div className="recipe-meta-item">
          <span className="recipe-meta-label">Active time:</span>
          <span>{recipe.active_time_min} min</span>
        </div>
      </div>

      {recipe.nutrition && (
        <div className="recipe-nutrition">
          {recipe.nutrition.calories && (
            <span>{recipe.nutrition.calories} kcal</span>
          )}
          {recipe.nutrition.protein_g && (
            <span>Protein: {recipe.nutrition.protein_g}g</span>
          )}
        </div>
      )}

      <div className="recipe-card-footer">
        <span className="recipe-view-link">View Recipe →</span>
      </div>
    </Link>
  );
}
