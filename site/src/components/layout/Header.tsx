'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Menu, X } from 'lucide-react';

export default function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const navigation = [
    { name: 'Главная', href: '/' },
    { name: 'Как это работает', href: '/#how-it-works' },
    { name: 'Тарифы', href: '/pricing' },
    { name: 'Калькулятор', href: '/calculator' },
    { name: 'FAQ', href: '/faq' },
    { name: 'Партнёрам', href: '/partners' },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/60">
      <nav className="container-custom">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-2">
            <div className="h-10 w-10 rounded-full overflow-hidden shadow-md">
              <Image
                src="/images/logo.jpeg"
                alt="Внорку - хомячок с горошком"
                width={40}
                height={40}
                className="object-cover"
                priority
              />
            </div>
            <span className="font-bold text-xl bg-gradient-to-r from-primary-500 to-accent-500 bg-clip-text text-transparent">Внорку</span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex md:items-center md:space-x-6">
            {navigation.map((item) => (
              <Link
                key={item.name}
                href={item.href}
                className="text-sm font-medium text-gray-700 hover:text-primary-500 transition-colors"
              >
                {item.name}
              </Link>
            ))}
          </div>

          {/* CTA Button */}
          <div className="hidden md:flex md:items-center md:space-x-4">
            <Link
              href="https://t.me/Coffeematebot"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg bg-primary-500 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-600 transition-colors"
            >
              Начать бесплатно
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <button
            type="button"
            className="md:hidden rounded-md p-2 text-gray-700 hover:bg-gray-100"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          >
            {isMenuOpen ? (
              <X className="h-6 w-6" />
            ) : (
              <Menu className="h-6 w-6" />
            )}
          </button>
        </div>

        {/* Mobile Menu */}
        {isMenuOpen && (
          <div className="md:hidden py-4 space-y-2">
            {navigation.map((item) => (
              <Link
                key={item.name}
                href={item.href}
                className="block px-3 py-2 text-base font-medium text-gray-700 hover:bg-gray-50 rounded-md"
                onClick={() => setIsMenuOpen(false)}
              >
                {item.name}
              </Link>
            ))}
            <Link
              href="https://t.me/Coffeematebot"
              target="_blank"
              rel="noopener noreferrer"
              className="block mx-3 mt-4 rounded-lg bg-primary-500 px-4 py-2 text-center text-sm font-semibold text-white hover:bg-primary-600 transition-colors"
              onClick={() => setIsMenuOpen(false)}
            >
              Начать бесплатно
            </Link>
          </div>
        )}
      </nav>
    </header>
  );
}
