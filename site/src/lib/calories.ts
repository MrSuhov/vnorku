// Mifflin-St Jeor Formula для расчёта калорий

export type Gender = 'male' | 'female';
export type ActivityLevel = 'sedentary' | 'light' | 'moderate' | 'active' | 'very_active';
export type Goal = 'weight_loss' | 'maintenance' | 'muscle_gain' | 'keto';

export interface CalorieInput {
  gender: Gender;
  age: number;
  height: number; // cm
  weight: number; // kg
  activityLevel: ActivityLevel;
  goal: Goal;
}

export interface MacroDistribution {
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  protein_percent: number;
  carbs_percent: number;
  fat_percent: number;
}

export interface CalorieResult {
  bmr: number; // Basal Metabolic Rate
  tdee: number; // Total Daily Energy Expenditure
  targetCalories: number;
  macros: MacroDistribution;
}

// Коэффициенты активности
const activityMultipliers: Record<ActivityLevel, number> = {
  sedentary: 1.2, // Сидячий образ жизни
  light: 1.375, // Лёгкие упражнения 1-3 раза/неделю
  moderate: 1.55, // Умеренные упражнения 3-5 раз/неделю
  active: 1.725, // Интенсивные упражнения 6-7 раз/неделю
  very_active: 1.9, // Очень интенсивные упражнения, физическая работа
};

// Корректировка калорий в зависимости от цели
const goalAdjustments: Record<Goal, number> = {
  weight_loss: -500, // Дефицит 500 ккал/день (~0.5 кг/неделю)
  maintenance: 0,
  muscle_gain: 300, // Профицит 300 ккал/день
  keto: -300, // Небольшой дефицит для кето
};

// Распределение макронутриентов по целям (% от калорий)
const macroDistributions: Record<Goal, { protein: number; carbs: number; fat: number }> = {
  weight_loss: { protein: 35, carbs: 35, fat: 30 }, // Высокий белок
  maintenance: { protein: 25, carbs: 45, fat: 30 }, // Сбалансированное
  muscle_gain: { protein: 30, carbs: 45, fat: 25 }, // Высокие углеводы
  keto: { protein: 25, carbs: 5, fat: 70 }, // Кето-диета
};

/**
 * Рассчитать BMR (базовый обмен веществ) по формуле Mifflin-St Jeor
 */
function calculateBMR(gender: Gender, age: number, height: number, weight: number): number {
  let bmr: number;

  if (gender === 'male') {
    // Формула для мужчин: 10 × вес (кг) + 6.25 × рост (см) − 5 × возраст (лет) + 5
    bmr = 10 * weight + 6.25 * height - 5 * age + 5;
  } else {
    // Формула для женщин: 10 × вес (кг) + 6.25 × рост (см) − 5 × возраст (лет) − 161
    bmr = 10 * weight + 6.25 * height - 5 * age - 161;
  }

  return Math.round(bmr);
}

/**
 * Рассчитать TDEE (общий расход калорий)
 */
function calculateTDEE(bmr: number, activityLevel: ActivityLevel): number {
  const multiplier = activityMultipliers[activityLevel];
  return Math.round(bmr * multiplier);
}

/**
 * Рассчитать целевые калории с учётом цели
 */
function calculateTargetCalories(tdee: number, goal: Goal): number {
  const adjustment = goalAdjustments[goal];
  const target = tdee + adjustment;

  // Минимум 1200 ккал для женщин, 1500 для мужчин
  return Math.max(target, 1200);
}

/**
 * Рассчитать распределение макронутриентов
 */
function calculateMacros(targetCalories: number, goal: Goal): MacroDistribution {
  const distribution = macroDistributions[goal];

  // Калории из каждого макронутриента
  const proteinCalories = (targetCalories * distribution.protein) / 100;
  const carbsCalories = (targetCalories * distribution.carbs) / 100;
  const fatCalories = (targetCalories * distribution.fat) / 100;

  // Граммы (белки и углеводы = 4 ккал/г, жиры = 9 ккал/г)
  const protein_g = Math.round(proteinCalories / 4);
  const carbs_g = Math.round(carbsCalories / 4);
  const fat_g = Math.round(fatCalories / 9);

  return {
    protein_g,
    carbs_g,
    fat_g,
    protein_percent: distribution.protein,
    carbs_percent: distribution.carbs,
    fat_percent: distribution.fat,
  };
}

/**
 * Главная функция расчёта калорий
 */
export function calculateCalories(input: CalorieInput): CalorieResult {
  const bmr = calculateBMR(input.gender, input.age, input.height, input.weight);
  const tdee = calculateTDEE(bmr, input.activityLevel);
  const targetCalories = calculateTargetCalories(tdee, input.goal);
  const macros = calculateMacros(targetCalories, input.goal);

  return {
    bmr,
    tdee,
    targetCalories,
    macros,
  };
}

/**
 * Получить описание уровня активности
 */
export function getActivityLabel(level: ActivityLevel): string {
  const labels: Record<ActivityLevel, string> = {
    sedentary: 'Сидячий (офисная работа, нет тренировок)',
    light: 'Лёгкая (1-3 тренировки в неделю)',
    moderate: 'Умеренная (3-5 тренировок в неделю)',
    active: 'Высокая (6-7 тренировок в неделю)',
    very_active: 'Очень высокая (интенсивные тренировки + физическая работа)',
  };
  return labels[level];
}

/**
 * Получить описание цели
 */
export function getGoalLabel(goal: Goal): string {
  const labels: Record<Goal, string> = {
    weight_loss: 'Похудение (-0.5 кг/неделю)',
    maintenance: 'Поддержание веса',
    muscle_gain: 'Набор мышечной массы',
    keto: 'Кето-диета',
  };
  return labels[goal];
}
