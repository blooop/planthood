import Link from 'next/link';
import { Recipe } from '@/lib/types';
import { fetchRecipeImage } from '@/lib/images';

interface RecipeCardProps {
  recipe: Recipe;
}

export default async function RecipeCard({ recipe }: RecipeCardProps) {
  const thumbnail = await fetchRecipeImage(recipe.source_url);

  return (
    <Link href={`/recipe/${recipe.id}`} className="recipe-card">
      <div className="recipe-card-image">
        {thumbnail ? (
          <img
            src={thumbnail}
            alt={`Thumbnail for ${recipe.title}`}
            loading="lazy"
          />
        ) : (
          <div className="recipe-card-placeholder">
            <span>No image</span>
          </div>
        )}
      </div>

      <div className="recipe-card-content">
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
      </div>
    </Link>
  );
}
