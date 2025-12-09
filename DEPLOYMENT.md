# DEPLOYMENT.md

# Инструкция по Деплою Сайта Внорку на VPS

## Информация о Сервере

**IP:** 109.73.207.207
**User:** root
**Domain:** vnorku.ru
**OS:** Linux (предположительно Ubuntu/Debian)
**Node.js:** 20.x LTS
**Package Manager:** npm
**Process Manager:** PM2
**Web Server:** Nginx
**SSL:** Let's Encrypt (Certbot)

---

## Предварительные Требования

Перед началом деплоя убедитесь, что:

- [ ] Доступ по SSH работает: `ssh root@109.73.207.207`
- [ ] Домен vnorku.ru указывает на IP 109.73.207.207 (A-запись в DNS)
- [ ] Проект собран локально без ошибок: `npm run build`
- [ ] Все environment variables подготовлены
- [ ] GitHub репозиторий создан (или используем локальную копию)

---

## Шаг 1: Подготовка VPS

### 1.1 Подключение к Серверу

```bash
ssh root@109.73.207.207
```

**Если нужен пароль — запросите у администратора сервера.**

---

### 1.2 Обновление Системы

```bash
apt-get update
apt-get upgrade -y
```

---

### 1.3 Установка Node.js 20 LTS

Проверьте текущую версию:
```bash
node --version
```

Если Node.js не установлен или версия <20, установите:

```bash
# Установка Node.js 20 LTS через NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Проверка
node --version  # должно быть v20.x.x
npm --version   # должно быть 10.x.x
```

---

### 1.4 Установка Nginx

```bash
apt-get install -y nginx

# Проверка
systemctl status nginx
# Должно быть "active (running)"

# Если не запущен:
systemctl start nginx
systemctl enable nginx  # Автозапуск при перезагрузке
```

Проверьте в браузере: `http://109.73.207.207` — должна открыться стандартная страница Nginx.

---

### 1.5 Установка PM2 (Process Manager)

```bash
npm install -g pm2

# Проверка
pm2 --version
```

---

### 1.6 Установка Certbot (для SSL)

```bash
apt-get install -y certbot python3-certbot-nginx

# Проверка
certbot --version
```

---

### 1.7 Создание Директории для Проекта

```bash
mkdir -p /var/www
cd /var/www
```

---

## Шаг 2: Загрузка Проекта на Сервер

### Вариант A: Через Git (Рекомендуется)

#### 2.1 Создание GitHub Репозитория (если ещё нет)

На локальной машине:

```bash
cd /Users/ss/GenAI/korzinka/site
git init
git add .
git commit -m "Initial commit: Vnorku website"

# Создайте приватный репозиторий на GitHub: vnorku/website

git remote add origin https://github.com/vnorku/website.git
git branch -M main
git push -u origin main
```

#### 2.2 Клонирование на Сервер

На VPS:

```bash
cd /var/www
git clone https://github.com/vnorku/website.git vnorku

# Если приватный репозиторий — используйте Personal Access Token
# git clone https://<TOKEN>@github.com/vnorku/website.git vnorku

cd vnorku
```

---

### Вариант B: Через SCP (Если Git недоступен)

На локальной машине:

```bash
cd /Users/ss/GenAI/korzinka
tar -czf site.tar.gz site/

scp site.tar.gz root@109.73.207.207:/var/www/
```

На VPS:

```bash
cd /var/www
tar -xzf site.tar.gz
mv site vnorku
rm site.tar.gz
cd vnorku
```

---

## Шаг 3: Настройка Проекта

### 3.1 Установка Зависимостей

```bash
cd /var/www/vnorku
npm install
```

Это займёт несколько минут.

---

### 3.2 Создание .env.production

```bash
nano .env.production
```

Содержимое:

```env
# Public variables
NEXT_PUBLIC_SITE_URL=https://vnorku.ru
NEXT_PUBLIC_TELEGRAM_BOT=t.me/vnorku_bot

# Private variables
DATABASE_URL=postgresql://user:password@localhost:5432/vnorku
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Email (опционально)
EMAIL_API_KEY=your_email_api_key
EMAIL_FROM=noreply@vnorku.ru

# Payment (опционально)
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key

# Security
JWT_SECRET=your_random_secret_key_here
NEXTAUTH_SECRET=your_nextauth_secret_here
NEXTAUTH_URL=https://vnorku.ru

# Redis (если используется)
REDIS_URL=redis://localhost:6379
```

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

