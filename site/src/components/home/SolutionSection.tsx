'use client';

import { motion } from 'framer-motion';
import { Target, Sparkles, TrendingDown } from 'lucide-react';

export default function SolutionSection() {
  return (
    <section className="section-padding bg-white">
      <div className="container-custom">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center space-x-2 bg-gradient-to-r from-primary-100 to-accent-100 text-primary-700 rounded-full px-4 py-2 mb-6">
            <Sparkles className="h-4 w-4" />
            <span className="text-sm font-medium">Решение</span>
          </div>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-gray-900 mb-6">
            Внорку берёт всё на себя
          </h2>
          <p className="text-lg text-gray-600 max-w-3xl mx-auto">
            Вы говорите цель (похудение, кето, своя программа...) — наши алгоритмы автоматически подберут оптимальную корзину продуктов, которая{' '}
            <span className="font-semibold text-primary-600">точно соответствует вашему плану</span> по калориям и макронутриентам
          </p>
        </motion.div>

        <div className="grid gap-8 md:grid-cols-3">
          {/* Card 1 */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="relative bg-gradient-to-br from-primary-50 to-white rounded-2xl p-8 shadow-lg hover:shadow-xl transition-shadow"
          >
            <div className="absolute -top-4 -right-4 bg-primary-500 rounded-full p-3">
              <Target className="h-8 w-8 text-white" />
            </div>
            <div className="mt-4">
              <h3 className="text-xl font-bold text-gray-900 mb-3">
                Гарантия точности ±5%
              </h3>
              <p className="text-gray-600">
                Наш алгоритм подбирает продукты так, чтобы калораж и макросы (белки/жиры/углеводы) соответствовали вашему плану с отклонением{' '}
                <span className="font-semibold">не более 5%</span>
              </p>
            </div>
            <div className="mt-6 bg-white rounded-lg p-4 shadow-sm">
              <div className="text-xs text-gray-600 mb-2">Пример для цели 2200 ккал:</div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-700">Калории:</span>
                  <span className="font-semibold text-primary-600">2,195 ккал</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-700">Белки:</span>
                  <span className="font-semibold">140г (целевой 137г)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-700">Отклонение:</span>
                  <span className="font-semibold text-pea-600">-0.2%</span>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Card 2 */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="relative bg-gradient-to-br from-accent-50 to-white rounded-2xl p-8 shadow-lg hover:shadow-xl transition-shadow"
          >
            <div className="absolute -top-4 -right-4 bg-accent-500 rounded-full p-3">
              <Sparkles className="h-8 w-8 text-white" />
            </div>
            <div className="mt-4">
              <h3 className="text-xl font-bold text-gray-900 mb-3">
                Автоматический поиск
              </h3>
              <p className="text-gray-600">
                Мы автоматически проверяем ассортимент и наличие в сервисах доставки и предложим лучшие варианты для вас
              </p>
            </div>
            <div className="mt-6">
              <p className="text-sm text-accent-600 font-medium">
                Локальные сервисы доставки еды
              </p>
            </div>
          </motion.div>

          {/* Card 3 */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="relative bg-gradient-to-br from-pea-50 to-white rounded-2xl p-8 shadow-lg hover:shadow-xl transition-shadow"
          >
            <div className="absolute -top-4 -right-4 bg-pea-500 rounded-full p-3">
              <TrendingDown className="h-8 w-8 text-white" />
            </div>
            <div className="mt-4">
              <h3 className="text-xl font-bold text-gray-900 mb-3">
                Оптимизация корзин
              </h3>
              <p className="text-gray-600">
                Алгоритм учитывает стоимость доставки и не будет предлагать заказывать один йогурт с доставкой
              </p>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
