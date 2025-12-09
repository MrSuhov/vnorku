import Link from 'next/link';
import Image from 'next/image';
import { Instagram, Send, Mail } from 'lucide-react';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  const footerLinks = {
    product: [
      { name: 'Как это работает', href: '/#how-it-works' },
      { name: 'Тарифы', href: '/pricing' },
      { name: 'Калькулятор калорий', href: '/calculator' },
      { name: 'FAQ', href: '/faq' },
    ],
    company: [
      { name: 'О нас', href: '/about' },
      { name: 'Блог', href: '/blog' },
      { name: 'Партнёрам', href: '/partners' },
      { name: 'Контакты', href: '/contact' },
    ],
    legal: [
      { name: 'Политика конфиденциальности', href: '/privacy' },
      { name: 'Условия использования', href: '/terms' },
      { name: 'Оферта', href: '/offer' },
    ],
  };

  return (
    <footer className="border-t bg-gradient-to-b from-gray-50 to-primary-50/30">
      <div className="container-custom py-12 md:py-16">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-4">
          {/* Brand Section */}
          <div className="space-y-4">
            <Link href="/" className="flex items-center space-x-2">
              <div className="h-10 w-10 rounded-full overflow-hidden shadow-md">
                <Image
                  src="/images/logo.jpeg"
                  alt="Внорку"
                  width={40}
                  height={40}
                  className="object-cover"
                />
              </div>
              <span className="font-bold text-xl bg-gradient-to-r from-primary-500 to-accent-500 bg-clip-text text-transparent">Внорку</span>
            </Link>
            <p className="text-sm text-gray-600">
              Персональный нутрициолог для контроля рациона
            </p>
            <div className="flex space-x-4">
              <a
                href="https://t.me/Coffeematebot"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-600 hover:text-primary-500 transition-colors"
              >
                <Send className="h-5 w-5" />
              </a>
              <a
                href="https://instagram.com/vnorku"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-600 hover:text-accent-500 transition-colors"
              >
                <Instagram className="h-5 w-5" />
              </a>
              <a
                href="mailto:dev@vnorku.ru"
                className="text-gray-600 hover:text-pea-500 transition-colors"
              >
                <Mail className="h-5 w-5" />
              </a>
            </div>
          </div>

          {/* Product Links */}
          <div>
            <h3 className="font-semibold text-gray-900 mb-4">Продукт</h3>
            <ul className="space-y-3">
              {footerLinks.product.map((link) => (
                <li key={link.name}>
                  <Link
                    href={link.href}
                    className="text-sm text-gray-600 hover:text-primary-500 transition-colors"
                  >
                    {link.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Company Links */}
          <div>
            <h3 className="font-semibold text-gray-900 mb-4">Компания</h3>
            <ul className="space-y-3">
              {footerLinks.company.map((link) => (
                <li key={link.name}>
                  <Link
                    href={link.href}
                    className="text-sm text-gray-600 hover:text-primary-500 transition-colors"
                  >
                    {link.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Legal Links */}
          <div>
            <h3 className="font-semibold text-gray-900 mb-4">Правовая информация</h3>
            <ul className="space-y-3">
              {footerLinks.legal.map((link) => (
                <li key={link.name}>
                  <Link
                    href={link.href}
                    className="text-sm text-gray-600 hover:text-primary-500 transition-colors"
                  >
                    {link.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="mt-12 border-t pt-8 flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
          <p className="text-sm text-gray-600">
            © {currentYear} Внорку. Все права защищены.
          </p>
          <div className="flex space-x-6">
            <Link
              href="/privacy"
              className="text-sm text-gray-600 hover:text-primary-500 transition-colors"
            >
              Конфиденциальность
            </Link>
            <Link
              href="/terms"
              className="text-sm text-gray-600 hover:text-primary-500 transition-colors"
            >
              Условия
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
