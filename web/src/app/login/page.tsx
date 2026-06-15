"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { signInWithMagicLink, signInWithGoogle, getSession } from "@/lib/auth";
import { useEffect } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getSession().then((s) => {
      if (s) router.replace("/");
    });
  }, [router]);

  async function handleMagicLink(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const { error: err } = await signInWithMagicLink(email);
    setLoading(false);
    if (err) {
      setError(err.message);
    } else {
      setSent(true);
    }
  }

  async function handleGoogle() {
    setError("");
    const { error: err } = await signInWithGoogle();
    if (err) setError(err.message);
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <div className="w-full max-w-sm bg-gray-900 rounded-xl p-8 border border-gray-800">
        <h1 className="text-2xl font-bold text-amber-400 mb-2">Nyaya Recall</h1>
        <p className="text-gray-400 text-sm mb-8">The logic of getting in.</p>

        {sent ? (
          <p className="text-green-400 text-sm">Check your email — magic link sent.</p>
        ) : (
          <>
            <form onSubmit={handleMagicLink} className="space-y-4 mb-4">
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-amber-500"
              />
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-amber-500 hover:bg-amber-400 text-gray-950 font-semibold rounded-lg py-2 text-sm transition-colors disabled:opacity-50"
              >
                {loading ? "Sending…" : "Send magic link"}
              </button>
            </form>

            <div className="relative my-4">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-700" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-gray-900 px-2 text-gray-500">or</span>
              </div>
            </div>

            <button
              onClick={handleGoogle}
              className="w-full border border-gray-700 hover:border-gray-500 rounded-lg py-2 text-sm text-gray-300 transition-colors"
            >
              Continue with Google
            </button>
          </>
        )}

        {error && <p className="mt-4 text-red-400 text-xs">{error}</p>}
      </div>
    </div>
  );
}
