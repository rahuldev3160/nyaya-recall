"use client";

type Confidence = "sure" | "unsure" | "guess";

interface ConfidenceSelectorProps {
  value: Confidence | null;
  onChange: (v: Confidence) => void;
  disabled?: boolean;
}

const OPTIONS: { key: Confidence; label: string; selected: string; unselected: string }[] = [
  {
    key: "sure",
    label: "Sure",
    selected: "border-green-700 bg-green-950 text-green-400",
    unselected: "border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-500 hover:text-gray-200",
  },
  {
    key: "unsure",
    label: "Unsure",
    selected: "border-amber-700 bg-amber-950 text-amber-400",
    unselected: "border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-500 hover:text-gray-200",
  },
  {
    key: "guess",
    label: "Guessing",
    selected: "border-gray-500 bg-gray-700 text-gray-300",
    unselected: "border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-500 hover:text-gray-200",
  },
];

export default function ConfidenceSelector({
  value,
  onChange,
  disabled = false,
}: ConfidenceSelectorProps) {
  return (
    <div className="space-y-1.5">
      <div className="flex gap-2">
        {OPTIONS.map((opt) => (
          <button
            key={opt.key}
            type="button"
            onClick={() => !disabled && onChange(opt.key)}
            disabled={disabled}
            className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors ${
              value === opt.key ? opt.selected : opt.unselected
            } ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <p className="text-xs text-gray-500">
        How confident are you? (This helps your revision schedule)
      </p>
    </div>
  );
}
