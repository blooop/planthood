import { Recipe } from './types';
import * as fs from 'fs';
import * as path from 'path';

let cachedRecipes: Recipe[] | null = null;

/**
 * Load recipes from the generated data file
 */
function loadRecipes(): Recipe[] {
  if (cachedRecipes) {
    return cachedRecipes;
  }

  // Try multiple possible paths for the data file
  const possiblePaths = [
    path.join(process.cwd(), '..', 'data', 'recipes_with_schedule.json'),
    path.join(process.cwd(), 'data', 'recipes_with_schedule.json'),
    path.join(__dirname, '..', '..', '..', 'data', 'recipes_with_schedule.json'),
  ];

  let dataPath = possiblePaths[0];
  for (const p of possiblePaths) {
    if (fs.existsSync(p)) {
      dataPath = p;
      break;
    }
  }

  // Check if data file exists
  if (!fs.existsSync(dataPath)) {
    console.warn('Recipe data file not found at:', dataPath);
    return [];
  }

  try {
    const fileContents = fs.readFileSync(dataPath, 'utf-8');
    const recipes = JSON.parse(fileContents) as Recipe[];
    cachedRecipes = recipes;
    return recipes;
  } catch (error) {
    console.error('Error loading recipes:', error);
    return [];
  }
}

/**
 * Get all recipes
 */
export function getRecipes(): Recipe[] {
  return loadRecipes();
}

/**
 * Get a recipe by ID
 */
export function getRecipeById(id: string): Recipe | undefined {
  const recipes = loadRecipes();
  return recipes.find(recipe => recipe.id === id);
}

/**
 * Get all unique week labels, sorted by most recent
 */
export function getWeeks(): string[] {
  const recipes = loadRecipes();
  const weeks = new Set<string>();

  recipes.forEach(recipe => {
    if (recipe.week_label) {
      weeks.add(recipe.week_label);
    }
  });

  return Array.from(weeks).sort().reverse();
}

/**
 * Get recipes for a specific week
 */
export function getRecipesByWeek(week: string): Recipe[] {
  const recipes = loadRecipes();
  return recipes.filter(recipe => recipe.week_label === week);
}

/**
 * Get the most recent week label
 */
export function getLatestWeek(): string | null {
  const weeks = getWeeks();
  return weeks.length > 0 ? weeks[0] : null;
}

/**
 * Check if a recipe has been processed (has steps and schedule)
 */
function isRecipeProcessed(recipe: Recipe): boolean {
  return recipe.steps && recipe.steps.length > 0 && recipe.total_time_min > 0;
}

/**
 * Get only processed recipes
 */
export function getProcessedRecipes(): Recipe[] {
  const recipes = loadRecipes();
  return recipes.filter(isRecipeProcessed);
}

/**
 * Get processed recipes for a specific week
 */
export function getProcessedRecipesByWeek(week: string): Recipe[] {
  const recipes = loadRecipes();
  return recipes.filter(recipe =>
    recipe.week_label === week && isRecipeProcessed(recipe)
  );
}

/**
 * Get weeks that have processed recipes
 */
export function getProcessedWeeks(): string[] {
  const recipes = getProcessedRecipes();
  const weeks = new Set<string>();

  recipes.forEach(recipe => {
    if (recipe.week_label) {
      weeks.add(recipe.week_label);
    }
  });

  return Array.from(weeks).sort().reverse();
}

/**
 * Get the most recent week that has processed recipes
 */
export function getLatestProcessedWeek(): string | null {
  const weeks = getProcessedWeeks();
  return weeks.length > 0 ? weeks[0] : null;
}
