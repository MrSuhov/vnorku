# Vnorku Website

Официальный сайт платформы Внорку — персонального нутрициолога для контроля рациона.

🌐 **Production:** https://vnorku.ru
📱 **Telegram Bot:** [@vnorku_bot](https://t.me/vnorku_bot)

---

## 📋 Обзор Проекта

**Внорку** — это интеллектуальная платформа, которая автоматически формирует продуктовые корзины на основе целей пользователя по питанию (похудение, набор массы, кето-диета и т.д.), гарантируя соблюдение плана по калориям и макронутриентам с точностью ±3%.

### Ключевые Фичи Сайта

- 🎯 **Интерактивный калькулятор калорий** (Mifflin-St Jeor формула)
- 💳 **Страница тарифов** (Free, Health, Health Pro)
- ❓ **Детальный FAQ** с категориями вопросов
- 🤝 **Раздел для партнёров** (e-Grocery интеграции)
- 🌍 **Мультиязычность** (RU/EN)
- 📱 **Полностью адаптивный дизайн** (mobile-first)
- ⚡ **Высокая производительность** (Lighthouse score >90)

---

## 🛠 Технологический Стек

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript 5.4
- **Styling:** Tailwind CSS 3.4
- **Animations:** Framer Motion 11
- **Icons:** Lucide React
- **Forms:** React Hook Form + Zod
- **i18n:** next-intl
- **UI Components:** Radix UI (Accordion, Select, Dialog, etc.)
- **Deployment:** VPS (Nginx + PM2)
- **SSL:** Let's Encrypt (Certbot)

---

## 🚀 Быстрый Старт

### Требования

- Node.js 18+ (рекомендуется 20 LTS)
- npm 9+

### Установка

```bash
# Клонировать репозиторий
git clone https://github.com/vnorku/website.git
cd website

# Установить зависимости
npm install

# Создать .env.local
cp .env.example .env.local
# Заполнить переменные окружения

# Запустить dev server
npm run dev
```

Откройте [http://localhost:3000](http://localhost:3000) в браузере.

---

## 📂 Структура Проекта

```
/site
├── /public
│   ├── /images          # Изображения (логотип, иконки, иллюстрации)
│   ├── /icons           # Иконки (favicon, apple-touch-icon)
│   └── /files           # Файлы для скачивания (PDF, etc.)
├── /src
│   ├── /app             # Next.js App Router
│   │   ├── page.tsx     # Главная страница
│   │   ├── /pricing     # Страница тарифов
│   │   ├── /calculator  # Калькулятор калорий
│   │   ├── /faq         # FAQ
│   │   ├── /partners    # Для партнёров
│   │   └── /api         # API routes
│   ├── /components
│   │   ├── /layout      # Header, Footer, MobileMenu
│   │   ├── /home        # Секции главной страницы
│   │   ├── /ui          # Переиспользуемые UI компоненты
│   │   └── /shared      # Общие компоненты
│   ├── /lib
│   │   ├── utils.ts     # Утилиты
│   │   ├── calories.ts  # Калькулятор калорий (Mifflin-St Jeor)
│   │   └── api.ts       # API клиент
│   ├── /types           # TypeScript типы
│   └── /styles          # Глобальные стили
├── /locales
│   ├── /ru              # Русский язык
│   └── /en              # Английский язык
├── SITE_ARCHITECTURE.md # Детальная архитектура сайта
├── CONTENT.md           # Все тексты для страниц
├── DEVELOPMENT_PLAN.md  # План разработки с чек-листами
├── DEPLOYMENT.md        # Инструкции по деплою на VPS
├── package.json
├── next.config.js
├── tailwind.config.ts
└── tsconfig.json
```

---

## 🎨 Дизайн-Система

### Цветовая Палитра

- **Primary (Green):** `#10B981` — здоровье, органика
- **Accent (Blue):** `#3B82F6` — доверие, технологии
- **Warning (Orange):** `#F59E0B` — предупреждения

### Типографика

- **Font:** Inter (Google Fonts)
- **H1:** 36-48px, Bold
- **H2:** 30-36px, Bold
- **Body:** 16px, Regular

### Компоненты

Все UI компоненты следуют принципам shadcn/ui:
- Button (Primary, Secondary, Ghost)
- Card (с тенью и border-radius)
- Input, Select, Accordion
- Badge, Dialog, Tabs

---

## 🧪 Скрипты

```bash
# Development
npm run dev          # Запуск dev server (localhost:3000)

# Production
npm run build        # Build для production
npm start            # Запуск production сервера

# Утилиты
npm run lint         # ESLint проверка
npm run type-check   # TypeScript проверка типов
npm run format       # Форматирование кода (Prettier)
```

---

## 🌍 Интернационализация (i18n)

Сайт поддерживает 2 языка:
- 🇷🇺 Русский (по умолчанию)
- 🇬🇧 Английский

### Добавление Переводов

1. Создайте файлы в `locales/ru` и `locales/en`
2. Используйте `useTranslations('namespace')` в компонентах
3. Добавьте переключатель языка в Header

Пример:

```tsx
import { useTranslations } from 'next-intl';

export default function Page() {
  const t = useTranslations('home');
  return <h1>{t('hero.title')}</h1>;
}
```

---

## 📡 API Endpoints

### `/api/calculate-calories`

Рассчитывает дневную норму калорий и макронутриентов.

**Request:**
```json
POST /api/calculate-calories
{
  "gender": "male",
  "age": 30,
  "height": 180,
  "weight": 80,
  "activity": "moderate",
  "goal": "weight_loss"
}
```

**Response:**
```json
{
  "bmr": 1789,
  "tdee": 2475,
  "target_calories": 1975,
  "macros": {
    "protein_g": 158,
    "carbs_g": 197,
    "fat_g": 62
  }
}
```

---

### `/api/beta-signup`

Регистрация на бета-тестирование.

**Request:**
```json
POST /api/beta-signup
{
  "email": "user@example.com",
  "name": "Иван Иванов",
  "telegram": "@ivan"
}
```

**Response:**
```json
{
  "success": true,
  "telegram_link": "https://t.me/vnorku_bot?start=beta_123456"
}
```

---

### `/api/partnership-request`

Запрос партнёрства от e-Grocery.

**Request:**
```json
POST /api/partnership-request
{
  "company_name": "Яндекс.Лавка",
  "contact_name": "Пётр Петров",
  "email": "petr@yandex.ru",
  "has_api": true
}
```

**Response:**
```json
{
  "success": true,
  "ticket_id": "PART-001"
}
```

---

## 🚢 Deployment

### Production (VPS)

**Сервер:** root@109.73.207.207
**Домен:** vnorku.ru
**Process Manager:** PM2
**Web Server:** Nginx
**SSL:** Let's Encrypt

**Полная инструкция:** См. [DEPLOYMENT.md](DEPLOYMENT.md)

**Быстрый deploy:**

```bash
# На локальной машине
git push origin main

# На сервере
ssh root@109.73.207.207
cd /var/www/vnorku
./deploy.sh
```

---

## 📊 Метрики Производительности

Целевые показатели Lighthouse:

- **Performance:** >90
- **Accessibility:** 100
- **Best Practices:** 100
- **SEO:** 100

**Текущие результаты:** (будут после деплоя)

---

## 🔒 Безопасность

- ✅ HTTPS везде (Let's Encrypt SSL)
- ✅ Security headers (CSP, X-Frame-Options, etc.)
- ✅ Rate limiting на API endpoints
- ✅ CSRF защита
- ✅ Input sanitization (Zod validation)
- ✅ Environment variables защищены (.gitignore)

---

## 🐛 Troubleshooting

### Сайт не запускается локально

```bash
# Очистить кэш
rm -rf .next
npm run build
npm run dev
```

### Build падает с ошибкой

```bash
# Проверить версию Node.js
node --version  # Должно быть >=18

# Переустановить зависимости
rm -rf node_modules package-lock.json
npm install
```

### SSL сертификат истёк

```bash
ssh root@109.73.207.207
certbot renew
systemctl reload nginx
```

---

## 📚 Документация

- [SITE_ARCHITECTURE.md](SITE_ARCHITECTURE.md) — Детальная архитектура сайта
- [CONTENT.md](CONTENT.md) — Все тексты для страниц (копирайт)
- [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) — План разработки с чек-листами
- [DEPLOYMENT.md](DEPLOYMENT.md) — Инструкции по деплою на VPS

---

## 🤝 Контрибьюция

Проект в активной разработке. Если вы хотите внести вклад:

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

---

## 📞 Контакты

**Email:** dev@vnorku.ru
**Telegram:** @vnorku_dev
**Website:** https://vnorku.ru

---

## 📄 Лицензия

© 2025 Внорку. Все права защищены.

---

**Версия:** 1.0.0
**Последнее обновление:** 2025-01-23
