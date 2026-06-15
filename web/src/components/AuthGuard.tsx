"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { getSession } from "@/lib/auth";

const PUBLIC_PATHS = ["/login", "/auth/callback"];

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Always allow public auth pages — prevents infinite redirect loop
    if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
      setReady(true);
      return;
    }
    // Skip auth check if Supabase is not configured (single-user / local dev mode)
    if (!process.env.NEXT_PUBLIC_SUPABASE_URL) {
      setReady(true);
      return;
    }
    getSession().then((session) => {
      if (!session) {
        router.replace("/login");
      } else {
        setReady(true);
      }
    });
  }, [router, pathname]);

  if (!ready) return null;
  return <>{children}</>;
}
