'use client';

import { motion } from 'framer-motion';
import { MessageSquare, Search, ShoppingCart, CheckCircle } from 'lucide-react';

export default function HowItWorksSection() {
  const steps = [
    {
      icon: MessageSquare,
      title: 'Укажите цель',
      description: 'Укажите вашу ежемесячную цель по калоражу — сервис рассчитает ваш план по неделям и дням',
      color: 'primary',
    },
    {
      icon: Search,
      title: 'Сделайте заказ',
      description: 'Сервис автоматически подберёт корзины и оценит прогресс по вашему еженедельному плану',
      color: 'accent',
    },
    {
      icon: ShoppingCart,
      title: 'Получаете корзины',
      description: 'За 2 минуты вы видите 3 оптимальных варианта с точным соответствием вашему плану (±5%)',
      color: 'orange',
    },
    {
      icon: CheckCircle,
      title: 'Переходите и заказываете',
      description: 'Переходя по ссылке товара — вы попадаете в приложение магазина, где добавляете товар в корзину и оплачиваете.',
      color: 'green',
    },
  ];

  const colorClasses = {
    primary: {
      bg: 'bg-primary-500',
      bgLight: 'bg-primary-50',
      text: 'text-primary-600',
      border: 'border-primary-200',
    },
    accent: {
      bg: 'bg-accent-500',
      bgLight: 'bg-accent-50',
      text: 'text-accent-600',
      border: 'border-accent-200',
    },
    orange: {
      bg: 'bg-accent-500',
      bgLight: 'bg-accent-50',
      text: 'text-accent-600',
      border: 'border-accent-200',
    },
    green: {
      bg: 'bg-pea-500',
      bgLight: 'bg-pea-50',
      text: 'text-pea-600',
      border: 'border-pea-200',
    },
  };

  return (
    <section id="how-it-works" className="section-padding bg-gray-50">
      <div className="container-custom">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-gray-900 mb-6">
            Как это работает?
          </h2>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Всего 4 простых шага от цели до готовой корзины
          </p>
        </motion.div>

        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, index) => {
            const Icon = step.icon;
            const colors = colorClasses[step.color as keyof typeof colorClasses];

            return (
              <motion.div
                key={step.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="relative"
              >
                {/* Connector Line (not on last item) */}
                {index < steps.length - 1 && (
                  <div className="hidden lg:block absolute top-12 left-[60%] w-[80%] h-0.5 bg-gradient-to-r from-gray-300 to-transparent" />
                )}

                <div className="bg-white rounded-2xl p-6 shadow-sm hover:shadow-lg transition-all h-full">
                  {/* Step Number */}
                  <div className="flex items-center justify-between mb-4">
                    <div className={`${colors.bg} rounded-full p-3`}>
                      <Icon className="h-6 w-6 text-white" />
                    </div>
                    <div className={`text-2xl font-bold ${colors.text}`}>
                      {index + 1}
                    </div>
                  </div>

                  <h3 className="text-lg font-bold text-gray-900 mb-2">
                    {step.title}
                  </h3>
                  <p className="text-sm text-gray-600">
                    {step.description}
                  </p>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="mt-12 text-center"
        >
          <a
            href="https://t.me/Coffeematebot"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center rounded-lg bg-gradient-to-r from-primary-500 to-primary-600 px-8 py-4 text-lg font-semibold text-white hover:from-primary-600 hover:to-primary-700 transition-all shadow-lg hover:shadow-glow-primary"
          >
            Попробовать прямо сейчас
          </a>
          <p className="mt-4 text-sm text-gray-600">
            Начните с бесплатного тарифа
          </p>
        </motion.div>
      </div>
    </section>
  );
}
