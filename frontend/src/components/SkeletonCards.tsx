/**
 * 推荐生成期间的骨架屏占位（N7.5）
 */
export function SkeletonCards({ count = 2 }: { count?: number }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="rounded-xl2 border border-line bg-white p-4 shadow-card">
          <div className="flex gap-3">
            <div className="shimmer h-24 w-24 shrink-0 rounded-lg" />
            <div className="flex-1 space-y-2.5 py-1">
              <div className="shimmer h-3.5 w-3/4 rounded" />
              <div className="shimmer h-3 w-1/3 rounded" />
              <div className="shimmer h-3 w-2/3 rounded" />
              <div className="shimmer h-3 w-1/2 rounded" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
