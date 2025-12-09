'use client';

import { motion } from 'framer-motion';
import { Target, Clock, DollarSign, Heart, Shield, Zap } from 'lucide-react';

export default function BenefitsSection() {
  const benefits = [
    {
      icon: Target,
      title: 'Точность ±5%',
      description: 'Гарантируем соблюдение вашего плана по калориям и макронутриентам',
    },
    {
      icon: Clock,
      title: 'Экономия времени',
      description: 'Готовая корзина за 2 минуты вместо 30 минут поиска',
    },
    {
      icon: DollarSign,
      title: 'Экономия денег',
      description: 'До 30% экономии на доставке и стоимости продуктов',
    },
    {
      icon: Heart,
      title: 'Здоровье',
      description: 'Сбалансированный рацион без подсчёта калорий вручную',
    },
    {
      icon: Shield,
      title: 'Безопасность',
      description: 'Не храним данные карт, работаем через партнёров',
    },
    {
      icon: Zap,
      title: 'Удобство',
      description: 'Всё в Telegram — не нужно устанавливать приложение',
    },
  ];

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
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-gray-900 mb-6">
            Почему выбирают Внорку?
          </h2>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Мы объединили лучшее: точность нутрициолога и скорость обработки заказа
          </p>
        </motion.div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {benefits.map((benefit, index) => {
            const Icon = benefit.icon;

            return (
              <motion.div
                key={benefit.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="group bg-white rounded-xl p-6 border-2 border-gray-100 hover:border-primary-200 hover:shadow-lg transition-all"
              >
                <div className="mb-4">
                  <div className="inline-flex items-center justify-center rounded-lg bg-primary-50 p-3 group-hover:bg-primary-100 transition-colors">
                    <Icon className="h-6 w-6 text-primary-600" />
                  </div>
                </div>
                <h3 className="text-lg font-bold text-gray-900 mb-2">
                  {benefit.title}
                </h3>
                <p className="text-gray-600 text-sm">
                  {benefit.description}
                </p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
