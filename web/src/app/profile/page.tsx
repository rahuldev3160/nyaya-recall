"use client";

import { useEffect, useState } from "react";

interface StreakData {
  current_streak: number;
  longest_streak: number;
  last_activity_date: string | null;
  shield_enabled: boolean;
  max_grace_per_week: number;
}

interface UsernameOption {
  username: string;
  available: boolean;
}

export default function ProfilePage() {
  const [streak, setStreak] = useState<StreakData | null>(null);
  const [usernameOptions, setUsernameOptions] = useState<UsernameOption[]>([]);
  const [currentUsername, setCurrentUsername] = useState<string>("Aspirant");
  const [claiming, setClaiming] = useState(false);
  const [claimMsg, setClaimMsg] = useState<string | null>(null);
  const [shieldEnabled, setShieldEnabled] = useState(true);
  const [gracePerWeek, setGracePerWeek] = useState(1);
  const [savingConfig, setSavingConfig] = useState(false);

  useEffect(() => {
    fetch("/api/backend/questions/streak")
      .then((r) => r.json())
      .then((d) => {
        setStreak(d);
        setShieldEnabled(d.shield_enabled ?? true);
        setGracePerWeek(d.max_grace_per_week ?? 1);
      })
      .catch(() => null);

    fetch("/api/backend/questions/username/options")
      .then((r) => r.json())
      .then((d) => {
        if (d.current) setCurrentUsername(d.current);
        if (d.options) setUsernameOptions(d.options);
      })
      .catch(() => null);
  }, []);

  async function claimUsername(username: string) {
    setClaiming(true);
    setClaimMsg(null);
    try {
      const res = await fetch("/api/backend/questions/username/claim", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username }),
      });
      const data = await res.json();
      if (data.success) {
        setCurrentUsername(username);
        setClaimMsg("Username updated!");
      } else {
        setClaimMsg(data.detail ?? "Could not claim username.");
      }
    } catch {
      setClaimMsg("Request failed.");
    } finally {
      setClaiming(false);
    }
  }

  async function saveStreakConfig() {
    setSavingConfig(true);
    try {
      await fetch("/api/backend/questions/streak/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shield_enabled: shieldEnabled,
          max_grace_per_week: gracePerWeek,
        }),
      });
    } catch {
      // Silent — non-critical
    } finally {
      setSavingConfig(false);
    }
  }

  return (
    <div className="max-w-lg flex flex-col gap-6 py-2">
      <h1 className="text-xl font-bold text-white">Profile</h1>

      {/* Username card */}
      <section className="rounded-xl border border-gray-700 bg-gray-900 p-5 space-y-4">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Your username</p>
          <p className="text-xl font-bold text-amber-400">{currentUsername}</p>
        </div>

        {usernameOptions.length > 0 && (
          <div>
            <p className="text-xs text-gray-500 mb-2">Pick a different one (editable once per 30 days)</p>
            <div className="flex flex-col gap-2">
              {usernameOptions.map((opt) => (
                <button
                  key={opt.username}
                  disabled={!opt.available || claiming || opt.username === currentUsername}
                  onClick={() => claimUsername(opt.username)}
                  className={`text-left rounded-lg border px-4 py-2.5 text-sm transition-all ${
                    opt.username === currentUsername
                      ? "border-amber-600 bg-amber-900/20 text-amber-300"
                      : opt.available
                      ? "border-gray-700 text-gray-300 hover:border-amber-600 hover:text-white cursor-pointer"
                      : "border-gray-800 text-gray-600 cursor-not-allowed opacity-50"
                  }`}
                >
                  {opt.username}
                  {opt.username === currentUsername && (
                    <span className="ml-2 text-xs text-amber-500">current</span>
                  )}
                  {!opt.available && opt.username !== currentUsername && (
                    <span className="ml-2 text-xs text-gray-600">taken</span>
                  )}
                </button>
              ))}
            </div>
            {claimMsg && (
              <p className={`text-xs mt-2 ${claimMsg.includes("!") ? "text-green-400" : "text-red-400"}`}>
                {claimMsg}
              </p>
            )}
          </div>
        )}
      </section>

      {/* Streak card */}
      {streak && (
        <section className="rounded-xl border border-gray-700 bg-gray-900 p-5 space-y-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Streak</p>
          <div className="flex gap-6">
            <div>
              <p className="text-3xl font-bold text-orange-400">{streak.current_streak}</p>
              <p className="text-xs text-gray-500">current</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-gray-300">{streak.longest_streak}</p>
              <p className="text-xs text-gray-500">longest</p>
            </div>
          </div>

          {/* Shield config */}
          <div className="border-t border-gray-800 pt-4 space-y-3">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Streak Shield</p>
            <label className="flex items-center gap-3 cursor-pointer">
              <div
                onClick={() => setShieldEnabled((v) => !v)}
                className={`w-10 h-5 rounded-full transition-colors relative cursor-pointer ${
                  shieldEnabled ? "bg-amber-500" : "bg-gray-700"
                }`}
              >
                <div
                  className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                    shieldEnabled ? "translate-x-5" : "translate-x-0.5"
                  }`}
                />
              </div>
              <span className="text-sm text-gray-300">Enable shield</span>
            </label>

            {shieldEnabled && (
              <div>
                <p className="text-xs text-gray-500 mb-2">Grace days per week (resets Monday)</p>
                <div className="flex gap-2">
                  {[0, 1, 2].map((n) => (
                    <button
                      key={n}
                      onClick={() => setGracePerWeek(n)}
                      className={`rounded-lg border px-4 py-1.5 text-sm transition-colors ${
                        gracePerWeek === n
                          ? "border-amber-600 bg-amber-900/30 text-amber-300"
                          : "border-gray-700 text-gray-400 hover:border-gray-500"
                      }`}
                    >
                      {n} {n === 1 ? "day" : "days"}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={saveStreakConfig}
              disabled={savingConfig}
              className="text-xs text-amber-400 hover:text-amber-300 disabled:opacity-50"
            >
              {savingConfig ? "Saving…" : "Save preferences"}
            </button>
          </div>
        </section>
      )}

      {/* Tier */}
      <section className="rounded-xl border border-gray-700 bg-gray-900 p-5 flex items-center justify-between">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Plan</p>
          <p className="text-sm font-semibold text-white">Free</p>
        </div>
        <a
          href="/pricing"
          className="text-xs text-amber-400 border border-amber-700 rounded-lg px-3 py-1.5 hover:bg-amber-900/20 transition-colors"
        >
          View Pro →
        </a>
      </section>
    </div>
  );
}
