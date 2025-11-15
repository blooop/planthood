import { getRecipeById, getRecipes } from '@/lib/data';
import GanttChart from '@/components/GanttChart';
import { notFound } from 'next/navigation';

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

export default function RecipePage({ params }: RecipePageProps) {
  const recipe = getRecipeById(params.id);

  if (!recipe) {
    notFound();
  }

  return (
    <div className="recipe-page">
      <div className="recipe-header">
        <a href="/" className="back-link">← Back to all recipes</a>

        <h1>{recipe.title}</h1>

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

        <div className="recipe-times">
          <div className="time-badge">
            <strong>Total Time:</strong> {recipe.total_time_min} minutes
          </div>
          <div className="time-badge">
            <strong>Active Time:</strong> {recipe.active_time_min} minutes
          </div>
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

      {recipe.steps.length > 0 && (
        <section className="recipe-timeline-section">
          <h2>Cooking Timeline (Gantt Chart)</h2>
          <p className="timeline-description">
            Interactive timeline showing when to start each step. Click any step for details.
            <br />
            <strong>Color code:</strong>{' '}
            <span className="color-legend prep">Blue = Prep</span>{' '}
            <span className="color-legend cook">Orange = Cooking</span>{' '}
            <span className="color-legend finish">Green = Finishing</span>
          </p>
          <GanttChart steps={recipe.steps} />
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
