import type { Metadata } from "next";
import "./globals.css";
import AuthGuard from "@/components/AuthGuard";
import NavClient from "@/components/NavClient";

export const metadata: Metadata = {
  title: "Nyaya Recall",
  description: "AI-powered adaptive UPSC Prelims preparation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen font-sans antialiased">
        <NavClient />
        <AuthGuard>
          {/* On desktop: push content right of sidebar (ml-56). On mobile: add bottom padding for tab bar. */}
          <main className="md:ml-56 pb-20 md:pb-0 max-w-4xl mx-auto px-4 md:px-8 py-8">
            {children}
          </main>
        </AuthGuard>
      </body>
    </html>
  );
}
