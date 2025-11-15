import { getRecipes, getWeeks, getRecipesByWeek, getLatestWeek } from '@/lib/data';
import RecipeCard from '@/components/RecipeCard';

export default function HomePage() {
  const allRecipes = getRecipes();
  const weeks = getWeeks();
  const latestWeek = getLatestWeek();

  // Get recipes for latest week, or all if no week labels
  const featuredRecipes = latestWeek
    ? getRecipesByWeek(latestWeek)
    : allRecipes;

  return (
    <div className="home-page">
      <section className="hero">
        <h2>This Week's Recipes</h2>
        {latestWeek && <p className="hero-week">{latestWeek}</p>}
        <p className="hero-description">
          Interactive Gantt chart timelines to make cooking easier and clearer.
          See what to prep, what can overlap, and how to time your meal perfectly.
        </p>
      </section>

      {weeks.length > 1 && (
        <section className="week-selector">
          <h3>Browse by Week</h3>
          <div className="week-list">
            {weeks.map(week => (
              <a key={week} href={`#week-${week}`} className="week-link">
                {week}
              </a>
            ))}
          </div>
        </section>
      )}

      <section className="recipes-section">
        <h3>Featured Recipes</h3>
        {featuredRecipes.length === 0 ? (
          <div className="no-recipes">
            <p>No recipes available yet.</p>
            <p>Run the data pipeline to scrape and parse recipes:</p>
            <pre>npm run build-data</pre>
          </div>
        ) : (
          <div className="recipe-grid">
            {featuredRecipes.map(recipe => (
              <RecipeCard key={recipe.id} recipe={recipe} />
            ))}
          </div>
        )}
      </section>

      {weeks.map(week => {
        const weekRecipes = getRecipesByWeek(week);
        if (week === latestWeek || weekRecipes.length === 0) return null;

        return (
          <section key={week} id={`week-${week}`} className="recipes-section">
            <h3>{week}</h3>
            <div className="recipe-grid">
              {weekRecipes.map(recipe => (
                <RecipeCard key={recipe.id} recipe={recipe} />
              ))}
            </div>
          </section>
        );
      })}

      <section className="stats-section">
        <h3>Collection Stats</h3>
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{allRecipes.length}</div>
            <div className="stat-label">Total Recipes</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{weeks.length}</div>
            <div className="stat-label">Weeks Available</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">
              {allRecipes.reduce((sum, r) => sum + r.steps.length, 0)}
            </div>
            <div className="stat-label">Total Steps</div>
          </div>
          {allRecipes.length > 0 && (
            <div className="stat-card">
              <div className="stat-value">
                {Math.round(
                  allRecipes.reduce((sum, r) => sum + r.total_time_min, 0) /
                    allRecipes.length
                )}
                min
              </div>
              <div className="stat-label">Average Cook Time</div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
