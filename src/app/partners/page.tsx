'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Handshake, TrendingUp, Users, Zap, CheckCircle, ArrowRight, Mail } from 'lucide-react';

export default function PartnersPage() {
  const [formData, setFormData] = useState({
    companyName: '',
    contactName: '',
    email: '',
    phone: '',
    hasAPI: 'yes',
    message: '',
  });

  const [isSubmitted, setIsSubmitted] = useState(false);

  const benefits = [
    {
      icon: TrendingUp,
      title: 'Рост GMV на 15-25%',
      description: 'Наши пользователи приходят с готовыми корзинами на сумму 2,500-3,500₽, что значительно выше среднего чека',
    },
    {
      icon: Users,
      title: 'Готовая аудитория с высокой конверсией',
      description: 'Пользователи Внорку мотивированы покупать — они уже рассчитали план питания и знают, что им нужно',
    },
    {
      icon: Zap,
      title: 'Бесшовная интеграция',
      description: 'Простое REST API для добавления товаров в корзину и перехода к оформлению заказа',
    },
    {
      icon: CheckCircle,
      title: 'Без дополнительных затрат',
      description: 'Партнёрство бесплатное — вы платите только стандартные комиссии вашей платформы',
    },
  ];

  const requirements = [
    {
      title: 'REST API для работы с корзиной',
      description: 'GET /products — получение списка товаров с ценами и наличием',
      status: 'required',
    },
    {
      title: 'Поддержка глубоких ссылок (Deep Links)',
      description: 'Возможность открыть корзину с предзаполненными товарами через URL',
      status: 'required',
    },
    {
      title: 'Актуализация данных',
      description: 'Обновление цен и наличия в режиме реального времени или по расписанию',
      status: 'required',
    },
    {
      title: 'Данные о доставке',
      description: 'Информация о стоимости и условиях доставки в зависимости от адреса',
      status: 'optional',
    },
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // В production здесь будет отправка на /api/partnership-request
    console.log('Form submitted:', formData);
    setIsSubmitted(true);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      {/* Hero Section */}
      <section className="section-padding bg-gradient-to-br from-primary-50 to-accent-50">
        <div className="container-custom">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-center max-w-4xl mx-auto"
          >
            <div className="inline-flex items-center justify-center w-20 h-20 bg-white rounded-2xl shadow-lg mb-6">
              <Handshake className="h-10 w-10 text-primary-600" />
            </div>
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-gray-900 mb-6">
              Партнёрство для e-Grocery
            </h1>
            <p className="text-lg md:text-xl text-gray-600 mb-8">
              Внорку направляет пользователей с готовыми корзинами в ваше приложение.
              Получите доступ к аудитории, которая точно знает, что хочет купить.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <a
                href="#request-form"
                className="inline-flex items-center justify-center bg-primary-500 hover:bg-primary-600 text-white font-semibold px-8 py-4 rounded-lg transition-colors"
              >
                Стать партнёром
                <ArrowRight className="ml-2 h-5 w-5" />
              </a>
              <a
                href="mailto:team@vnorku.ru"
                className="inline-flex items-center justify-center border-2 border-primary-500 text-primary-600 hover:bg-white font-semibold px-8 py-4 rounded-lg transition-colors"
              >
                <Mail className="mr-2 h-5 w-5" />
                team@vnorku.ru
              </a>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Benefits */}
      <section className="section-padding">
        <div className="container-custom">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center mb-12"
          >
            <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
              Преимущества партнёрства
            </h2>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              Почему e-Grocery выбирают Внорку для привлечения клиентов
            </p>
          </motion.div>

          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-4 max-w-6xl mx-auto">
            {benefits.map((benefit, index) => {
              const Icon = benefit.icon;
              return (
                <motion.div
                  key={benefit.title}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.5, delay: index * 0.1 }}
                  className="bg-white rounded-xl p-6 shadow-sm hover:shadow-lg transition-shadow"
                >
                  <div className="inline-flex items-center justify-center w-12 h-12 bg-primary-100 rounded-lg mb-4">
                    <Icon className="h-6 w-6 text-primary-600" />
                  </div>
                  <h3 className="text-lg font-bold text-gray-900 mb-2">
                    {benefit.title}
                  </h3>
                  <p className="text-sm text-gray-600">
                    {benefit.description}
                  </p>
                </motion.div>
              );
            })}
          </div>

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-8 max-w-4xl mx-auto"
          >
            <div className="text-center">
              <div className="text-4xl font-bold text-primary-600 mb-2">2,500+</div>
              <div className="text-sm text-gray-600">Активных пользователей</div>
            </div>
            <div className="text-center">
              <div className="text-4xl font-bold text-primary-600 mb-2">3,200₽</div>
              <div className="text-sm text-gray-600">Средний чек корзины</div>
            </div>
            <div className="text-center">
              <div className="text-4xl font-bold text-primary-600 mb-2">87%</div>
              <div className="text-sm text-gray-600">Конверсия в покупку</div>
            </div>
            <div className="text-center">
              <div className="text-4xl font-bold text-primary-600 mb-2">10M₽</div>
              <div className="text-sm text-gray-600">GMV (план на год 1)</div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* How It Works */}
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
              Как работает интеграция
            </h2>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              Простой процесс в 4 шага
            </p>
          </motion.div>

          <div className="max-w-3xl mx-auto">
            <div className="space-y-6">
              {[
                {
                  step: 1,
                  title: 'Пользователь формирует план питания',
                  description: 'Указывает цель (похудение, набор массы и т.д.) и получает расчёт калорий',
                },
                {
                  step: 2,
                  title: 'Внорку подбирает продукты',
                  description: 'Алгоритм через ваш API получает список товаров, цены и наличие',
                },
                {
                  step: 3,
                  title: 'Формируется оптимальная корзина',
                  description: 'Пользователь выбирает один из 3 вариантов корзин с точным соблюдением плана',
                },
                {
                  step: 4,
                  title: 'Переход в ваше приложение',
                  description: 'Пользователь нажимает кнопку "Заказать" и попадает в ваше приложение с готовой корзиной',
                },
              ].map((item, index) => (
                <motion.div
                  key={item.step}
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.5, delay: index * 0.1 }}
                  className="flex gap-6 bg-white rounded-xl p-6 shadow-sm"
                >
                  <div className="flex-shrink-0 w-12 h-12 bg-primary-500 text-white rounded-full flex items-center justify-center font-bold text-xl">
                    {item.step}
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-gray-900 mb-2">
                      {item.title}
                    </h3>
                    <p className="text-gray-600">
                      {item.description}
                    </p>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Technical Requirements */}
      <section className="section-padding">
        <div className="container-custom">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center mb-12"
          >
            <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
              Технические требования
            </h2>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              Что нужно для интеграции с Внорку
            </p>
          </motion.div>

          <div className="max-w-4xl mx-auto space-y-4">
            {requirements.map((req, index) => (
              <motion.div
                key={req.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="bg-white rounded-xl p-6 shadow-sm"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-bold text-gray-900">
                        {req.title}
                      </h3>
                      <span
                        className={`text-xs font-semibold px-2 py-1 rounded ${
                          req.status === 'required'
                            ? 'bg-red-100 text-red-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {req.status === 'required' ? 'Обязательно' : 'Опционально'}
                      </span>
                    </div>
                    <p className="text-gray-600">
                      {req.description}
                    </p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="mt-12 max-w-4xl mx-auto"
          >
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-6">
              <h3 className="font-semibold text-blue-900 mb-3">
                💡 Нет API? Не проблема!
              </h3>
              <p className="text-sm text-blue-800 leading-relaxed">
                Если у вас пока нет публичного API, мы можем обсудить альтернативные варианты интеграции
                или помочь с разработкой минимального API для работы с Внорку. Свяжитесь с нами: team@vnorku.ru
              </p>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Partnership Request Form */}
      <section id="request-form" className="section-padding bg-gradient-to-br from-primary-50 to-accent-50">
        <div className="container-custom">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="max-w-2xl mx-auto"
          >
            <div className="text-center mb-8">
              <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
                Заявка на партнёрство
              </h2>
              <p className="text-lg text-gray-600">
                Заполните форму, и мы свяжемся с вами в течение 24 часов
              </p>
            </div>

            {!isSubmitted ? (
              <form onSubmit={handleSubmit} className="bg-white rounded-2xl p-8 shadow-lg">
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Название компании *
                    </label>
                    <input
                      type="text"
                      name="companyName"
                      value={formData.companyName}
                      onChange={handleChange}
                      required
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-primary-500 focus:ring-0 outline-none transition-colors"
                      placeholder="Яндекс.Лавка"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Контактное лицо *
                    </label>
                    <input
                      type="text"
                      name="contactName"
                      value={formData.contactName}
                      onChange={handleChange}
                      required
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-primary-500 focus:ring-0 outline-none transition-colors"
                      placeholder="Иван Иванов"
                    />
                  </div>

                  <div className="grid md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Email *
                      </label>
                      <input
                        type="email"
                        name="email"
                        value={formData.email}
                        onChange={handleChange}
                        required
                        className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-primary-500 focus:ring-0 outline-none transition-colors"
                        placeholder="ivan@company.ru"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Телефон
                      </label>
                      <input
                        type="tel"
                        name="phone"
                        value={formData.phone}
                        onChange={handleChange}
                        className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-primary-500 focus:ring-0 outline-none transition-colors"
                        placeholder="+7 (999) 123-45-67"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Есть ли у вас API для работы с корзиной? *
                    </label>
                    <select
                      name="hasAPI"
                      value={formData.hasAPI}
                      onChange={handleChange}
                      required
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-primary-500 focus:ring-0 outline-none transition-colors bg-white"
                    >
                      <option value="yes">Да, API готов</option>
                      <option value="in-development">В разработке</option>
                      <option value="no">Нет, но готовы обсудить</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Дополнительная информация
                    </label>
                    <textarea
                      name="message"
                      value={formData.message}
                      onChange={handleChange}
                      rows={4}
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-primary-500 focus:ring-0 outline-none transition-colors"
                      placeholder="Расскажите о вашем сервисе, географии работы и т.д."
                    />
                  </div>

                  <button
                    type="submit"
                    className="w-full bg-primary-500 hover:bg-primary-600 text-white font-semibold py-4 px-6 rounded-lg transition-colors"
                  >
                    Отправить заявку
                  </button>
                </div>
              </form>
            ) : (
              <div className="bg-white rounded-2xl p-12 shadow-lg text-center">
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
                  <CheckCircle className="h-8 w-8 text-green-600" />
                </div>
                <h3 className="text-2xl font-bold text-gray-900 mb-4">
                  Спасибо за заявку!
                </h3>
                <p className="text-gray-600 mb-8">
                  Мы получили вашу заявку и свяжемся с вами в течение 24 часов.
                  Проверьте почту {formData.email}
                </p>
                <button
                  onClick={() => setIsSubmitted(false)}
                  className="text-primary-600 hover:text-primary-700 font-medium"
                >
                  Отправить ещё одну заявку
                </button>
              </div>
            )}
          </motion.div>
        </div>
      </section>
    </div>
  );
}
