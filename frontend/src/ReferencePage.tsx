import { useMemo } from "react";

type ReferencePageProps = {
  title: string;
  filename?: string;
};

export default function ReferencePage({ title, filename }: ReferencePageProps) {
  const safeTitle = useMemo(() => {
    const trimmed = title.trim();
    return trimmed.length > 0 ? trimmed : "unknown";
  }, [title]);
  const safeFilename = useMemo(() => {
    const trimmed = filename?.trim();
    return trimmed ? trimmed : null;
  }, [filename]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100 text-slate-900">
      <div className="flex min-h-screen items-center justify-center px-6 py-10">
        <div className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white/90 p-8 text-center shadow-xl shadow-slate-200/60 backdrop-blur">
          <div className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">
            Reference
          </div>
          <h1 className="mt-3 text-2xl font-semibold text-slate-900">
            This is a page for <span className="text-slate-700">{safeTitle}</span>!
          </h1>
          <p className="mt-3 text-sm text-slate-500">
            Your content could go here.
          </p>
          {safeFilename && (
            <p className="mt-2 text-xs uppercase tracking-[0.2em] text-slate-400">
              File: {safeFilename}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
