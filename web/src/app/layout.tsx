import type { Metadata } from "next";
import "./globals.css";
import AuthGuard from "@/components/AuthGuard";

export const metadata: Metadata = {
  title: "UPSC 10-Day Prep",
  description: "AI-powered adaptive UPSC Prelims preparation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen font-sans antialiased">
        <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-6 text-sm">
          <span className="font-bold text-amber-400 mr-4">UPSC Sprint</span>
          {[
            ["Dashboard", "/"],
            ["Diagnostic", "/diagnostic"],
            ["Session", "/session"],
            ["History", "/sessions"],
            ["Tracker", "/tracker"],
            ["Planner", "/planner"],
            ["Strategy", "/strategy"],
            ["CSAT", "/csat"],
            ["Attest", "/attestation"],
            ["Analysis", "/analysis"],
            ["PYQ", "/pyq"],
            ["Exam Sim", "/exam-sim"],
            ["Setup", "/setup"],
          ].map(([label, href]) => (
            <a key={href} href={href} className="text-gray-400 hover:text-white transition-colors">
              {label}
            </a>
          ))}
        </nav>
        <AuthGuard>
          <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
        </AuthGuard>
      </body>
    </html>
  );
}
