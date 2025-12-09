import type { Metadata } from 'next';
import '@/styles/globals.css';
import Header from '@/components/layout/Header';
import Footer from '@/components/layout/Footer';

export const metadata: Metadata = {
  metadataBase: new URL('https://vnorku.ru'),
  title: 'Внорку - Персональный нутрициолог для контроля рациона',
  description: 'Готовые продуктовые корзины, которые гарантируют соблюдение вашего плана по питанию с точностью ±5%',
  keywords: ['питание', 'калории', 'нутрициолог', 'здоровье', 'диета', 'доставка продуктов'],
  authors: [{ name: 'Внорку' }],
  icons: {
    icon: '/favicon.ico',
    apple: '/apple-touch-icon.png',
  },
  openGraph: {
    type: 'website',
    locale: 'ru_RU',
    url: 'https://vnorku.ru',
    siteName: 'Внорку',
    title: 'Внорку - Персональный нутрициолог для контроля рациона',
    description: 'Готовые продуктовые корзины с точностью соблюдения плана питания ±5%',
    images: [
      {
        url: '/images/logo.jpeg',
        width: 1200,
        height: 630,
        alt: 'Внорку - хомячок с горошком',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Внорку - Персональный нутрициолог',
    description: 'Готовые продуктовые корзины с точностью соблюдения плана питания ±5%',
    images: ['/images/logo.jpeg'],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-white text-gray-900 antialiased font-sans">
        <Header />
        <main>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
