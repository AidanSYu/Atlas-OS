import type { Metadata } from 'next'
import { Inter, Sora, IBM_Plex_Mono } from 'next/font/google'
import './globals.css'
import ToastContainer from '@/components/ToastContainer'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
})

const sora = Sora({
  subsets: ['latin'],
  variable: '--font-display',
})

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-mono',
})

export const metadata: Metadata = {
  title: 'Atlas - Research OS',
  description: 'Professional spatial research and intelligence platform',
  keywords: ['research', 'knowledge graph', 'AI', 'RAG', 'document analysis'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`dark ${inter.variable} ${sora.variable} ${ibmPlexMono.variable}`}>
      <body className={`${inter.className} dark bg-background text-foreground antialiased`}>
        {children}
        <ToastContainer />
      </body>
    </html>
  )
}
