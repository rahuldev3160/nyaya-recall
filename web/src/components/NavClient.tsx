"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const SIDEBAR_LINKS: { label: string; href: string; icon: string }[] = [
  { icon: "🏠", label: "Dashboard", href: "/" },
  { icon: "⚡", label: "Practice", href: "/practice" },
  { icon: "📚", label: "PYQ Browser", href: "/pyq" },
  { icon: "📊", label: "Progress", href: "/tracker" },
  { icon: "🏆", label: "Leaderboard", href: "/leaderboard" },
];

const SIDEBAR_BOTTOM: { label: string; href: string; icon: string }[] = [
  { icon: "👤", label: "Profile", href: "/profile" },
];

const MOBILE_LINKS: { label: string; href: string; icon: string; primary?: boolean }[] = [
  { icon: "🏠", label: "Home", href: "/" },
  { icon: "⚡", label: "Practice", href: "/practice", primary: true },
  { icon: "📚", label: "PYQs", href: "/pyq" },
  { icon: "📊", label: "Progress", href: "/tracker" },
  { icon: "👤", label: "Profile", href: "/profile" },
];

export default function NavClient() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <>
      {/* ── Desktop sidebar ── */}
      <aside className="hidden md:flex fixed top-0 left-0 h-full w-56 flex-col border-r border-gray-800 bg-gray-950 z-30">
        {/* Brand */}
        <div className="px-5 py-5 border-b border-gray-800">
          <span className="font-bold text-amber-400 text-base tracking-tight">NYAYA RECALL</span>
        </div>

        {/* Primary links */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {SIDEBAR_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive(link.href)
                  ? "bg-gray-800 text-white"
                  : "text-gray-400 hover:text-white hover:bg-gray-900"
              }`}
            >
              <span className="text-base w-5 text-center">{link.icon}</span>
              {link.label}
            </Link>
          ))}

          {/* Separator */}
          <div className="border-t border-gray-800 my-2" />

          {SIDEBAR_BOTTOM.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive(link.href)
                  ? "bg-gray-800 text-white"
                  : "text-gray-400 hover:text-white hover:bg-gray-900"
              }`}
            >
              <span className="text-base w-5 text-center">{link.icon}</span>
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Legacy tools — collapsed by default on desktop */}
        <div className="px-3 pb-4 border-t border-gray-800 pt-3">
          <p className="text-xs text-gray-600 px-3 mb-2 uppercase tracking-wider">Tools</p>
          {[
            ["Diagnostic", "/diagnostic"],
            ["Session", "/session"],
            ["CSAT", "/csat"],
            ["Strategy", "/strategy"],
            ["Analysis", "/analysis"],
            ["Setup", "/setup"],
          ].map(([label, href]) => (
            <Link
              key={href}
              href={href}
              className={`flex items-center px-3 py-1.5 rounded-lg text-xs transition-colors ${
                isActive(href)
                  ? "text-white bg-gray-800"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              {label}
            </Link>
          ))}
        </div>
      </aside>

      {/* ── Mobile bottom tab bar ── */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-30 border-t border-gray-800 bg-gray-950 flex items-stretch">
        {MOBILE_LINKS.map((link) => {
          const active = isActive(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`flex-1 flex flex-col items-center justify-center py-2 gap-0.5 transition-colors ${
                link.primary
                  ? active
                    ? "text-blue-400"
                    : "text-blue-500 hover:text-blue-400"
                  : active
                  ? "text-white"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              <span className={link.primary ? "text-xl" : "text-lg"}>{link.icon}</span>
              <span className={`text-[10px] font-medium ${link.primary ? "text-xs" : ""}`}>
                {link.label}
              </span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
