export interface RecipeStep {
  id: string;
  label: string;
  type: 'prep' | 'cook' | 'finish';
  duration_min: number;
  start_min: number;
  end_min: number;
  raw_text: string;
  equipment: string[];
  temperature_c?: number;
  requires: string[];
  can_overlap_with: string[];
  notes?: string;
  is_critical: boolean;
  slack_min: number;
  latest_start_min: number;
  latest_end_min: number;
}

export interface Recipe {
  id: string;
  title: string;
  source_url: string;
  category?: string;
  week_label?: string;
  weeks?: string[];
  ingredients: string[];
  steps: RecipeStep[];
  total_time_min: number;
  active_time_min: number;
  nutrition?: {
    calories?: number;
    protein_g?: number;
    fat_g?: number;
    carbs_g?: number;
    fibre_g?: number;
    salt_g?: number;
  };
}
