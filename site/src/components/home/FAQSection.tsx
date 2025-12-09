'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';

export default function FAQSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const faqs = [
    {
      question: 'Как Внорку гарантирует точность ±5%?',
      answer: 'Мы используем Health-First алгоритм оптимизации, который анализирует калорийность и макронутриенты каждого продукта из нашей базы данных (более 5,000 позиций). Алгоритм перебирает миллионы комбинаций продуктов и выбирает те, которые максимально точно соответствуют вашему плану по питанию. Для расчёта базового обмена веществ используется формула Mifflin-St Jeor (1990) — научно обоснованный метод с точностью ±10% у 82% людей согласно мета-анализу Frankenfield et al. (2005). Эта формула рекомендована Американской диетологической ассоциацией как наиболее точная для современной популяции. Затем мы корректируем калорийность с учётом вашей цели (похудение, набор массы и т.д.).',
    },
    {
      question: 'В каких городах работает сервис?',
      answer: 'Внорку работает во всех городах, где доступны сервисы доставки e-grossery. Это все крупные города России: Москва, Санкт-Петербург, Казань, Нижний Новгород, Екатеринбург и другие.',
    },
    {
      question: 'Внорку сам делает покупки за меня?',
      answer: 'Нет. Мы только формируем готовые корзины и направляем вас в приложение партнёра, где вы сами оплачиваете заказ. Мы не храним данные ваших карт и не имеем доступа к вашим другим платёжным данным.',
    },
    {
      question: 'Можно ли исключить определённые продукты (аллергии, непереносимость)?',
      answer: 'Да! В боте есть раздел "Настройки", где вы можете указать список исключений. Например: "без молочных продуктов", "без глютена", "не ем рыбу", "веган", "без орехов" и т.д. Алгоритм учтёт эти ограничения при подборе корзины и исключит все продукты, содержащие указанные ингредиенты. Вы также можете добавить конкретные продукты, которые не хотите видеть в корзине.',
    },
    {
      question: 'Сколько стоит доставка?',
      answer: 'Стоимость доставки зависит от сервиса-партнёра, размера заказа, адреса доставки и времени суток когда оформляется заказ — в пиковые часы доставка стоит дороже. Наш алгоритм учитывает стоимость доставки при составлении корзины и показывает итоговую сумму, включающую стоимость доставки.',
    },
    {
      question: 'Что делать, если в момент оформления покупки товар закончился?',
      answer: 'Мы показываем 3 варианта корзин на выбор — если в одном варианте что-то закончилось, можете выбрать следующий. Наш алгоритм проверяет наличие ассортимента из заказа в торговой сети непосредственно для вашего адреса доставки.',
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
          className="text-center mb-16"
        >
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-gray-900 mb-6">
            Часто задаваемые вопросы
          </h2>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Ответы на популярные вопросы о работе сервиса
          </p>
        </motion.div>

        <div className="max-w-3xl mx-auto space-y-4">
          {faqs.map((faq, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: index * 0.05 }}
              className="bg-white rounded-xl shadow-sm overflow-hidden"
            >
              <button
                onClick={() => setOpenIndex(openIndex === index ? null : index)}
                className="w-full px-6 py-5 flex items-center justify-between text-left hover:bg-gray-50 transition-colors"
              >
                <span className="font-semibold text-gray-900 pr-4">
                  {faq.question}
                </span>
                <ChevronDown
                  className={`h-5 w-5 text-gray-500 flex-shrink-0 transition-transform ${
                    openIndex === index ? 'rotate-180' : ''
                  }`}
                />
              </button>

              <AnimatePresence>
                {openIndex === index && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    <div className="px-6 pb-5 text-gray-600">
                      {faq.answer}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
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
          <p className="text-gray-600 mb-4">
            Не нашли ответ на свой вопрос?
          </p>
          <a
            href="mailto:dev@vnorku.ru"
            className="inline-flex items-center justify-center rounded-lg border-2 border-primary-500 px-6 py-3 font-semibold text-primary-600 hover:bg-primary-50 transition-colors"
          >
            Написать в поддержку
          </a>
        </motion.div>
      </div>
    </section>
  );
}
