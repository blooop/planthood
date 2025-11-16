import { getRecipeById, getRecipes } from '@/lib/data';
import GanttChart from '@/components/GanttChart';
import { notFound } from 'next/navigation';
import Link from 'next/link';
import { fetchRecipeImage } from '@/lib/images';

interface RecipePageProps {
  params: {
    id: string;
  };
}

// Generate static paths for all recipes
export async function generateStaticParams() {
  const recipes = getRecipes();
  return recipes.map(recipe => ({
    id: recipe.id,
  }));
}

export default async function RecipePage({ params }: RecipePageProps) {
  const recipe = getRecipeById(params.id);

  if (!recipe) {
    notFound();
  }

  const heroImage = await fetchRecipeImage(recipe.source_url);

  return (
    <div className="recipe-page">
      <Link href="/" className="back-link">← Back to all recipes</Link>

      <div className="recipe-hero-card">
        <div className="recipe-hero-media">
          {heroImage ? (
            <img
              src={heroImage}
              alt={`Dish photo for ${recipe.title}`}
              loading="lazy"
            />
          ) : (
            <div className="recipe-hero-placeholder">
              <span>Photo coming soon</span>
            </div>
          )}
        </div>

        <div className="recipe-header">
          <div className="recipe-meta-top">
            <div className="recipe-meta-bar">
              {recipe.category && (
                <span className={`recipe-category ${recipe.category.toLowerCase()}`}>
                  {recipe.category}
                </span>
              )}
              {recipe.week_label && (
                <span className="recipe-week">{recipe.week_label}</span>
              )}
            </div>
            <a
              href={recipe.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="source-link"
            >
              View original recipe →
            </a>
          </div>

          <h1>{recipe.title}</h1>

          <div className="recipe-times">
            <div className="time-badge">
              <strong>Total time</strong>
              <span>{recipe.total_time_min} minutes</span>
            </div>
            <div className="time-badge">
              <strong>Active time</strong>
              <span>{recipe.active_time_min} minutes</span>
            </div>
          </div>
        </div>
      </div>

      {recipe.steps.length > 0 && (
        <section className="recipe-timeline-section">
          <h2>Cooking Timeline</h2>
          <p className="timeline-description">
            Tap steps for details
          </p>
          <GanttChart steps={recipe.steps} />
        </section>
      )}

      {recipe.ingredients.length > 0 && (
        <section className="recipe-ingredients-section">
          <h2>Ingredients</h2>
          <ul className="ingredients-list">
            {recipe.ingredients.map((ingredient, idx) => (
              <li key={idx}>{ingredient}</li>
            ))}
          </ul>
        </section>
      )}

      {recipe.nutrition && Object.keys(recipe.nutrition).length > 0 && (
        <section className="recipe-nutrition-section">
          <h2>Nutrition Information</h2>
          <div className="nutrition-grid">
            {recipe.nutrition.calories && (
              <div className="nutrition-item">
                <strong>Calories</strong>
                <span>{recipe.nutrition.calories} kcal</span>
              </div>
            )}
            {recipe.nutrition.protein_g && (
              <div className="nutrition-item">
                <strong>Protein</strong>
                <span>{recipe.nutrition.protein_g}g</span>
              </div>
            )}
            {recipe.nutrition.fat_g && (
              <div className="nutrition-item">
                <strong>Fat</strong>
                <span>{recipe.nutrition.fat_g}g</span>
              </div>
            )}
            {recipe.nutrition.carbs_g && (
              <div className="nutrition-item">
                <strong>Carbs</strong>
                <span>{recipe.nutrition.carbs_g}g</span>
              </div>
            )}
            {recipe.nutrition.fibre_g && (
              <div className="nutrition-item">
                <strong>Fibre</strong>
                <span>{recipe.nutrition.fibre_g}g</span>
              </div>
            )}
            {recipe.nutrition.salt_g && (
              <div className="nutrition-item">
                <strong>Salt</strong>
                <span>{recipe.nutrition.salt_g}g</span>
              </div>
            )}
          </div>
        </section>
      )}

      {recipe.steps.length > 0 && (
        <section className="recipe-steps-section">
          <h2>Step-by-Step Instructions</h2>
          <ol className="steps-list">
            {recipe.steps.map(step => (
              <li key={step.id} className={`step-item step-${step.type}`}>
                <div className="step-header">
                  <h3>{step.label}</h3>
                  <span className="step-duration">{step.duration_min} min</span>
                </div>
                <p className="step-text">{step.raw_text}</p>
                {step.equipment.length > 0 && (
                  <div className="step-equipment">
                    <strong>Equipment:</strong> {step.equipment.join(', ')}
                  </div>
                )}
                {step.temperature_c && (
                  <div className="step-temperature">
                    <strong>Temperature:</strong> {step.temperature_c}°C
                  </div>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
