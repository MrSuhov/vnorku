'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Calculator, User, Ruler, Weight, Activity, Target, TrendingDown, ArrowRight } from 'lucide-react';
import {
  calculateCalories,
  getActivityLabel,
  getGoalLabel,
  type Gender,
  type ActivityLevel,
  type Goal,
  type CalorieResult,
} from '@/lib/calories';

export default function CalculatorPage() {
  const [gender, setGender] = useState<Gender>('male');
  const [age, setAge] = useState<string>('30');
  const [height, setHeight] = useState<string>('175');
  const [weight, setWeight] = useState<string>('75');
  const [activityLevel, setActivityLevel] = useState<ActivityLevel>('moderate');
  const [goal, setGoal] = useState<Goal>('weight_loss');
  const [result, setResult] = useState<CalorieResult | null>(null);

  const handleCalculate = () => {
    const ageNum = parseInt(age);
    const heightNum = parseInt(height);
    const weightNum = parseInt(weight);

    if (isNaN(ageNum) || isNaN(heightNum) || isNaN(weightNum)) {
      alert('Пожалуйста, заполните все поля корректно');
      return;
    }

    if (ageNum < 18 || ageNum > 100) {
      alert('Возраст должен быть от 18 до 100 лет');
      return;
    }

    if (heightNum < 120 || heightNum > 250) {
      alert('Рост должен быть от 120 до 250 см');
      return;
    }

    if (weightNum < 30 || weightNum > 300) {
      alert('Вес должен быть от 30 до 300 кг');
      return;
    }

    const calculatedResult = calculateCalories({
      gender,
      age: ageNum,
      height: heightNum,
      weight: weightNum,
      activityLevel,
      goal,
    });

    setResult(calculatedResult);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      <section className="section-padding">
        <div className="container-custom">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-center max-w-3xl mx-auto mb-12"
          >
            <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-100 rounded-2xl mb-6">
              <Calculator className="h-8 w-8 text-primary-600" />
            </div>
            <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              Калькулятор калорий
            </h1>
            <p className="text-lg text-gray-600">
              Рассчитайте свою дневную норму калорий и макронутриентов по формуле Mifflin-St Jeor
            </p>
          </motion.div>

          <div className="grid gap-8 lg:grid-cols-2 max-w-6xl mx-auto">
            {/* Calculator Form */}
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="bg-white rounded-2xl p-8 shadow-lg"
            >
              <h2 className="text-2xl font-bold text-gray-900 mb-6">
                Ваши данные
              </h2>

              <div className="space-y-6">
                {/* Gender */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">
                    <User className="inline h-4 w-4 mr-2" />
                    Пол
                  </label>
                  <div className="grid grid-cols-2 gap-4">
                    <button
                      onClick={() => setGender('male')}
                      className={`py-3 px-4 rounded-lg border-2 font-medium transition-colors ${
                        gender === 'male'
                          ? 'border-primary-500 bg-primary-50 text-primary-700'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      Мужской
                    </button>
                    <button
                      onClick={() => setGender('female')}
                      className={`py-3 px-4 rounded-lg border-2 font-medium transition-colors ${
                        gender === 'female'
                          ? 'border-primary-500 bg-primary-50 text-primary-700'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      Женский
                    </button>
                  </div>
                </div>

                {/* Age */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <User className="inline h-4 w-4 mr-2" />
                    Возраст (лет)
                  </label>
                  <input
                    type="number"
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                    className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-primary-500 focus:ring-0 outline-none transition-colors"
                    placeholder="30"
                    min="18"
                    max="100"
                  />
                </div>

                {/* Height */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Ruler className="inline h-4 w-4 mr-2" />
                    Рост (см)
                  </label>
                  <input
                    type="number"
                    value={height}
                    onChange={(e) => setHeight(e.target.value)}
                    className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-primary-500 focus:ring-0 outline-none transition-colors"
                    placeholder="175"
                    min="120"
                    max="250"
                  />
                </div>

                {/* Weight */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Weight className="inline h-4 w-4 mr-2" />
                    Вес (кг)
                  </label>
                  <input
                    type="number"
                    value={weight}
                    onChange={(e) => setWeight(e.target.value)}
                    className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-primary-500 focus:ring-0 outline-none transition-colors"
                    placeholder="75"
                    min="30"
                    max="300"
                  />
                </div>

                {/* Activity Level */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Activity className="inline h-4 w-4 mr-2" />
                    Уровень активности
                  </label>
                  <select
                    value={activityLevel}
                    onChange={(e) => setActivityLevel(e.target.value as ActivityLevel)}
                    className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-primary-500 focus:ring-0 outline-none transition-colors bg-white"
                  >
                    <option value="sedentary">{getActivityLabel('sedentary')}</option>
                    <option value="light">{getActivityLabel('light')}</option>
                    <option value="moderate">{getActivityLabel('moderate')}</option>
                    <option value="active">{getActivityLabel('active')}</option>
                    <option value="very_active">{getActivityLabel('very_active')}</option>
                  </select>
                </div>

                {/* Goal */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Target className="inline h-4 w-4 mr-2" />
                    Цель
                  </label>
                  <select
                    value={goal}
                    onChange={(e) => setGoal(e.target.value as Goal)}
                    className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-primary-500 focus:ring-0 outline-none transition-colors bg-white"
                  >
                    <option value="weight_loss">{getGoalLabel('weight_loss')}</option>
                    <option value="maintenance">{getGoalLabel('maintenance')}</option>
                    <option value="muscle_gain">{getGoalLabel('muscle_gain')}</option>
                    <option value="keto">{getGoalLabel('keto')}</option>
                  </select>
                </div>

                {/* Calculate Button */}
                <button
                  onClick={handleCalculate}
                  className="w-full bg-primary-500 hover:bg-primary-600 text-white font-semibold py-4 px-6 rounded-lg transition-colors flex items-center justify-center"
                >
                  <Calculator className="h-5 w-5 mr-2" />
                  Рассчитать
                </button>
              </div>
            </motion.div>

            {/* Results */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.4 }}
            >
              {result ? (
                <div className="bg-gradient-to-br from-primary-50 to-accent-50 rounded-2xl p-8 shadow-lg">
                  <h2 className="text-2xl font-bold text-gray-900 mb-6">
                    Ваш план питания
                  </h2>

                  <div className="space-y-6">
                    {/* Target Calories */}
                    <div className="bg-white rounded-xl p-6 shadow-sm">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-gray-600">
                          Целевые калории в день
                        </span>
                        <TrendingDown className="h-5 w-5 text-primary-500" />
                      </div>
                      <div className="text-4xl font-bold text-primary-600">
                        {result.targetCalories} ккал
                      </div>
                      <p className="text-sm text-gray-500 mt-2">
                        {getGoalLabel(goal)}
                      </p>
                    </div>

                    {/* BMR & TDEE */}
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-white rounded-xl p-4 shadow-sm">
                        <div className="text-sm text-gray-600 mb-1">BMR</div>
                        <div className="text-2xl font-bold text-gray-900">
                          {result.bmr}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          Базовый обмен
                        </div>
                      </div>
                      <div className="bg-white rounded-xl p-4 shadow-sm">
                        <div className="text-sm text-gray-600 mb-1">TDEE</div>
                        <div className="text-2xl font-bold text-gray-900">
                          {result.tdee}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          Общий расход
                        </div>
                      </div>
                    </div>

                    {/* Macros */}
                    <div className="bg-white rounded-xl p-6 shadow-sm">
                      <h3 className="font-semibold text-gray-900 mb-4">
                        Макронутриенты (БЖУ)
                      </h3>
                      <div className="space-y-4">
                        <div>
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-sm text-gray-700">Белки</span>
                            <span className="font-semibold text-gray-900">
                              {result.macros.protein_g}г ({result.macros.protein_percent}%)
                            </span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-blue-500 h-2 rounded-full"
                              style={{ width: `${result.macros.protein_percent}%` }}
                            />
                          </div>
                        </div>

                        <div>
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-sm text-gray-700">Жиры</span>
                            <span className="font-semibold text-gray-900">
                              {result.macros.fat_g}г ({result.macros.fat_percent}%)
                            </span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-yellow-500 h-2 rounded-full"
                              style={{ width: `${result.macros.fat_percent}%` }}
                            />
                          </div>
                        </div>

                        <div>
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-sm text-gray-700">Углеводы</span>
                            <span className="font-semibold text-gray-900">
                              {result.macros.carbs_g}г ({result.macros.carbs_percent}%)
                            </span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-green-500 h-2 rounded-full"
                              style={{ width: `${result.macros.carbs_percent}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* CTA */}
                    <div className="bg-white rounded-xl p-6 shadow-sm text-center">
                      <p className="text-gray-700 mb-4">
                        Готовы получать корзины, которые точно соответствуют этому плану?
                      </p>
                      <a
                        href="https://t.me/Coffeematebot"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center justify-center bg-primary-500 hover:bg-primary-600 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
                      >
                        Начать в Telegram
                        <ArrowRight className="ml-2 h-5 w-5" />
                      </a>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-white rounded-2xl p-8 shadow-lg h-full flex flex-col items-center justify-center text-center">
                  <div className="w-24 h-24 bg-gray-100 rounded-full flex items-center justify-center mb-6">
                    <Calculator className="h-12 w-12 text-gray-400" />
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">
                    Заполните форму
                  </h3>
                  <p className="text-gray-600">
                    Введите ваши данные слева и нажмите "Рассчитать", чтобы получить персональный план питания
                  </p>
                </div>
              )}
            </motion.div>
          </div>

          {/* Info Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.6 }}
            className="mt-16 max-w-4xl mx-auto"
          >
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-6">
              <h3 className="font-semibold text-blue-900 mb-3">
                ℹ️ О формуле Mifflin-St Jeor
              </h3>
              <p className="text-sm text-blue-800 leading-relaxed">
                Эта формула считается одной из наиболее точных для расчёта базового обмена веществ (BMR).
                Она учитывает ваш пол, возраст, рост и вес. Затем BMR умножается на коэффициент активности
                для получения общего расхода калорий (TDEE). В зависимости от вашей цели мы корректируем
                калорийность: для похудения создаём дефицит 500 ккал/день, для набора массы — профицит 300 ккал/день.
              </p>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
