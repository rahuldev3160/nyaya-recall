"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { supabase } from "@/lib/supabase";

export default function AuthCallbackPage() {
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) {
        router.replace("/");
      } else {
        router.replace("/login?error=true");
      }
    });
  }, [router, params]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <p className="text-gray-400 text-sm">Signing you in…</p>
    </div>
  );
}
