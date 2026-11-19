import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AuthProvider } from "@/providers/auth-provider";
import { SSEProvider } from "@/providers/sse-provider";
import { ToastProvider } from "@/components/ui/toast";
import { AuthGuard } from "@/components/layout/auth-guard";

export const metadata: Metadata = {
  title: "ClipDeck — Live Stream Clipping Platform",
  description: "Personal live-stream moment detection and DVR buffer clipping platform",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "ClipDeck",
  },
};

export const viewport: Viewport = {
  themeColor: "#0D0D0D",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="icon" href="/icon-192.svg" type="image/svg+xml" />
        <link rel="apple-touch-icon" href="/icon-192.svg" />
      </head>
      <body className="bg-background text-foreground antialiased min-h-screen selection:bg-accent selection:text-white">
        <ToastProvider>
          <AuthProvider>
            <SSEProvider>
              <AuthGuard>{children}</AuthGuard>
            </SSEProvider>
          </AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
