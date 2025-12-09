'use client';

import { motion } from 'framer-motion';
import { XCircle } from 'lucide-react';

export default function ProblemSection() {
  const problems = [
    {
      title: 'Считать калории самому — утомительно',
      description: 'Каждый раз вручную искать калорийность продуктов, взвешивать порции, вести таблицы...',
    },
    {
      title: 'Ассортимент разбросан по 10+ сервисам доставки',
      description: 'У кого представлен весь необходимый ассортимент? Сколько времени я потрачу на сравнение ассортимента?',
    },
    {
      title: 'План по питанию нарушается',
      description: 'Купил лишнего или не то — и вот уже +200 ккал сверх нормы. А завтра — опять срыв.',
    },
    {
      title: 'Товар закончился',
      description: 'Пока собирал корзину товар закончился. Теперь заново нужно считать калории с новыми продуктами и собирать новую корзину.',
    },
  ];

  return (
    <section className="section-padding bg-gray-50">
      <div className="container-custom">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
            Знакомо?
          </h2>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Контролировать рацион и экономить время — сложно и отнимает много сил
          </p>
        </motion.div>

        <div className="grid gap-6 md:grid-cols-2 lg:gap-8">
          {problems.map((problem, index) => (
            <motion.div
              key={problem.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              className="bg-white rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0">
                  <XCircle className="h-6 w-6 text-red-500" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 mb-2">
                    {problem.title}
                  </h3>
                  <p className="text-gray-600 text-sm">
                    {problem.description}
                  </p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
