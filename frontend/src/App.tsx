import { ChatKit, useChatKit } from "@openai/chatkit-react";
import { CgClose, CgFileDocument, CgOptions } from "react-icons/cg";
import { useCallback, useEffect, useState } from "react";

const CHATKIT_API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/chatkit";
const CHATKIT_API_DOMAIN_KEY = import.meta.env.VITE_CHATKIT_API_DOMAIN_KEY ?? "domain_pk_localhost_dev";

type ReferenceSource = {
  key: string;
  title: string;
  subtitle?: string;
  kind: "url" | "file" | "entity" | "unknown";
};

function openReferencePage(filename: string) {
  const safeFilename = filename.trim() || "unknown";
  const url = `/#reference?filename=${encodeURIComponent(safeFilename)}`;
  window.open(url, "_blank", "noopener,noreferrer");
}

function ReferencesWidgetPanel({
  colorScheme,
  accentColor,
  activeThreadId,
  isLoadingReferences,
  referenceSources,
}: {
  colorScheme: "light" | "dark";
  accentColor: string;
  activeThreadId: string | null;
  isLoadingReferences: boolean;
  referenceSources: ReferenceSource[];
}) {
  const panelClasses = [
    "h-full rounded-2xl border shadow-sm overflow-hidden",
    colorScheme === "dark" ? "border-slate-800 bg-gray-900" : "border-gray-200 bg-white",
  ].join(" ");

  return (
    <div className={panelClasses}>
      <div className="h-full w-full overflow-y-auto p-4">
        <div className="flex flex-col gap-3">
          <div className={`text-lg font-semibold ${colorScheme === "dark" ? "text-gray-200" : "text-gray-900"}`}>
            Sources
          </div>
          <div className={`text-sm ${colorScheme === "dark" ? "text-gray-400" : "text-gray-500"}`}>
            {activeThreadId ? "From the latest assistant response" : "Start chatting to see references"}
          </div>
          <div className={`${colorScheme === "dark" ? "bg-slate-700" : "bg-gray-200"} h-px w-full`} />

          {isLoadingReferences && (
            <div className={`${colorScheme === "dark" ? "text-gray-200" : "text-gray-700"} text-md`}>
              Loading references...
            </div>
          )}

          {!isLoadingReferences && referenceSources.length === 0 && (
            <div className={`${colorScheme === "dark" ? "text-gray-200" : "text-gray-700"} text-md`}>
              No references found in the latest response.
            </div>
          )}

          {!isLoadingReferences && referenceSources.length > 0 && (
            <div className="flex flex-col gap-2">
              {referenceSources.map((source) => {
                const filename = source.kind === "file" && source.subtitle ? source.subtitle : source.title;
                const cardClasses = [
                  "flex items-center justify-between gap-3 rounded-xl px-3 py-2",
                  "transition-colors",
                  colorScheme === "dark"
                    ? "bg-slate-700/60 hover:bg-slate-900/80 border border-slate-800"
                    : "bg-slate-50 hover:bg-white border border-slate-200",
                ].join(" ");
                const visitClasses = [
                  "shrink-0 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide cursor-pointer",
                  "text-white transition-opacity hover:opacity-90",
                ].join(" ");

                return (
                  <div key={source.key} className={cardClasses}>
                    <div className="flex min-w-0 items-start gap-2">
                      <div
                        className={[
                          "mt-0.5 flex h-7 w-7 items-center justify-center rounded-md border",
                          colorScheme === "dark"
                            ? "border-slate-700 bg-slate-800 text-slate-200"
                            : "border-slate-200 bg-white text-slate-600",
                        ].join(" ")}
                        aria-hidden="true"
                      >
                        <CgFileDocument className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <div className={`text-md font-semibold ${colorScheme === "dark" ? "text-gray-100" : "text-gray-900"}`}>
                          {source.title}
                        </div>
                        <div className={`text-sm ${colorScheme === "dark" ? "text-gray-400" : "text-gray-500"}`}>
                          {source.subtitle ?? source.kind.toUpperCase()}
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => openReferencePage(filename)}
                      className={visitClasses}
                      style={{ backgroundColor: accentColor }}
                    >
                      Visit
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SettingsDrawer({
  isOpen,
  onClose,
  colorScheme,
  radius,
  density,
  accentColor,
  onColorSchemeChange,
  onRadiusChange,
  onDensityChange,
  onAccentColorChange,
}: {
  isOpen: boolean;
  onClose: () => void;
  colorScheme: "light" | "dark";
  radius: "pill" | "round" | "soft" | "sharp";
  density: "compact" | "normal" | "spacious";
  accentColor: string;
  onColorSchemeChange: (value: "light" | "dark") => void;
  onRadiusChange: (value: "pill" | "round" | "soft" | "sharp") => void;
  onDensityChange: (value: "compact" | "normal" | "spacious") => void;
  onAccentColorChange: (value: string) => void;
}) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50">
      <button
        type="button"
        aria-label="Close settings"
        className="absolute inset-0 bg-slate-900/35 backdrop-blur-[1px]"
        onClick={onClose}
      />
      <aside className="absolute right-0 top-0 h-full w-[340px] border-l border-slate-200 bg-white p-5 shadow-2xl">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Appearance</div>
            <h2 className="text-lg font-semibold text-slate-900">Chat Settings</h2>
          </div>
          <button
            type="button"
            aria-label="Close drawer"
            onClick={onClose}
            className="rounded-lg border border-slate-200 bg-white p-2 text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
          >
            <CgClose className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4">
          <label className="block">
            <div className="mb-1 text-sm font-medium text-slate-700">Accent color</div>
            <div className="mb-2 flex flex-wrap gap-2">
              {["#0689D8", "#0EA5A0", "#4F46E5", "#E11D48", "#D97706"].map((color) => (
                <button
                  key={color}
                  type="button"
                  aria-label={`Use ${color} accent color`}
                  onClick={() => onAccentColorChange(color)}
                  className={[
                    "h-7 w-7 rounded-full border-2 transition-transform hover:scale-105",
                    accentColor.toLowerCase() === color.toLowerCase() ? "border-slate-900" : "border-white",
                  ].join(" ")}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
            <input
              type="color"
              value={accentColor}
              onChange={(e) => onAccentColorChange(e.target.value)}
              className="h-10 w-full cursor-pointer rounded-lg border border-slate-300 bg-white px-2 py-1"
            />
          </label>

          <label className="block">
            <div className="mb-1 text-sm font-medium text-slate-700">Color scheme</div>
            <select
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-[#0689D8] focus:outline-none"
              value={colorScheme}
              onChange={(e) => onColorSchemeChange(e.target.value as "light" | "dark")}
            >
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </label>

          <label className="block">
            <div className="mb-1 text-sm font-medium text-slate-700">Radius</div>
            <select
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-[#0689D8] focus:outline-none"
              value={radius}
              onChange={(e) => onRadiusChange(e.target.value as "pill" | "round" | "soft" | "sharp")}
            >
              <option value="round">Round</option>
              <option value="soft">Soft</option>
              <option value="pill">Pill</option>
              <option value="sharp">Sharp</option>
            </select>
          </label>

          <label className="block">
            <div className="mb-1 text-sm font-medium text-slate-700">Density</div>
            <select
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-[#0689D8] focus:outline-none"
              value={density}
              onChange={(e) => onDensityChange(e.target.value as "compact" | "normal" | "spacious")}
            >
              <option value="compact">Compact</option>
              <option value="normal">Normal</option>
              <option value="spacious">Spacious</option>
            </select>
          </label>
        </div>
      </aside>
    </div>
  );
}

export default function App() {
  const [isMounted, setIsMounted] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [colorScheme, setColorScheme] = useState<"light" | "dark">("light");
  const [radius, setRadius] = useState<"pill" | "round" | "soft" | "sharp">("round");
  const [density, setDensity] = useState<"compact" | "normal" | "spacious">("normal");
  const [accentColor, setAccentColor] = useState("#0689D8");
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [referenceSources, setReferenceSources] = useState<ReferenceSource[]>([]);
  const [isLoadingReferences, setIsLoadingReferences] = useState(false);

  const fetchLatestReferences = useCallback(async () => {
    if (!activeThreadId) {
      setReferenceSources([]);
      return;
    }

    setIsLoadingReferences(true);
    try {
      const response = await fetch(CHATKIT_API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: "items.list",
          params: {
            thread_id: activeThreadId,
            limit: 50,
            order: "desc",
          },
        }),
      });

      const payload = await response.json();
      const items = Array.isArray(payload?.data) ? payload.data : [];
      const latestAssistant = items.find(
        (item: any) =>
          item?.type === "assistant_message" &&
          Array.isArray(item?.content) &&
          item.content.some((part: any) => Array.isArray(part?.annotations) && part.annotations.length > 0)
      );

      if (!latestAssistant) {
        setReferenceSources([]);
        return;
      }

      const rawSources = (latestAssistant.content ?? [])
        .flatMap((part: any) => part?.annotations ?? [])
        .map((annotation: any) => annotation?.source)
        .filter(Boolean);

      const unique = new Map<string, ReferenceSource>();
      for (const source of rawSources) {
        const kind = source?.type ?? "unknown";
        const title = source?.title ?? "Untitled reference";
        const subtitle =
          kind === "url"
            ? source?.url
            : kind === "file"
              ? source?.filename ?? source?.description
              : kind === "entity"
                ? source?.label ?? source?.id
                : source?.description;
        const key = `${kind}|${title}|${subtitle ?? ""}`;

        if (!unique.has(key)) {
          unique.set(key, { key, title, subtitle, kind });
        }
      }

      setReferenceSources(Array.from(unique.values()));
    } catch (error) {
      console.error("Failed to load references", error);
      setReferenceSources([]);
    } finally {
      setIsLoadingReferences(false);
    }
  }, [activeThreadId]);

  const chatkit = useChatKit({
    api: {
      url: CHATKIT_API_URL,
      domainKey: CHATKIT_API_DOMAIN_KEY,
    },
    initialThread: activeThreadId,
    theme: {
      color: {
        accent: {
          primary: accentColor,
          level: 1,
        },
      },
      colorScheme,
      radius,
      density,
    },
    onThreadChange: (e) => setActiveThreadId(e.threadId),
    onResponseEnd: () => {
      void fetchLatestReferences();
    },
    onReady: () => console.log("ChatKit ready"),
    onError: (e) => console.error("ChatKit error:", e.error),
    onLog: (e) => console.log("ChatKit log:", e.name, e.data),
    onEffect: (e) => console.log("ChatKit effect:", e.name, e.data),
    startScreen: {
      greeting: "Welcome to Samsung Support. How can I help you today?",
    //   prompts: [
    //   {
    //     icon: 'circle-question',
    //     label: 'What is Yext Search?',
    //     prompt: 'What is Yext Search?'
    //   },
    //   {
    //     icon: 'circle-question',
    //     label: 'Help me with a Search Frontend',
    //     prompt: 'How can I set up a new Search Frontend?'
    //   },
    //   {
    //     icon: 'circle-question',
    //     label: 'What are custom phrases?',
    //     prompt: 'What are custom phrases in Yext Search?'
    //   },
    // ],
    prompts: [
      {
        icon: 'circle-question',
        label: 'How can I contact support?',
        prompt: 'How can I contact support?'
      },
      {
        icon: 'circle-question',
        label: 'Good phones for gaming',
        prompt: 'What are good phones for gaming?'
      },
      {
        icon: 'circle-question',
        label: 'What is airplane mode?',
        prompt: 'What is airplane mode?'
      },
    ],
    },
    composer: {
      placeholder: "Type your message...",
    },
  });

  useEffect(() => {
    setIsMounted(true);
  }, [chatkit]);

  useEffect(() => {
    void fetchLatestReferences();
  }, [fetchLatestReferences]);

  if (!isMounted) {
    return (
      <div className="flex h-screen items-center justify-center font-sans">
        Loading ChatKit...
      </div>
    );
  }

  const pageClasses =
    colorScheme === "dark" ? "min-h-screen bg-slate-950 text-slate-100" : "min-h-screen bg-slate-50 text-slate-900";
  const headerClasses =
    colorScheme === "dark"
      ? "border-b border-slate-800 bg-slate-950/85 backdrop-blur"
      : "border-b border-slate-200 bg-white/80 backdrop-blur";
  const subtextClasses = colorScheme === "dark" ? "text-slate-400" : "text-slate-500";
  const panelClasses =
    colorScheme === "dark"
      ? "min-h-0 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-sm"
      : "min-h-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm";
  const initClasses =
    colorScheme === "dark"
      ? "flex min-h-0 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900 text-slate-300 shadow-sm"
      : "flex min-h-0 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-600 shadow-sm";

  return (
    <div className={pageClasses}>
      <header className={headerClasses}>
        <div className="mx-auto flex w-full max-w-[1400px] items-center justify-between px-4 py-3 md:px-6">
          <div>
            <div className={`text-sm font-semibold uppercase tracking-wide ${subtextClasses}`}>Support Assistant</div>
            <h1 className="text-lg font-semibold">Samsung Help Center</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className={`hidden text-sm md:block ${subtextClasses}`}>Ask a question or choose a suggested prompt.</div>
            <button
              type="button"
              onClick={() => setIsSettingsOpen(true)}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
            >
              <CgOptions className="h-4 w-4" />
              Settings
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto grid h-[calc(100vh-73px)] w-full max-w-[1400px] grid-cols-1 gap-4 p-4 md:grid-cols-[minmax(0,1fr)_360px] md:gap-6 md:p-6">
        {chatkit?.control ? (
          <div className={panelClasses}>
            <ChatKit control={chatkit.control} className="h-full w-full" />
          </div>
        ) : (
          <div className={initClasses}>
            Initializing ChatKit...
          </div>
        )}

        <div className="min-h-[260px] md:min-h-0">
          <ReferencesWidgetPanel
            colorScheme={colorScheme}
            accentColor={accentColor}
            activeThreadId={activeThreadId}
            isLoadingReferences={isLoadingReferences}
            referenceSources={referenceSources}
          />
        </div>
      </main>

      <SettingsDrawer
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        colorScheme={colorScheme}
        radius={radius}
        density={density}
        accentColor={accentColor}
        onColorSchemeChange={setColorScheme}
        onRadiusChange={setRadius}
        onDensityChange={setDensity}
        onAccentColorChange={setAccentColor}
      />
    </div>
  );
}
