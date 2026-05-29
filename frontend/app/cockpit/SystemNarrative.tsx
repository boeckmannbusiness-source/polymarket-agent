"use client";

export default function SystemNarrative({
  text,
}: {
  text: string | null;
}) {
  if (!text) return null;
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-5 py-3">
      <p className="text-sm text-gray-200 italic">&ldquo;{text}&rdquo;</p>
    </div>
  );
}
