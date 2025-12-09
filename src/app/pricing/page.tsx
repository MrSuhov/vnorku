'use client';

import { motion } from 'framer-motion';
import Link from 'next/link';
import { Check, X, ArrowRight } from 'lucide-react';

export default function PricingPage() {
  const plans = [
    {
      name: 'Free',
      price: '0₽',
      period: 'навсегда',
      description: 'Идеально для первого знакомства с сервисом',
      features: [
        { text: 'До 2 корзин в неделю', included: true },
        { text: 'Поиск в 2 сервисах доставки на ваш выбор', included: true },
        { text: 'Калькулятор калорий', included: true },
                { text: 'Поддержка в Telegram', included: true },
        { text: 'Поиск во всех локальных сервисах доставки', included: false },
        { text: 'Неограниченные корзины', included: false },
        { text: 'Персональный план питания', included: false },
        { text: 'Интеграция с фитнес-трекерами', included: false },
      ],
      cta: 'Начать бесплатно',
      href: 'https://t.me/Coffeematebot',
      popular: false,
      color: 'gray',
    },
    {
      name: 'Health',
      price: '199₽',
      period: 'в месяц',
      description: 'Полный контроль рациона для достижения целей',
      features: [
        { text: 'Неограниченные корзины', included: true },
        { text: 'Поиск во всех локальных сервисах доставки', included: true },
        { text: 'Персональный план питания', included: true },
                { text: 'Учёт макронутриентов (БЖУ)', included: true },
        { text: 'История заказов и статистика', included: true },
        { text: 'Приоритетная поддержка', included: true },
        { text: 'Экспорт данных в PDF', included: true },
        { text: 'Интеграция с Apple Health/Google Fit', included: false },
      ],
      cta: 'Выбрать Health',
      href: 'https://t.me/Coffeematebot',
      popular: true,
      color: 'primary',
    },
    {
      name: 'Health Pro',
      price: '499₽',
      period: 'в месяц',
      description: 'Максимальная персонализация и интеграции',
      features: [
        { text: 'Всё из тарифа Health, плюс:', included: true },
        { text: 'Интеграция с Apple Health', included: true },
        { text: 'Интеграция с Google Fit', included: true },
        { text: 'Автоматическая синхронизация активности', included: true },
        { text: 'Еженедельный PDF-отчёт по питанию', included: true },
                { text: 'Ранний доступ к новым фичам', included: true },
        { text: 'Персональный менеджер поддержки', included: true },
        { text: 'Консультация нутрициолога (1 раз/мес)', included: true },
      ],
      cta: 'Выбрать Health Pro',
      href: 'https://t.me/Coffeematebot',
      popular: false,
      color: 'accent',
    },
  ];

  const colorClasses = {
    gray: {
      border: 'border-gray-200',
      bg: 'bg-gray-500',
      bgHover: 'hover:bg-gray-600',
      text: 'text-gray-600',
      badge: 'bg-gray-100 text-gray-700',
    },
    primary: {
      border: 'border-primary-500',
      bg: 'bg-primary-500',
      bgHover: 'hover:bg-primary-600',
      text: 'text-primary-600',
      badge: 'bg-primary-100 text-primary-700',
    },
    accent: {
      border: 'border-accent-500',
      bg: 'bg-accent-500',
      bgHover: 'hover:bg-accent-600',
      text: 'text-accent-600',
      badge: 'bg-accent-100 text-accent-700',
    },
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      {/* Hero Section */}
      <section className="section-padding">
        <div className="container-custom">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-center max-w-3xl mx-auto mb-16"
          >
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-gray-900 mb-6">
              Выберите свой тариф
            </h1>
            <p className="text-lg md:text-xl text-gray-600">
              Начните бесплатно или получите полный доступ ко всем возможностям сервиса.
              Отменить подписку можно в любой момент.
            </p>
          </motion.div>

          {/* Pricing Cards */}
          <div className="grid gap-8 lg:grid-cols-3 max-w-7xl mx-auto mb-16">
            {plans.map((plan, index) => {
              const colors = colorClasses[plan.color as keyof typeof colorClasses];

              return (
                <motion.div
                  key={plan.name}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: index * 0.1 }}
                  className={`relative bg-white rounded-2xl p-8 shadow-lg hover:shadow-xl transition-all ${
                    plan.popular ? `ring-2 ${colors.border} scale-105 lg:scale-110` : ''
                  }`}
                >
                  {plan.popular && (
                    <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                      <span className={`${colors.bg} text-white text-sm font-semibold px-4 py-1 rounded-full`}>
                        Популярный выбор
                      </span>
                    </div>
                  )}

                  {/* Plan Header */}
                  <div className="mb-8">
                    <h3 className="text-2xl font-bold text-gray-900 mb-2">
                      {plan.name}
                    </h3>
                    <p className="text-sm text-gray-600 mb-6">
                      {plan.description}
                    </p>
                    <div className="flex items-baseline mb-2">
                      <span className="text-5xl font-bold text-gray-900">
                        {plan.price}
                      </span>
                      <span className="ml-2 text-gray-600">
                        /{plan.period}
                      </span>
                    </div>
                  </div>

                  {/* Features List */}
                  <ul className="space-y-4 mb-8">
                    {plan.features.map((feature, i) => (
                      <li key={i} className="flex items-start space-x-3">
                        {feature.included ? (
                          <Check className={`h-5 w-5 ${colors.text} flex-shrink-0 mt-0.5`} />
                        ) : (
                          <X className="h-5 w-5 text-gray-300 flex-shrink-0 mt-0.5" />
                        )}
                        <span className={`text-sm ${feature.included ? 'text-gray-700' : 'text-gray-400'}`}>
                          {feature.text}
                        </span>
                      </li>
                    ))}
                  </ul>

                  {/* CTA Button */}
                  <Link
                    href={plan.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`block w-full text-center rounded-lg px-6 py-3 font-semibold transition-colors ${
                      plan.popular
                        ? `${colors.bg} ${colors.bgHover} text-white`
                        : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
                    }`}
                  >
                    {plan.cta}
                  </Link>
                </motion.div>
              );
            })}
          </div>

          {/* Comparison Table */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="max-w-5xl mx-auto"
          >
            <h2 className="text-3xl font-bold text-gray-900 text-center mb-12">
              Детальное сравнение
            </h2>

            <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-4 px-6 font-semibold text-gray-900">
                        Функция
                      </th>
                      <th className="text-center py-4 px-6 font-semibold text-gray-900">
                        Free
                      </th>
                      <th className="text-center py-4 px-6 font-semibold text-primary-600 bg-primary-50">
                        Health
                      </th>
                      <th className="text-center py-4 px-6 font-semibold text-gray-900">
                        Health Pro
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    <tr>
                      <td className="py-4 px-6 text-sm text-gray-700">Корзин в неделю</td>
                      <td className="py-4 px-6 text-center text-sm">До 2</td>
                      <td className="py-4 px-6 text-center text-sm bg-primary-50">Неограничено</td>
                      <td className="py-4 px-6 text-center text-sm">Неограничено</td>
                    </tr>
                    <tr>
                      <td className="py-4 px-6 text-sm text-gray-700">Сервисов доставки</td>
                      <td className="py-4 px-6 text-center text-sm">3</td>
                      <td className="py-4 px-6 text-center text-sm bg-primary-50">10+</td>
                      <td className="py-4 px-6 text-center text-sm">10+</td>
                    </tr>
                    <tr>
                      <td className="py-4 px-6 text-sm text-gray-700">Точность калорий</td>
                      <td className="py-4 px-6 text-center text-sm">±5%</td>
                      <td className="py-4 px-6 text-center text-sm bg-primary-50">±5%</td>
                      <td className="py-4 px-6 text-center text-sm">±5%</td>
                    </tr>
                    <tr>
                      <td className="py-4 px-6 text-sm text-gray-700">История заказов</td>
                      <td className="py-4 px-6 text-center">
                        <X className="h-5 w-5 text-gray-300 mx-auto" />
                      </td>
                      <td className="py-4 px-6 text-center bg-primary-50">
                        <Check className="h-5 w-5 text-primary-500 mx-auto" />
                      </td>
                      <td className="py-4 px-6 text-center">
                        <Check className="h-5 w-5 text-primary-500 mx-auto" />
                      </td>
                    </tr>
                    <tr>
                      <td className="py-4 px-6 text-sm text-gray-700">Интеграция с фитнес-трекерами</td>
                      <td className="py-4 px-6 text-center">
                        <X className="h-5 w-5 text-gray-300 mx-auto" />
                      </td>
                      <td className="py-4 px-6 text-center bg-primary-50">
                        <X className="h-5 w-5 text-gray-300 mx-auto" />
                      </td>
                      <td className="py-4 px-6 text-center">
                        <Check className="h-5 w-5 text-primary-500 mx-auto" />
                      </td>
                    </tr>
                    <tr>
                      <td className="py-4 px-6 text-sm text-gray-700">API-доступ</td>
                      <td className="py-4 px-6 text-center">
                        <X className="h-5 w-5 text-gray-300 mx-auto" />
                      </td>
                      <td className="py-4 px-6 text-center bg-primary-50">
                        <X className="h-5 w-5 text-gray-300 mx-auto" />
                      </td>
                      <td className="py-4 px-6 text-center">
                        <Check className="h-5 w-5 text-primary-500 mx-auto" />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </motion.div>

          {/* FAQ Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.6 }}
            className="mt-20 max-w-3xl mx-auto"
          >
            <h2 className="text-3xl font-bold text-gray-900 text-center mb-12">
              Вопросы по тарифам
            </h2>

            <div className="space-y-6">
              <div className="bg-white rounded-xl p-6 shadow-sm">
                <h3 className="font-semibold text-gray-900 mb-2">
                  Можно ли отменить подписку?
                </h3>
                <p className="text-gray-600 text-sm">
                  Да, вы можете отменить подписку в любой момент через бота в Telegram.
                  После отмены доступ к платным функциям сохраняется до конца оплаченного периода.
                </p>
              </div>

              <div className="bg-white rounded-xl p-6 shadow-sm">
                <h3 className="font-semibold text-gray-900 mb-2">
                  Есть ли пробный период для платных тарифов?
                </h3>
                <p className="text-gray-600 text-sm">
                  Бесплатный тариф позволяет попробовать основной функционал сервиса.
                  Для платных тарифов мы предлагаем 7 дней возврата средств, если сервис вам не подошёл.
                </p>
              </div>

              <div className="bg-white rounded-xl p-6 shadow-sm">
                <h3 className="font-semibold text-gray-900 mb-2">
                  Можно ли перейти с одного тарифа на другой?
                </h3>
                <p className="text-gray-600 text-sm">
                  Да, вы можете перейти на другой тариф в любой момент. При переходе на более дорогой тариф
                  мы пересчитаем стоимость пропорционально оставшимся дням текущего периода.
                </p>
              </div>
            </div>
          </motion.div>

          {/* CTA */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.8 }}
            className="mt-16 text-center"
          >
            <Link
              href="https://t.me/Coffeematebot"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center rounded-lg bg-primary-500 px-8 py-4 text-lg font-semibold text-white hover:bg-primary-600 transition-colors shadow-lg hover:shadow-xl"
            >
              Начать бесплатно
              <ArrowRight className="ml-2 h-5 w-5" />
            </Link>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
