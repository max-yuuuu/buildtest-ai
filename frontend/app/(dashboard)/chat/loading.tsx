export default function ChatLoading() {
  return (
    <div className="flex h-full min-h-[calc(100vh-80px)] flex-col gap-4 p-4 lg:p-5">
      <div className="flex flex-col gap-2">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div className="space-y-2">
            <div className="h-7 w-40 animate-pulse rounded-md bg-muted" />
            <div className="h-3 w-full max-w-md animate-pulse rounded bg-muted/80" />
          </div>
          <div className="h-9 w-56 shrink-0 animate-pulse rounded-md bg-muted" />
        </div>
        <div className="h-4 w-48 animate-pulse rounded bg-muted/70" />
      </div>

      <div className="flex flex-1 flex-col rounded-xl border bg-background/80 p-4 shadow-sm">
        <div className="flex flex-1 flex-col items-center justify-center gap-3">
          <div className="h-3 w-52 animate-pulse rounded bg-muted/60" />
          <div className="h-3 w-40 animate-pulse rounded bg-muted/50" />
        </div>
      </div>

      <div className="sticky bottom-0 space-y-2 rounded-3xl border bg-background/95 px-3 py-3 shadow-sm backdrop-blur">
        <div className="flex gap-2">
          <div className="h-9 flex-1 animate-pulse rounded-lg bg-muted" />
          <div className="h-9 w-16 shrink-0 animate-pulse rounded-md bg-muted" />
        </div>
      </div>
    </div>
  );
}
