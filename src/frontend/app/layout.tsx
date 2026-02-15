import type { Metadata } from 'next'
import { Inter, JetBrains_Mono, Merriweather } from 'next/font/google'
import './globals.css'

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-inter',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
})

const merriweather = Merriweather({
  subsets: ['latin'],
  weight: ['400', '700'],
  variable: '--font-serif',
})

export const metadata: Metadata = {
  title: 'Atlas - Research Intelligence Platform',
  description: 'Professional knowledge graph and AI-powered research analysis platform',
  keywords: ['research', 'knowledge graph', 'AI', 'RAG', 'document analysis'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`dark ${inter.variable} ${jetbrainsMono.variable} ${merriweather.variable}`}>
      <body className={`${inter.className} dark bg-background text-foreground antialiased`}>
        {children}
      </body>
    </html>
  )
}