---

### 3.3 Build Проекта

```bash
npm run build
```

Проверьте, что build завершился без ошибок. Должно появиться:

```
✓ Compiled successfully
✓ Linting and checking validity of types
✓ Collecting page data
✓ Generating static pages (X/X)
✓ Finalizing page optimization

Route (app)                Size     First Load JS
┌ ○ /                      1.2 kB          85.1 kB
├ ○ /pricing               1.5 kB          86.4 kB
├ ○ /calculator            2.1 kB          87.0 kB
...
```

---

## Шаг 4: Запуск с PM2

### 4.1 Запуск Приложения

```bash
pm2 start npm --name "vnorku-site" -- start
```

### 4.2 Проверка Статуса

```bash
pm2 status
```

Должно быть:

```
┌────┬────────────────┬─────────┬─────────┬──────────┐
│ id │ name           │ mode    │ status  │ cpu      │
├────┼────────────────┼─────────┼─────────┼──────────┤
│ 0  │ vnorku-site    │ fork    │ online  │ 0%       │
└────┴────────────────┴─────────┴─────────┴──────────┘
```

### 4.3 Просмотр Логов

```bash
pm2 logs vnorku-site
```

Должно быть:

```
ready - started server on 0.0.0.0:3000, url: http://localhost:3000
```

Нажмите `Ctrl+C` для выхода.

### 4.4 Тест Локально на Сервере

```bash
curl http://localhost:3000
```

Должен вернуться HTML главной страницы.

---

### 4.5 Настройка Автозапуска

```bash
pm2 save
pm2 startup
```

PM2 выведет команду — **скопируйте и выполните её**. Например:

```bash
sudo env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u root --hp /root
```

Теперь PM2 будет автоматически запускаться при перезагрузке сервера.

---

## Шаг 5: Настройка Nginx

### 5.1 Создание Конфигурации

```bash
nano /etc/nginx/sites-available/vnorku.ru
```

Содержимое:

```nginx
# HTTP (будет редиректить на HTTPS после получения SSL)
server {
    listen 80;
    listen [::]:80;
    server_name vnorku.ru www.vnorku.ru;

    # Временно разрешим HTTP для Certbot
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Проксирование на Next.js
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Кэширование статических файлов Next.js
    location /_next/static/ {
        proxy_pass http://localhost:3000;
        proxy_cache_valid 200 365d;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    location /images/ {
        proxy_pass http://localhost:3000;
        proxy_cache_valid 200 7d;
        add_header Cache-Control "public, max-age=604800";
    }
}
```

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

---

### 5.2 Активация Конфигурации

```bash
ln -s /etc/nginx/sites-available/vnorku.ru /etc/nginx/sites-enabled/
```

---

### 5.3 Проверка Синтаксиса Nginx

```bash
nginx -t
```

Должно быть:

```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

---

### 5.4 Перезагрузка Nginx

```bash
systemctl reload nginx
```

---

### 5.5 Проверка Сайта (HTTP)

Откройте в браузере: `http://vnorku.ru`

Должна открыться главная страница сайта.

---

## Шаг 6: Получение SSL Сертификата (HTTPS)

### 6.1 Запуск Certbot

```bash
certbot --nginx -d vnorku.ru -d www.vnorku.ru
```

Certbot задаст несколько вопросов:

1. **Email:** укажите ваш email (для уведомлений об истечении сертификата)
2. **Terms of Service:** введите `A` (agree)
3. **Newsletter:** введите `N` (no) или `Y` (yes)
4. **Redirect HTTP → HTTPS:** введите `2` (рекомендуется)

Certbot автоматически:
- Получит SSL сертификат от Let's Encrypt
- Обновит конфигурацию Nginx
- Настроит автоматический redirect HTTP → HTTPS

---

### 6.2 Проверка HTTPS

Откройте в браузере: `https://vnorku.ru`

Должен быть:
- ✅ Зелёный замочек (валидный SSL)
- ✅ Сайт открывается корректно

