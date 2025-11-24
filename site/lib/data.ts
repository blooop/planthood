import { Recipe } from './types';
import * as fs from 'fs';
import * as path from 'path';

const isProd = process.env.NODE_ENV === 'production';
let cachedRecipes: Recipe[] | null = null;

const MONTH_MAP: Record<string, number> = {
  january: 0,
  february: 1,
  march: 2,
  april: 3,
  may: 4,
  june: 5,
  july: 6,
  august: 7,
  september: 8,
  october: 9,
  november: 10,
  december: 11,
};

function removeOrdinals(value: string) {
  return value.replace(/(\d+)(st|nd|rd|th)/gi, '$1');
}

function normalizeWeekText(label: string) {
  return removeOrdinals(
    label
      .replace(/menu/gi, ' ')
      .replace(/deliver(?:ed|ies|y)?/gi, ' ')
      .replace(/week\s*(?:of|commencing|starting|ending)/gi, ' ')
      .replace(/w\/?c/gi, ' ')
      .replace(/[\|,]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
  );
}

function alignToWeekStart(date: Date) {
  const aligned = new Date(date);
  const day = aligned.getDay();
  const diff = (day + 6) % 7; // Monday as start
  aligned.setDate(aligned.getDate() - diff);
  aligned.setHours(0, 0, 0, 0);
  return aligned;
}

export function getWeekStartDate(weekLabel?: string | null): Date | null {
  if (!weekLabel) return null;

  const label = normalizeWeekText(weekLabel);
  if (!label) return null;

  const isoMatch = label.match(/(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (isoMatch) {
    const [_, year, month, day] = isoMatch;
    const date = new Date(
      Number(year),
      Number(month) - 1,
      Number(day)
    );
    return Number.isNaN(date.getTime()) ? null : alignToWeekStart(date);
  }

  const slashMatch = label.match(/(\d{1,2})\/(\d{1,2})\/(\d{2,4})/);
  if (slashMatch) {
    const [_, day, month, year] = slashMatch;
    const fullYear = year.length === 2 ? Number(`20${year}`) : Number(year);
    const date = new Date(fullYear, Number(month) - 1, Number(day));
    return Number.isNaN(date.getTime()) ? null : alignToWeekStart(date);
  }

  const textMatch = label.match(
    /(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})/i
  );
  if (textMatch) {
    const [, day, monthName, year] = textMatch;
    const month = MONTH_MAP[monthName.toLowerCase()];
    const date = new Date(Number(year), month, Number(day));
    return Number.isNaN(date.getTime()) ? null : alignToWeekStart(date);
  }

  const reversedTextMatch = label.match(
    /(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})\s+(\d{4})/i
  );
  if (reversedTextMatch) {
    const [_, monthName, day, year] = reversedTextMatch;
    const month = MONTH_MAP[monthName.toLowerCase()];
    const date = new Date(Number(year), month, Number(day));
    return Number.isNaN(date.getTime()) ? null : alignToWeekStart(date);
  }

  const parsed = new Date(label);
  if (!Number.isNaN(parsed.getTime())) {
    return alignToWeekStart(parsed);
  }

  return null;
}

function compareWeekLabels(a?: string | null, b?: string | null) {
  const dateA = getWeekStartDate(a);
  const dateB = getWeekStartDate(b);

  if (dateA && dateB) {
    return dateB.getTime() - dateA.getTime();
  }
  if (dateA) return -1;
  if (dateB) return 1;
  return (b ?? '').localeCompare(a ?? '');
}

function sortWeekLabels(weeks: string[]) {
  return [...weeks].sort((a, b) => compareWeekLabels(a, b));
}

/**
 * Load recipes from the generated data file
 */
function loadRecipes(): Recipe[] {
  if (isProd && cachedRecipes) {
    return cachedRecipes;
  }

  // Try multiple possible paths for the data file
  const possiblePaths = [
    // Prefer repository data files so dev server always reads the latest outputs
    path.join(process.cwd(), '..', 'data', 'recipes_with_schedule.json'),
    path.join(process.cwd(), 'data', 'recipes_with_schedule.json'),
    path.join(__dirname, '..', '..', '..', 'data', 'recipes_with_schedule.json'),
    // Fallback to static copy inside site/public for export builds
    path.join(process.cwd(), 'public', 'data', 'recipes_with_schedule.json'),
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
    if (isProd) {
      cachedRecipes = recipes;
    }
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

  return sortWeekLabels(Array.from(weeks));
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
 * Get only processed recipes (have steps and schedule)
 */
export function getProcessedRecipes(): Recipe[] {
  return loadRecipes()
    .filter(r => r.steps?.length > 0 && r.total_time_min > 0)
    .sort((a, b) => {
      const cmp = compareWeekLabels(a.week_label ?? null, b.week_label ?? null);
      if (cmp !== 0) return cmp;
      return a.title.localeCompare(b.title);
    });
}

/**
 * Get processed recipes for a specific week
 */
export function getProcessedRecipesByWeek(week: string): Recipe[] {
  return getProcessedRecipes().filter(r => r.week_label === week);
}

/**
 * Get weeks that have processed recipes
 */
export function getProcessedWeeks(): string[] {
  return Array.from(
    new Set(
      getProcessedRecipes()
        .map(r => r.week_label)
        .filter((week): week is string => typeof week === 'string' && week.length > 0)
    )
  ).sort((a, b) => compareWeekLabels(a, b));
}

/**
 * Get the most recent week that has processed recipes
 */
export function getLatestProcessedWeek(): string | null {
  return getProcessedWeeks()[0] ?? null;
}
