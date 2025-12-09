'use client';

import Link from 'next/link';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { ArrowRight, CheckCircle2 } from 'lucide-react';

export default function HeroSection() {
  const features = [
    'Готовая корзина за 2 минуты',
    'Точность соблюдения плана по рациону ±5%',
    'Существенная экономия времени',
  ];

  return (
    <section className="relative overflow-hidden bg-gradient-to-br from-primary-50 via-white to-accent-50 section-padding">
      <div className="container-custom">
        <div className="grid gap-12 lg:grid-cols-2 lg:gap-16 items-center">
          {/* Left Column - Text Content */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="space-y-8"
          >
            <div className="space-y-4">
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-gray-900">
                Персональный нутрициолог{' '}
                <span className="bg-gradient-to-r from-primary-500 to-accent-500 bg-clip-text text-transparent">в кармане</span>
              </h1>
              <p className="text-lg md:text-xl text-gray-600 leading-relaxed">
                Готовые продуктовые корзины, которые гарантируют соблюдение вашего плана по питанию с точностью{' '}
                <span className="font-semibold text-primary-600">±5%</span>
              </p>
            </div>

            {/* Feature List */}
            <ul className="space-y-3">
              {features.map((feature, index) => (
                <motion.li
                  key={feature}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.5, delay: 0.2 + index * 0.1 }}
                  className="flex items-center space-x-3"
                >
                  <CheckCircle2 className="h-5 w-5 text-pea-500 flex-shrink-0" />
                  <span className="text-gray-700">{feature}</span>
                </motion.li>
              ))}
            </ul>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-4">
              <Link
                href="https://t.me/Coffeematebot"
                target="_blank"
                rel="noopener noreferrer"
                className="group inline-flex items-center justify-center rounded-lg bg-gradient-to-r from-primary-500 to-primary-600 px-6 py-3 text-base font-semibold text-white hover:from-primary-600 hover:to-primary-700 transition-all shadow-lg hover:shadow-glow-primary"
              >
                Попробовать бесплатно
                <ArrowRight className="ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
              </Link>
              <Link
                href="/calculator"
                className="inline-flex items-center justify-center rounded-lg border-2 border-accent-400 px-6 py-3 text-base font-semibold text-accent-600 hover:bg-accent-50 hover:border-accent-500 transition-colors"
              >
                Рассчитать калории
              </Link>
            </div>

            {/* Social Proof */}
            <div className="flex items-center space-x-6 text-sm text-gray-600">
              <div className="flex items-center space-x-2">
                <div className="flex -space-x-2">
                  {[1, 2, 3, 4].map((i) => (
                    <div
                      key={i}
                      className="h-8 w-8 rounded-full bg-gradient-to-br from-primary-400 to-accent-500 ring-2 ring-white"
                    />
                  ))}
                </div>
                <span className="font-medium">2,500+ пользователей</span>
              </div>
              <div className="flex items-center space-x-1">
                <span className="text-accent-500">★★★★★</span>
                <span className="font-medium">4.9/5</span>
              </div>
            </div>
          </motion.div>

          {/* Right Column - Hero Image with Logo */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="relative"
          >
            <div className="relative rounded-3xl bg-gradient-to-br from-primary-100 via-accent-50 to-pea-100 p-8 shadow-2xl">
              {/* Logo Image */}
              <div className="relative mx-auto max-w-[400px] rounded-2xl overflow-hidden shadow-xl">
                <Image
                  src="/images/logo.jpeg"
                  alt="Внорку - хомячок с горошком и кофе"
                  width={400}
                  height={400}
                  className="object-cover"
                  priority
                />
                {/* Neon glow overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-primary-500/20 to-transparent pointer-events-none" />
              </div>

              {/* Floating Stats */}
              <motion.div
                animate={{ y: [0, -10, 0] }}
                transition={{ duration: 3, repeat: Infinity }}
                className="absolute top-4 right-4 bg-white rounded-xl shadow-lg p-3 border border-primary-100"
              >
                <div className="text-xs text-gray-600">Точность</div>
                <div className="text-xl font-bold bg-gradient-to-r from-primary-500 to-pea-500 bg-clip-text text-transparent">±5%</div>
              </motion.div>

              <motion.div
                animate={{ y: [0, 10, 0] }}
                transition={{ duration: 3, repeat: Infinity, delay: 0.5 }}
                className="absolute bottom-4 left-4 bg-white rounded-xl shadow-lg p-3 border border-accent-100"
              >
                <div className="text-xs text-gray-600">Экономия</div>
                <div className="text-xl font-bold text-accent-600">времени</div>
              </motion.div>

              <motion.div
                animate={{ y: [0, -8, 0] }}
                transition={{ duration: 2.5, repeat: Infinity, delay: 1 }}
                className="absolute bottom-4 right-4 bg-white rounded-xl shadow-lg p-3 border border-pea-100"
              >
                <div className="text-xs text-gray-600">Свежие продукты</div>
                <div className="text-xl font-bold text-pea-600">🥦 каждый день</div>
              </motion.div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
