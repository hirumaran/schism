import type React from "react"
import type { Metadata } from "next"
import { Analytics } from "@vercel/analytics/next"
import { Providers } from "@/components/providers"
import { Topbar } from "@/components/topbar/topbar"
import { SettingsModal } from "@/components/settings/settings-modal"
import { DocsDrawer } from "@/components/docs/docs-drawer"
import { ToastContainer } from "@/components/shared/toast-container"
import "./globals.css"

export const metadata: Metadata = {
  title: "Schism — Research Contradiction Finder",
  description:
    "Upload your paper, extract empirical claims, and discover what the literature disagrees with in your research.",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <Providers>
          <Topbar />
          <main>{children}</main>
          <SettingsModal />
          <DocsDrawer />
          <ToastContainer />
        </Providers>
        <Analytics />
      </body>
    </html>
  )
}
