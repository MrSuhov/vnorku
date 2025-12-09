'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { Check, ArrowRight } from 'lucide-react';

export default function PricingPreviewSection() {
  const plans = [
    {
      name: 'Free',
      price: '0₽',
      period: 'бесплатно',
      description: 'Попробуйте основной функционал',
      features: [
        'До 2 корзин в неделю',
        'Поиск в 2 сервисах доставки на ваш выбор',
        'Калькулятор калорий',
      ],
      cta: 'Начать бесплатно',
      href: 'https://t.me/Coffeematebot',
      popular: false,
    },
    {
      name: 'Health',
      price: '199₽',
      period: 'в месяц',
      description: 'Полный контроль рациона',
      features: [
        'Неограниченные корзины',
        'Поиск во всех локальных сервисах доставки',
        'Персональный план питания',
        'История заказов',
        'Приоритетная поддержка',
      ],
      cta: 'Выбрать Health',
      href: '/pricing',
      popular: true,
    },
    {
      name: 'Health Pro',
      price: '499₽',
      period: 'в месяц',
      description: 'Для серьёзных целей',
      features: [
        'Всё из Health, плюс:',
        'Интеграция с Apple Health/Google Fit',
        'Еженедельный PDF-отчёт',
        'Ранний доступ к новым фичам',
      ],
      cta: 'Выбрать Health Pro',
      href: '/pricing',
      popular: false,
    },
  ];

  return (
    <section className="section-padding bg-gradient-to-b from-primary-50/30 to-white">
      <div className="container-custom">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-gray-900 mb-6">
            Выберите свой план
          </h2>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Начните бесплатно или выберите план для полного контроля рациона
          </p>
        </motion.div>

        <div className="grid gap-8 md:grid-cols-3 max-w-6xl mx-auto">
          {plans.map((plan, index) => (
            <motion.div
              key={plan.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              className={`relative bg-white rounded-2xl p-8 shadow-lg hover:shadow-xl transition-all ${
                plan.popular ? 'ring-2 ring-primary-500' : ''
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="bg-primary-500 text-white text-sm font-semibold px-4 py-1 rounded-full">
                    Популярный
                  </span>
                </div>
              )}

              <div className="mb-6">
                <h3 className="text-2xl font-bold text-gray-900 mb-2">
                  {plan.name}
                </h3>
                <p className="text-gray-600 text-sm mb-4">
                  {plan.description}
                </p>
                <div className="flex items-baseline">
                  <span className="text-4xl font-bold text-gray-900">
                    {plan.price}
                  </span>
                  <span className="ml-2 text-gray-600">
                    /{plan.period}
                  </span>
                </div>
              </div>

              <ul className="space-y-3 mb-8">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start space-x-3">
                    <Check className="h-5 w-5 text-pea-500 flex-shrink-0 mt-0.5" />
                    <span className="text-gray-700 text-sm">{feature}</span>
                  </li>
                ))}
              </ul>

              <Link
                href={plan.href}
                target={plan.href.startsWith('http') ? '_blank' : undefined}
                rel={plan.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                className={`block w-full text-center rounded-lg px-6 py-3 font-semibold transition-colors ${
                  plan.popular
                    ? 'bg-primary-500 text-white hover:bg-primary-600'
                    : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
                }`}
              >
                {plan.cta}
              </Link>
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mt-12 text-center"
        >
          <Link
            href="/pricing"
            className="inline-flex items-center text-primary-600 hover:text-primary-700 font-medium"
          >
            Подробное сравнение тарифов
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
