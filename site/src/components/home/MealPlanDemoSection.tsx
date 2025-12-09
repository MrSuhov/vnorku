'use client';

import { motion } from 'framer-motion';

interface MealItem {
  meal: string;
  foods: string;
  calories: number;
  protein: number;
  fats: number;
  carbs: number;
}

export default function MealPlanDemoSection() {
  const dailyPlan: MealItem[] = [
    {
      meal: 'Завтрак',
      foods: 'Овсянка с бананом и орехами',
      calories: 420,
      protein: 12,
      fats: 14,
      carbs: 62,
    },
    {
      meal: 'Обед',
      foods: 'Куриная грудка с рисом и овощами',
      calories: 580,
      protein: 45,
      fats: 12,
      carbs: 65,
    },
    {
      meal: 'Перекус',
      foods: 'Греческий йогурт с ягодами',
      calories: 180,
      protein: 15,
      fats: 5,
      carbs: 18,
    },
    {
      meal: 'Ужин',
      foods: 'Лосось с киноа и брокколи',
      calories: 520,
      protein: 38,
      fats: 22,
      carbs: 42,
    },
  ];

  const totals = dailyPlan.reduce(
    (acc, item) => ({
      calories: acc.calories + item.calories,
      protein: acc.protein + item.protein,
      fats: acc.fats + item.fats,
      carbs: acc.carbs + item.carbs,
    }),
    { calories: 0, protein: 0, fats: 0, carbs: 0 }
  );

  const goals = { calories: 1800, protein: 120, fats: 60, carbs: 200 };

  const getProgress = (current: number, goal: number) => Math.min((current / goal) * 100, 100);

  return (
    <section className="section-padding bg-white">
      <div className="container-custom">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
            Создавайте ваши персональные планы по питанию и достигайте целей
          </h2>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Дневной/недельный/месячный рацион с точным расчётом калорий и БЖУ
          </p>
        </motion.div>

        {/* Meal Plan Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="max-w-4xl mx-auto mb-12"
        >
          <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-100">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-gradient-to-r from-primary-50 to-accent-50">
                    <th className="text-left py-4 px-6 font-semibold text-gray-900">Приём пищи</th>
                    <th className="text-left py-4 px-6 font-semibold text-gray-900 hidden sm:table-cell">Продукты</th>
                    <th className="text-center py-4 px-3 font-semibold text-gray-900">Ккал</th>
                    <th className="text-center py-4 px-3 font-semibold text-primary-600">Б</th>
                    <th className="text-center py-4 px-3 font-semibold text-accent-600">Ж</th>
                    <th className="text-center py-4 px-3 font-semibold text-pea-600">У</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {dailyPlan.map((item, index) => (
                    <motion.tr
                      key={item.meal}
                      initial={{ opacity: 0, x: -20 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.4, delay: 0.1 * index }}
                      className="hover:bg-gray-50 transition-colors"
                    >
                      <td className="py-4 px-6">
                        <div className="font-medium text-gray-900">{item.meal}</div>
                        <div className="text-sm text-gray-500 sm:hidden">{item.foods}</div>
                      </td>
                      <td className="py-4 px-6 text-sm text-gray-600 hidden sm:table-cell">{item.foods}</td>
                      <td className="py-4 px-3 text-center font-medium text-gray-900">{item.calories}</td>
                      <td className="py-4 px-3 text-center text-primary-600">{item.protein}г</td>
                      <td className="py-4 px-3 text-center text-accent-600">{item.fats}г</td>
                      <td className="py-4 px-3 text-center text-pea-600">{item.carbs}г</td>
                    </motion.tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="bg-gray-50 font-semibold">
                    <td className="py-4 px-6 text-gray-900">Итого</td>
                    <td className="py-4 px-6 hidden sm:table-cell"></td>
                    <td className="py-4 px-3 text-center text-gray-900">{totals.calories}</td>
                    <td className="py-4 px-3 text-center text-primary-600">{totals.protein}г</td>
                    <td className="py-4 px-3 text-center text-accent-600">{totals.fats}г</td>
                    <td className="py-4 px-3 text-center text-pea-600">{totals.carbs}г</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </motion.div>

        {/* Progress Bars */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="max-w-2xl mx-auto"
        >
          <h3 className="text-xl font-semibold text-gray-900 text-center mb-6">
            Прогресс выполнения дневного плана
          </h3>
          <div className="space-y-6">
            {/* Calories */}
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">Калории</span>
                <span className="text-sm text-gray-600">{totals.calories} / {goals.calories} ккал</span>
              </div>
              <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  whileInView={{ width: `${getProgress(totals.calories, goals.calories)}%` }}
                  viewport={{ once: true }}
                  transition={{ duration: 1, delay: 0.5 }}
                  className="h-full bg-gradient-to-r from-gray-600 to-gray-700 rounded-full"
                />
              </div>
            </div>

            {/* Protein */}
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">Белки</span>
                <span className="text-sm text-gray-600">{totals.protein} / {goals.protein} г</span>
              </div>
              <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  whileInView={{ width: `${getProgress(totals.protein, goals.protein)}%` }}
                  viewport={{ once: true }}
                  transition={{ duration: 1, delay: 0.6 }}
                  className="h-full bg-gradient-to-r from-primary-400 to-primary-600 rounded-full"
                />
              </div>
            </div>

            {/* Fats */}
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">Жиры</span>
                <span className="text-sm text-gray-600">{totals.fats} / {goals.fats} г</span>
              </div>
              <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  whileInView={{ width: `${getProgress(totals.fats, goals.fats)}%` }}
                  viewport={{ once: true }}
                  transition={{ duration: 1, delay: 0.7 }}
                  className="h-full bg-gradient-to-r from-accent-400 to-accent-600 rounded-full"
                />
              </div>
            </div>

            {/* Carbs */}
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">Углеводы</span>
                <span className="text-sm text-gray-600">{totals.carbs} / {goals.carbs} г</span>
              </div>
              <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  whileInView={{ width: `${getProgress(totals.carbs, goals.carbs)}%` }}
                  viewport={{ once: true }}
                  transition={{ duration: 1, delay: 0.8 }}
                  className="h-full bg-gradient-to-r from-pea-400 to-pea-600 rounded-full"
                />
              </div>
            </div>
          </div>

          {/* Accuracy Badge */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 1 }}
            className="mt-8 text-center"
          >
            <div className="inline-flex items-center bg-pea-50 border border-pea-200 rounded-full px-6 py-3">
              <span className="text-pea-700 font-medium">
                Точность соблюдения плана: <span className="font-bold text-pea-600">94.4%</span> (в пределах ±5%)
              </span>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