---

### 6.3 Автообновление Сертификата

Certbot автоматически настраивает cron job для обновления сертификата. Проверьте:

```bash
systemctl status certbot.timer
```

Должно быть "active (running)".

Протестируйте обновление вручную:

```bash
certbot renew --dry-run
```

Если всё ок — сертификат будет автоматически обновляться каждые 60 дней.

---

## Шаг 7: Финальная Проверка

### 7.1 Чек-лист

- [ ] Сайт открывается по `https://vnorku.ru` ✅
- [ ] HTTP редиректит на HTTPS ✅
- [ ] Все страницы работают:
  - [ ] `/` (главная)
  - [ ] `/pricing` (тарифы)
  - [ ] `/calculator` (калькулятор)
  - [ ] `/faq` (FAQ)
  - [ ] `/partners` (партнёры)
  - [ ] `/how-it-works` (как это работает)
- [ ] Формы отправляют данные ✅
- [ ] API endpoints работают ✅
- [ ] Мобильная версия отображается корректно ✅
- [ ] SSL сертификат валидный (зелёный замочек) ✅

---

### 7.2 Lighthouse Audit

Откройте DevTools (Chrome):
1. F12 → Lighthouse
2. Выберите "Desktop" и "Mobile"
3. Запустите аудит

Цели:
- **Performance:** >90
- **Accessibility:** 100
- **Best Practices:** 100
- **SEO:** 100

Если что-то ниже — см. раздел "Оптимизация" ниже.

---

### 7.3 Проверка Логов PM2

```bash
pm2 logs vnorku-site --lines 50
```

Убедитесь, что нет ошибок (errors).

---

### 7.4 Мониторинг Ресурсов

```bash
pm2 monit
```

Проверьте CPU и Memory usage. Должно быть:
- CPU: 0-5% (в idle)
- Memory: 100-300 MB

Нажмите `Ctrl+C` для выхода.

---

## Шаг 8: Auto-Deploy (Опционально)

### 8.1 Создание Deploy Script

```bash
nano /var/www/vnorku/deploy.sh
```

Содержимое:

```bash
#!/bin/bash

echo "🚀 Starting deployment..."

# Navigate to project directory
cd /var/www/vnorku

# Pull latest changes from Git
echo "📥 Pulling latest changes from Git..."
git pull origin main

# Install dependencies (in case package.json changed)
echo "📦 Installing dependencies..."
npm install

# Build the project
echo "🔨 Building the project..."
npm run build

# Restart PM2
echo "🔄 Restarting PM2..."
pm2 restart vnorku-site

# Check status
echo "✅ Deployment completed! Status:"
pm2 status vnorku-site

echo "📊 Recent logs:"
pm2 logs vnorku-site --lines 10 --nostream

echo "🎉 Deployment finished successfully!"
```

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

---

### 8.2 Сделать Executable

```bash
chmod +x /var/www/vnorku/deploy.sh
```

---

### 8.3 Тестирование Deploy Script

```bash
cd /var/www/vnorku
./deploy.sh
```

Должно пройти без ошибок.

---

### 8.4 Использование

Теперь для обновления сайта достаточно:

```bash
ssh root@109.73.207.207
cd /var/www/vnorku
./deploy.sh
```

---

### 8.5 Автоматический Deploy через GitHub Webhook (Advanced)

**Опционально:** Можно настроить автоматический deploy при push в main.

1. Создать endpoint `/api/deploy` в Next.js
2. Проверять GitHub secret
3. Запускать `deploy.sh`

Инструкция: https://docs.github.com/en/webhooks

---

## Troubleshooting (Решение Проблем)

### Проблема 1: Сайт не открывается (502 Bad Gateway)

**Причина:** Next.js не запущен или упал.

**Решение:**

```bash
pm2 status
pm2 restart vnorku-site
pm2 logs vnorku-site
```

Проверьте логи на ошибки.

---

### Проблема 2: SSL сертификат не устанавливается

**Причина:** Домен не указывает на IP сервера.

**Решение:**

Проверьте DNS:

```bash
nslookup vnorku.ru
```

Должно вернуть IP: 109.73.207.207

Если нет — настройте A-запись в DNS провайдере домена.

---

