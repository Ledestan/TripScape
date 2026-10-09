export default function LoadingScreen({ text = "加载中…" }: { text?: string }) {
  return (
    <div className="fixed inset-0 z-[9999] flex flex-col items-center justify-center overflow-hidden bg-[#04070f] text-white">
      {/* 星空（Google Earth 官方素材，右上覆盖） */}
      <div
        className="absolute inset-0 opacity-70"
        style={{
          backgroundImage: "url(/stars.jpg)",
          backgroundSize: "cover",
          backgroundPosition: "top right",
        }}
      />
      {/* 底部地球弧光 */}
      <div
        className="absolute inset-x-0 bottom-0 h-[46%]"
        style={{
          backgroundImage: "url(/earth-arc.jpg)",
          backgroundSize: "1280px auto",
          backgroundPosition: "bottom center",
          backgroundRepeat: "no-repeat",
          maskImage: "linear-gradient(to top, black 55%, transparent 100%)",
          WebkitMaskImage: "linear-gradient(to top, black 55%, transparent 100%)",
        }}
      />
      {/* 中央地球（细光环呼吸） */}
      <div className="relative flex flex-col items-center gap-6">
        <div
          className="h-20 w-20 rounded-full animate-[breathe_2.8s_ease-in-out_infinite]"
          style={{
            background: "radial-gradient(circle at 32% 30%, #9fd0ff 0%, #3f7cc2 52%, #16345e 100%)",
            boxShadow: "0 0 60px rgba(90,150,230,0.35), inset -8px -10px 24px rgba(0,0,0,0.45)",
          }}
        />
        <div className="text-[13px] font-light tracking-[0.45em] text-white/80">{text}</div>
      </div>
      <style>{`
        @keyframes breathe {
          0%, 100% { transform: scale(1); box-shadow: 0 0 60px rgba(90,150,230,0.35), inset -8px -10px 24px rgba(0,0,0,0.45); }
          50% { transform: scale(1.05); box-shadow: 0 0 90px rgba(90,150,230,0.5), inset -8px -10px 24px rgba(0,0,0,0.45); }
        }
      `}</style>
    </div>
  );
}
