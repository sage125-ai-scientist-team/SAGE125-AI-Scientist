export default function Sage125Scroll(args) {
  const data = args.data || {};
  const target = data.scrollTarget;
  const nonce = data.nonce;
  const setTrigger = args.setTriggerValue;
  if (target && nonce && typeof window !== "undefined") {
    const parentWin = window.parent || window;
    const key = `${String(nonce)}:${String(target)}`;
    if (parentWin.__sage125ScrollNonce !== key) {
      parentWin.__sage125ScrollNonce = key;
      const el = parentWin.document.getElementById(target);
      if (el) {
        const reduce = parentWin.matchMedia("(prefers-reduced-motion: reduce)").matches;
        parentWin.requestAnimationFrame(() => {
          el.scrollIntoView({
            behavior: reduce ? "auto" : "smooth",
            block: "start",
            inline: "nearest",
          });
        });
      }
    }
  }
  if (typeof setTrigger === "function") {
    setTrigger("acknowledged", `${nonce || ""}:${target || ""}`);
  }
  return () => {};
}