### Проблема 3: Высокое использование памяти

**Причина:** Next.js может потреблять много памяти.

**Решение:**

Увеличьте RAM на VPS или оптимизируйте Next.js:

```bash
# Ограничение памяти для Node.js
pm2 delete vnorku-site
pm2 start npm --name "vnorku-site" --max-memory-restart 500M -- start
pm2 save
```

---

### Проблема 4: Nginx показывает 404

**Причина:** Конфигурация Nginx неверная.

**Решение:**

```bash
nginx -t
systemctl status nginx
cat /var/log/nginx/error.log
```

Проверьте конфигурацию в `/etc/nginx/sites-available/vnorku.ru`.

---

### Проблема 5: Build падает с ошибкой

**Причина:** Недостаточно RAM или ошибки в коде.

**Решение:**

```bash
# Проверьте логи
npm run build

# Если ошибка "JavaScript heap out of memory":
export NODE_OPTIONS="--max-old-space-size=4096"
npm run build
```

---

## Оптимизация (После Запуска)

### 1. Кэширование Nginx

Добавьте в `/etc/nginx/nginx.conf` (в блок `http`):

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=STATIC:10m inactive=7d use_temp_path=off;
```

Затем в конфигурации `/etc/nginx/sites-available/vnorku.ru`:

```nginx
location /_next/static/ {
    proxy_cache STATIC;
    proxy_pass http://localhost:3000;
    proxy_cache_valid 200 365d;
    add_header Cache-Control "public, max-age=31536000, immutable";
}
```

Перезагрузите Nginx:

```bash
systemctl reload nginx
```

---

### 2. Gzip Compression

Убедитесь, что Gzip включён в `/etc/nginx/nginx.conf`:

```nginx
gzip on;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 6;
gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss;
```

---

### 3. Security Headers

Добавьте в `/etc/nginx/sites-available/vnorku.ru` (в блок `server`):

```nginx
# Security headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

---

### 4. Rate Limiting (Защита от DDoS)

Добавьте в `/etc/nginx/nginx.conf` (в блок `http`):

```nginx
limit_req_zone $binary_remote_addr zone=mylimit:10m rate=10r/s;
```

В `/etc/nginx/sites-available/vnorku.ru` (в блок `location /`):

```nginx
limit_req zone=mylimit burst=20 nodelay;
```

---

## Мониторинг (Опционально)

### PM2 Dashboard

```bash
pm2 install pm2-server-monit
```

Откройте: `http://109.73.207.207:9615` (если открыт порт).

### Логи в Реальном Времени

```bash
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
pm2 logs vnorku-site --lines 100
```

---

## Backup (Резервное Копирование)

### 1. Backup БД (если используется PostgreSQL)

```bash
# Создать backup
pg_dump vnorku > /backups/vnorku_$(date +%Y%m%d).sql

# Восстановить backup
psql vnorku < /backups/vnorku_20250123.sql
```

### 2. Backup Сайта

```bash
# Создать архив
tar -czf /backups/vnorku_site_$(date +%Y%m%d).tar.gz /var/www/vnorku

# Восстановить
tar -xzf /backups/vnorku_site_20250123.tar.gz -C /var/www/
```

### 3. Автоматический Backup (Cron)

```bash
crontab -e
```

Добавьте:

```cron
# Backup сайта каждый день в 3:00 AM
0 3 * * * tar -czf /backups/vnorku_site_$(date +\%Y\%m\%d).tar.gz /var/www/vnorku

# Backup БД каждый день в 3:30 AM
30 3 * * * pg_dump vnorku > /backups/vnorku_db_$(date +\%Y\%m\%d).sql

# Удалить старые backups (>30 дней)
0 4 * * * find /backups -name "vnorku_*" -mtime +30 -delete
```

---

## Контакты

**Если что-то не работает:**

- Email: dev@vnorku.ru
- Telegram: @vnorku_dev

**Документация:**

- Next.js: https://nextjs.org/docs
- Nginx: https://nginx.org/en/docs/
- PM2: https://pm2.keymetrics.io/docs/
- Certbot: https://certbot.eff.org/

---

**Версия документа:** 1.0
**Дата создания:** 2025-01-23
**Последнее обновление:** 2025-01-23
