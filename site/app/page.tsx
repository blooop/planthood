import {
  getProcessedRecipes,
  getProcessedWeeks,
  getProcessedRecipesByWeek,
  getLatestProcessedWeek,
  getWeekStartDate,
} from '@/lib/data';
import RecipeCard from '@/components/RecipeCard';
import WeekDropdown from '@/components/WeekDropdown';

const ORIGINAL_SITE_URL = 'https://planthood.co.uk/collections/cooking-instructions';

function startOfWeek(date: Date) {
  const result = new Date(date);
  const day = result.getDay();
  const diff = (day + 6) % 7;
  result.setDate(result.getDate() - diff);
  result.setHours(0, 0, 0, 0);
  return result;
}

function slugifyWeek(label: string) {
  return label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

export default function HomePage() {
  const allRecipes = getProcessedRecipes();
  const weeks = getProcessedWeeks();
  const latestWeek = getLatestProcessedWeek();
  const weekOptions = weeks.map(label => ({
    label,
    anchor: slugifyWeek(label),
  }));

  const weekInfos = weeks.map(week => ({
    label: week,
    date: getWeekStartDate(week),
  }));

  const todayWeekStart = startOfWeek(new Date());
  const sameWeek = weekInfos.find(
    info => info.date && info.date.getTime() === todayWeekStart.getTime()
  );
  const upcomingWeek = weekInfos
    .filter(info => info.date && info.date.getTime() > todayWeekStart.getTime())
    .sort((a, b) => (a.date && b.date ? a.date.getTime() - b.date.getTime() : 0))[0];

  const currentWeekLabel =
    sameWeek?.label ?? upcomingWeek?.label ?? latestWeek ?? weeks[0] ?? null;

  const selectedWeek = currentWeekLabel ?? (weeks.length > 0 ? weeks[0] : null);

  const selectedRecipes =
    selectedWeek === null
      ? allRecipes
      : selectedWeek
        ? getProcessedRecipesByWeek(selectedWeek)
        : allRecipes;

  const heroWeekLabel = selectedWeek ?? 'All available weeks';
  const recipesHeading = selectedWeek
    ? `${selectedWeek} Recipes`
    : 'All Processed Recipes';

  return (
    <div className="home-page">
      <section className="hero">
        <h2>This Week's Recipes</h2>
        {heroWeekLabel && <p className="hero-week">{heroWeekLabel}</p>}
        <p className="hero-description">
          Interactive Gantt chart timelines to make cooking easier and clearer.
          See what to prep, what can overlap, and how to time your meal perfectly.{' '}
          <a href={ORIGINAL_SITE_URL} target="_blank" rel="noreferrer">
            View the official Planthood instructions
          </a>
          .
        </p>
      </section>

      {weeks.length > 0 ? (
        <section className="week-selector">
          <div className="week-selector-header">
            <div className="week-selector-copy">
              <h3>Select a delivery week</h3>
              <p>
                {selectedWeek
                  ? `Currently showing recipes for ${selectedWeek}.`
                  : 'Showing every processed recipe in chronological order.'}
              </p>
              {currentWeekLabel && (
                <p className="week-selector-meta">
                  Defaulting to <strong>{currentWeekLabel}</strong> to match the
                  Planthood delivery schedule.
                </p>
              )}
            </div>
            <WeekDropdown
              weeks={weekOptions}
              selectedWeek={selectedWeek}
              currentWeek={currentWeekLabel}
            />
          </div>
        </section>
      ) : (
        <section className="week-selector week-selector--empty">
          <div className="week-selector-copy">
            <h3>Select a delivery week</h3>
            <p>
              We’ll list upcoming delivery weeks here once the Planthood data
              includes their published schedules.
            </p>
          </div>
        </section>
      )}

      <section className="recipes-section">
        <h3>{recipesHeading}</h3>
        {selectedRecipes.length === 0 ? (
          <div className="no-recipes">
            <p>No recipes available yet.</p>
            <p>Run the data pipeline to scrape and parse recipes:</p>
            <pre>npm run build-data</pre>
          </div>
        ) : (
          <div className="recipe-grid">
            {selectedRecipes.map(recipe => (
              <RecipeCard key={recipe.id} recipe={recipe} />
            ))}
          </div>
        )}
      </section>

      {selectedWeek &&
        weeks.map(week => {
          if (week === selectedWeek) return null;
          const weekRecipes = getProcessedRecipesByWeek(week);
          if (weekRecipes.length === 0) return null;

          return (
            <section
              key={week}
              id={`week-${slugifyWeek(week)}`}
              className="recipes-section"
            >
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
