'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, Search, HelpCircle } from 'lucide-react';

interface FAQItem {
  question: string;
  answer: string;
  category: string;
}

export default function FAQPage() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const categories = [
    { id: 'all', name: 'Все вопросы' },
    { id: 'general', name: 'Общие вопросы' },
    { id: 'how-it-works', name: 'Как это работает' },
    { id: 'pricing', name: 'Тарифы и оплата' },
    { id: 'nutrition', name: 'Питание и калории' },
    { id: 'technical', name: 'Технические вопросы' },
  ];

  const faqs: FAQItem[] = [
    {
      question: 'Как Внорку гарантирует точность ±5%?',
      answer: 'Мы используем Health-First алгоритм оптимизации, который анализирует калорийность и макронутриенты каждого продукта из нашей базы данных (более 5,000 позиций). Алгоритм перебирает миллионы комбинаций продуктов и выбирает те, которые максимально точно соответствуют вашему плану по питанию. Для расчёта базового обмена веществ используется формула Mifflin-St Jeor (1990) — научно обоснованный метод с точностью ±10% у 82% людей согласно мета-анализу Frankenfield et al. (2005). Эта формула рекомендована Американской диетологической ассоциацией как наиболее точная для современной популяции. Затем мы корректируем калорийность с учётом вашей цели (похудение, набор массы и т.д.).',
      category: 'nutrition',
    },
    {
      question: 'В каких городах работает сервис?',
      answer: 'Внорку работает во всех городах, где доступны сервисы доставки e-grossery. Это все крупные города России: Москва, Санкт-Петербург, Казань, Нижний Новгород, Екатеринбург и другие.',
      category: 'general',
    },
    {
      question: 'Внорку сам делает покупки за меня?',
      answer: 'Нет. Мы только формируем готовые корзины и направляем вас в приложение партнёра, где вы сами оплачиваете заказ. Мы не храним данные ваших карт и не имеем доступа к вашим другим платёжным инструментам.',
      category: 'how-it-works',
    },
    {
      question: 'Можно ли исключить определённые продукты (аллергии, непереносимость)?',
      answer: 'Да! В боте есть раздел "Настройки", где вы можете указать список исключений. Например: "без молочных продуктов", "без глютена", "не ем рыбу", "веган", "без орехов" и т.д. Алгоритм учтёт эти ограничения при подборе корзины и исключит все продукты, содержащие указанные ингредиенты. Вы также можете добавить конкретные продукты, которые не хотите видеть в корзине.',
      category: 'nutrition',
    },
    {
      question: 'Сколько стоит доставка?',
      answer: 'Стоимость доставки зависит от сервиса-партнёра, размера заказа, адреса доставки и времени суток когда оформляется заказ — в пиковые часы доставка стоит дороже. Наш алгоритм учитывает стоимость доставки при составлении корзины и показывает итоговую сумму, включающую стоимость доставки.',
      category: 'pricing',
    },
    {
      question: 'Что делать, если в момент оформления покупки товар закончился?',
      answer: 'Мы показываем 3 варианта корзин на выбор — если в одном варианте что-то закончилось, можете выбрать следующий. Наш алгоритм проверяет наличие ассортимента из заказа в торговой сети непосредственно для вашего адреса доставки.',
      category: 'how-it-works',
    },
    {
      question: 'Можно ли отменить подписку?',
      answer: 'Да, вы можете отменить подписку в любой момент через бота в Telegram (команда /cancel или раздел "Подписка"). После отмены доступ к платным функциям сохраняется до конца оплаченного периода. Никаких штрафов или комиссий за отмену нет. Если вы передумаете, подписку можно возобновить в любой момент.',
      category: 'pricing',
    },
    {
      question: 'Есть ли пробный период для платных тарифов?',
      answer: 'Бесплатный тариф Free позволяет попробовать основной функционал сервиса (до 2 корзин в неделю). Для платных тарифов Health и Health Pro мы предлагаем 7 дней возврата средств без объяснения причин. Если сервис вам не подошёл в течение первых 7 дней, просто напишите в поддержку, и мы вернём полную стоимость.',
      category: 'pricing',
    },
    {
      question: 'Можно ли перейти с одного тарифа на другой?',
      answer: 'Да, вы можете перейти на другой тариф в любой момент через бота (команда /upgrade или /downgrade). При переходе на более дорогой тариф мы пересчитаем стоимость пропорционально оставшимся дням текущего периода. При переходе на более дешёвый тариф остаток будет зачтён в счёт следующего платежа.',
      category: 'pricing',
    },
    {
      question: 'Как рассчитывается моя норма калорий?',
      answer: 'Мы используем формулу Mifflin-St Jeor — одну из наиболее точных формул для расчёта базового обмена веществ (BMR). Она учитывает ваш пол, возраст, рост и вес. Затем BMR умножается на коэффициент активности для получения общего расхода калорий (TDEE). В зависимости от вашей цели (похудение, поддержание веса, набор массы) мы корректируем калорийность: для похудения создаём дефицит 500 ккал/день, для набора массы — профицит 300 ккал/день.',
      category: 'nutrition',
    },
    {
      question: 'Можно ли использовать сервис для кето-диеты?',
      answer: 'Да! У нас есть специальный режим "Кето-диета", который автоматически подбирает продукты с низким содержанием углеводов (до 5% от общей калорийности) и высоким содержанием жиров (около 70%). Вы можете выбрать эту цель при настройке плана питания, и алгоритм будет искать подходящие продукты: мясо, рыбу, яйца, сыры, орехи, масла, некрахмалистые овощи и т.д.',
      category: 'nutrition',
    },
    {
      question: 'Поддерживается ли вегетарианское/веганское питание?',
      answer: 'Да, в настройках можно выбрать тип питания: "Веган", "Вегетарианец", "Пескетарианец" (рыба разрешена). Алгоритм будет исключать продукты животного происхождения согласно выбранному типу. Для веганов мы подбираем растительные источники белка (бобовые, тофу, темпе, орехи, семена) и следим за балансом незаменимых аминокислот.',
      category: 'nutrition',
    },
    {
      question: 'Как часто обновляются цены на продукты?',
      answer: 'Мы обновляем цены в режиме реального времени при каждом запросе корзины. Данные о наличии обновляются каждые 15 минут. Это гарантирует, что вы всегда видите актуальные цены и не столкнётесь с ситуацией, когда продукт значительно подорожал или закончился.',
      category: 'technical',
    },
    {
      question: 'Можно ли сохранить корзину и заказать позже?',
      answer: 'Да, в боте есть функция "Сохранить корзину". Все сохранённые корзины доступны в разделе "История" в течение 30 дней. Вы можете открыть сохранённую корзину и заказать её в любой момент. Обратите внимание, что цены и наличие товаров могут измениться с момента сохранения.',
      category: 'how-it-works',
    },
    {
      question: 'Есть ли мобильное приложение?',
      answer: 'На текущий момент приложение в разработке. Взаимодействие с сервисом реализовано посредством Telegram, т.к. Telegram доступен на всех мобильных и веб платформах (iOS, Android, Web, Desktop), поэтому вы можете пользоваться сервисом с любого устройства. Просто найдите бота @Coffeematebot и начните диалог.',
      category: 'technical',
    },
    {
      question: 'Можно ли использовать сервис для всей семьи?',
      answer: 'Да! Вы можете создать семейный профиль и добавить индивидуальные планы для каждого члена вашей семьи. При формировании корзины вы можете выбрать, для кого именно создать план, или объединить несколько профилей в одну корзину (например, если заказываете продукты на неделю для всей семьи).',
      category: 'general',
    },
    {
      question: 'Как работает интеграция с Apple Health / Google Fit?',
      answer: 'На тарифе Health Pro вы можете подключить свой фитнес-трекер (Apple Health, Google Fit, Fitbit и др.). Сервис будет автоматически синхронизировать данные о вашей активности, расходе калорий и весе. Это позволяет динамически корректировать план питания в зависимости от фактической активности (например, если вы сегодня пробежали 10 км, калорийность корзины увеличится автоматически).',
      category: 'technical',
    },
    {
      question: 'Можно ли добавить свои продукты в корзину?',
      answer: 'Да, при просмотре готовой корзины вы можете добавить дополнительные продукты вручную. Бот пересчитает калорийность и макронутриенты с учётом добавленных позиций и покажет, как это повлияет на соблюдение плана. Также можно удалить продукты из корзины или заменить их на аналоги.',
      category: 'how-it-works',
    },
    {
      question: 'Что такое Health-First оптимизация?',
      answer: 'Это наш уникальный алгоритм, который ставит здоровье на первое место. 85% веса в оптимизации отдаётся соблюдению плана питания (калорийность, БЖУ, микронутриенты, разнообразие), и только 15% — стоимости. Это значит, что алгоритм в первую очередь найдёт корзину, которая точно соответствует вашему плану, и среди таких вариантов выберет наиболее выгодный по цене.',
      category: 'nutrition',
    },
    {
      question: 'Безопасно ли передавать данные о питании?',
      answer: 'Да, наш сервис соблюдает все современные стандарты безопасности. Для передачи данных мы используем только защищенные каналы, а хранение данных зашифровано. Мы не передаём ваши персональные данные третьим лицам без вашего согласия. Данные о вашем питании хранятся в зашифрованном виде и используются только для формирования корзин. Вы можете в любой момент удалить свою историю или весь аккаунт.',
      category: 'technical',
    },
  ];

  const filteredFAQs = faqs.filter((faq) => {
    const matchesCategory = selectedCategory === 'all' || faq.category === selectedCategory;
    const matchesSearch =
      searchQuery === '' ||
      faq.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
      faq.answer.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

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
              <HelpCircle className="h-8 w-8 text-primary-600" />
            </div>
            <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              Часто задаваемые вопросы
            </h1>
            <p className="text-lg text-gray-600">
              Найдите ответы на популярные вопросы о работе сервиса
            </p>
          </motion.div>

          {/* Search */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="max-w-2xl mx-auto mb-12"
          >
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                type="text"
                placeholder="Поиск по вопросам..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-12 pr-4 py-4 border-2 border-gray-200 rounded-xl focus:border-primary-500 focus:ring-0 outline-none transition-colors"
              />
            </div>
          </motion.div>

          {/* Categories */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="flex flex-wrap gap-3 justify-center mb-12"
          >
            {categories.map((category) => (
              <button
                key={category.id}
                onClick={() => setSelectedCategory(category.id)}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  selectedCategory === category.id
                    ? 'bg-primary-500 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-100 border border-gray-200'
                }`}
              >
                {category.name}
              </button>
            ))}
          </motion.div>

          {/* FAQ List */}
          <div className="max-w-3xl mx-auto">
            {filteredFAQs.length > 0 ? (
              <div className="space-y-4">
                {filteredFAQs.map((faq, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
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
                          <div className="px-6 pb-5 text-gray-600 leading-relaxed">
                            {faq.answer}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Search className="h-8 w-8 text-gray-400" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  Ничего не найдено
                </h3>
                <p className="text-gray-600">
                  Попробуйте изменить поисковый запрос или выбрать другую категорию
                </p>
              </div>
            )}
          </div>

          {/* Contact Support */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.6 }}
            className="mt-16 text-center"
          >
            <div className="bg-primary-50 border border-primary-200 rounded-2xl p-8 max-w-2xl mx-auto">
              <h3 className="text-xl font-bold text-gray-900 mb-2">
                Не нашли ответ?
              </h3>
              <p className="text-gray-600 mb-6">
                Напишите нам, и мы с радостью поможем вам разобраться
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <a
                  href="https://t.me/Coffeematebot"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center bg-primary-500 hover:bg-primary-600 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
                >
                  Написать в Telegram
                </a>
                <a
                  href="mailto:dev@vnorku.ru"
                  className="inline-flex items-center justify-center border-2 border-primary-500 text-primary-600 hover:bg-primary-50 font-semibold px-6 py-3 rounded-lg transition-colors"
                >
                  Отправить Email
                </a>
              </div>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
