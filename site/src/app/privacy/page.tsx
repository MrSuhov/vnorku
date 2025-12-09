'use client';

import { motion } from 'framer-motion';
import { Shield, Mail, MessageCircle } from 'lucide-react';

export default function PrivacyPage() {
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
              <Shield className="h-8 w-8 text-primary-600" />
            </div>
            <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              Политика обработки персональных данных
            </h1>
            <p className="text-lg text-gray-600">
              Дата вступления в силу: 9 декабря 2024 г.
            </p>
          </motion.div>

          {/* Content */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="max-w-4xl mx-auto"
          >
            <div className="bg-white rounded-2xl shadow-sm p-8 md:p-12 space-y-8">
              {/* Section 1 */}
              <section>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">1. Общие положения</h2>
                <div className="space-y-4 text-gray-600 leading-relaxed">
                  <p>
                    1.1. Настоящая Политика обработки персональных данных (далее — «Политика») определяет порядок обработки и защиты персональных данных пользователей сервиса «Внорку» (далее — «Сервис»).
                  </p>
                  <p>
                    1.2. Оператором персональных данных является ИП [наименование оператора] (далее — «Оператор»).
                  </p>
                  <p>
                    1.3. Политика разработана в соответствии с Федеральным законом от 27.07.2006 № 152-ФЗ «О персональных данных».
                  </p>
                  <p>
                    1.4. Использование Сервиса означает безоговорочное согласие пользователя с настоящей Политикой и указанными в ней условиями обработки его персональных данных.
                  </p>
                </div>
              </section>

              {/* Section 2 */}
              <section>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">2. Категории обрабатываемых персональных данных</h2>
                <div className="space-y-4 text-gray-600 leading-relaxed">
                  <p>2.1. Оператор обрабатывает следующие категории персональных данных:</p>

                  <div className="bg-gray-50 rounded-xl p-6 space-y-4">
                    <div>
                      <h3 className="font-semibold text-gray-900 mb-2">Идентификационные данные:</h3>
                      <ul className="list-disc list-inside space-y-1">
                        <li>Имя пользователя в Telegram</li>
                        <li>Telegram ID</li>
                      </ul>
                    </div>

                    <div>
                      <h3 className="font-semibold text-gray-900 mb-2">Контактные данные:</h3>
                      <ul className="list-disc list-inside space-y-1">
                        <li>Адрес доставки</li>
                      </ul>
                    </div>

                    <div>
                      <h3 className="font-semibold text-gray-900 mb-2">Данные о здоровье и питании:</h3>
                      <ul className="list-disc list-inside space-y-1">
                        <li>Пол, возраст, рост, вес (при указании пользователем)</li>
                        <li>Уровень физической активности</li>
                        <li>Цели питания (похудение, набор массы, поддержание веса)</li>
                        <li>Диетические ограничения и аллергии</li>
                        <li>Предпочтения в питании</li>
                      </ul>
                    </div>

                    <div>
                      <h3 className="font-semibold text-gray-900 mb-2">Данные об использовании Сервиса:</h3>
                      <ul className="list-disc list-inside space-y-1">
                        <li>История заказов и сформированных корзин</li>
                        <li>Настройки и предпочтения пользователя</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </section>

              {/* Section 3 */}
              <section>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">3. Цели обработки персональных данных</h2>
                <div className="space-y-4 text-gray-600 leading-relaxed">
                  <p>3.1. Персональные данные обрабатываются в следующих целях:</p>

                  <div className="bg-gray-50 rounded-xl p-6 space-y-4">
                    <div>
                      <h3 className="font-semibold text-gray-900 mb-2">Предоставление услуг Сервиса:</h3>
                      <ul className="list-disc list-inside space-y-1">
                        <li>Формирование персонализированных продуктовых корзин</li>
                        <li>Расчёт индивидуальной нормы калорий и макронутриентов</li>
                        <li>Учёт диетических ограничений и пищевых аллергий</li>
                      </ul>
                    </div>

                    <div className="bg-primary-50 border border-primary-200 rounded-lg p-4">
                      <h3 className="font-semibold text-gray-900 mb-2">Определение доступного ассортимента:</h3>
                      <p>
                        Адрес пользователя используется для проверки доступного к доставке ассортимента продуктов по его адресу в сервисах доставки партнёров.
                      </p>
                    </div>

                    <div>
                      <h3 className="font-semibold text-gray-900 mb-2">Улучшение качества Сервиса:</h3>
                      <ul className="list-disc list-inside space-y-1">
                        <li>Анализ использования Сервиса для улучшения функциональности</li>
                        <li>Персонализация рекомендаций</li>
                      </ul>
                    </div>

                    <div>
                      <h3 className="font-semibold text-gray-900 mb-2">Коммуникация с пользователем:</h3>
                      <ul className="list-disc list-inside space-y-1">
                        <li>Отправка уведомлений о сформированных корзинах</li>
                        <li>Техническая поддержка</li>
                        <li>Информирование об изменениях в работе Сервиса</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </section>

              {/* Section 4 */}
              <section>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">4. Правовые основания обработки</h2>
                <div className="space-y-4 text-gray-600 leading-relaxed">
                  <p>4.1. Обработка персональных данных осуществляется на следующих правовых основаниях:</p>
                  <ul className="list-disc list-inside space-y-2">
                    <li>Согласие субъекта персональных данных (п. 1 ч. 1 ст. 6 ФЗ № 152-ФЗ)</li>
                    <li>Исполнение договора, стороной которого является субъект персональных данных (п. 5 ч. 1 ст. 6 ФЗ № 152-ФЗ)</li>
                  </ul>
                </div>
              </section>

              {/* Section 5 */}
              <section>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">5. Порядок и условия обработки персональных данных</h2>
                <div className="space-y-4 text-gray-600 leading-relaxed">
                  <p>5.1. Обработка персональных данных осуществляется следующими способами:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Сбор, запись, систематизация, накопление, хранение</li>
                    <li>Уточнение (обновление, изменение)</li>
                    <li>Извлечение, использование, передача (предоставление, доступ)</li>
                    <li>Обезличивание, блокирование, удаление, уничтожение</li>
                  </ul>
                  <p>5.2. Обработка осуществляется с использованием средств автоматизации.</p>
                  <p>5.3. Персональные данные хранятся в зашифрованном виде на защищённых серверах.</p>
                </div>
              </section>

              {/* Section 6 */}
              <section>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">6. Передача персональных данных третьим лицам</h2>
                <div className="space-y-4 text-gray-600 leading-relaxed">
                  <p>6.1. Оператор не передаёт персональные данные третьим лицам, за исключением случаев:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Наличия согласия пользователя</li>
                    <li>Предусмотренных законодательством Российской Федерации</li>
                  </ul>
                  <p className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <strong>Важно:</strong> Сервис не осуществляет оплату покупок за пользователя. Данные банковских карт не собираются и не хранятся Оператором.
                  </p>
                </div>
              </section>

              {/* Section 7 */}
              <section>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">7. Защита персональных данных</h2>
                <div className="space-y-4 text-gray-600 leading-relaxed">
                  <p>7.1. Оператор принимает необходимые организационные и технические меры для защиты персональных данных от неправомерного или случайного доступа, уничтожения, изменения, блокирования, копирования, распространения.</p>
                  <p>7.2. К мерам защиты относятся:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Шифрование данных при передаче и хранении</li>
                    <li>Ограничение доступа к персональным данным</li>
                    <li>Использование защищённых каналов связи</li>
                    <li>Регулярное резервное копирование</li>
                  </ul>
                </div>
              </section>

              {/* Section 8 */}
              <section>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">8. Права субъекта персональных данных</h2>
                <div className="space-y-4 text-gray-600 leading-relaxed">
                  <p>8.1. Пользователь имеет право:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Получить информацию об обработке своих персональных данных</li>
                    <li>Требовать уточнения, блокирования или уничтожения персональных данных</li>
                    <li>Отозвать согласие на обработку персональных данных</li>
                    <li>Удалить свой аккаунт и все связанные данные</li>
                  </ul>
                  <p>8.2. Для реализации своих прав пользователь может:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Использовать команду удаления аккаунта в Telegram-боте</li>
                    <li>Обратиться в службу поддержки: dev@vnorku.ru</li>
                  </ul>
                </div>
              </section>

              {/* Section 9 */}
              <section>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">9. Сроки обработки персональных данных</h2>
                <div className="space-y-4 text-gray-600 leading-relaxed">
                  <p>9.1. Персональные данные обрабатываются до момента:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Удаления аккаунта пользователем</li>
                    <li>Отзыва согласия на обработку</li>
                    <li>Достижения целей обработки</li>
                  </ul>
                  <p>9.2. При удалении аккаунта персональные данные уничтожаются в течение 30 дней.</p>
                </div>
              </section>

              {/* Section 10 */}
              <section>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">10. Файлы cookie и технологии отслеживания</h2>
                <div className="space-y-4 text-gray-600 leading-relaxed">
                  <p>10.1. Сервис использует файлы cookie для:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Обеспечения функционирования авторизации в сервисах доставки</li>
                    <li>Сохранения настроек пользователя</li>
                  </ul>
                  <p>10.2. Cookie-файлы сервисов доставки хранятся локально и используются исключительно для авторизации пользователя в выбранных им сервисах.</p>
                </div>
              </section>

              {/* Section 11 */}
              <section>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">11. Изменение Политики</h2>
                <div className="space-y-4 text-gray-600 leading-relaxed">
                  <p>11.1. Оператор вправе вносить изменения в настоящую Политику.</p>
                  <p>11.2. При внесении существенных изменений пользователи уведомляются через Telegram-бот.</p>
                  <p>11.3. Актуальная версия Политики размещена на данной странице.</p>
                </div>
              </section>

              {/* Section 12 - Contact */}
              <section>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">12. Контактная информация</h2>
                <div className="space-y-4 text-gray-600 leading-relaxed">
                  <p>По вопросам обработки персональных данных обращайтесь:</p>
                  <div className="flex flex-col sm:flex-row gap-4 mt-6">
                    <a
                      href="mailto:team@vnorku.ru"
                      className="inline-flex items-center justify-center gap-2 bg-primary-500 hover:bg-primary-600 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
                    >
                      <Mail className="h-5 w-5" />
                      team@vnorku.ru
                    </a>
                    <a
                      href="https://t.me/Coffeematebot"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center justify-center gap-2 border-2 border-primary-500 text-primary-600 hover:bg-primary-50 font-semibold px-6 py-3 rounded-lg transition-colors"
                    >
                      <MessageCircle className="h-5 w-5" />
                      Telegram
                    </a>
                  </div>
                </div>
              </section>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
