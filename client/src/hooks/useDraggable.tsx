import { useRef, useState, type PointerEvent, type ReactNode, type CSSProperties } from "react";

type Offset = { x: number; y: number };

const INTERACTIVE = "button, input, textarea, select, a, label, [contenteditable], [data-no-drag]";
const DRAG_THRESHOLD = 4; // px of movement before a press becomes a drag

function useDraggable(initial: Offset = { x: 0, y: 0 }) {
  const [offset, setOffset] = useState<Offset>(initial);
  const [dragging, setDragging] = useState(false);
  const start = useRef<{ px: number; py: number; ox: number; oy: number } | null>(null);
  const active = useRef(false);

  const onPointerDown = (e: PointerEvent<HTMLElement>) => {
    if (e.button !== 0) return;
    if ((e.target as HTMLElement).closest(INTERACTIVE)) return; // let children handle it
    start.current = { px: e.clientX, py: e.clientY, ox: offset.x, oy: offset.y };
    active.current = false;
    // note: no pointer capture yet, so clicks still reach children
  };

  const onPointerMove = (e: PointerEvent<HTMLElement>) => {
    const s = start.current;
    if (!s) return;
    const dx = e.clientX - s.px;
    const dy = e.clientY - s.py;

    if (!active.current) {
      if (Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
      active.current = true;
      e.currentTarget.setPointerCapture(e.pointerId); // capture only once it's really a drag
      setDragging(true);
    }
    setOffset({ x: s.ox + dx, y: s.oy + dy });
  };

  const end = (e: PointerEvent<HTMLElement>) => {
    if (active.current && e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
    start.current = null;
    active.current = false;
    setDragging(false);
  };

  const style: CSSProperties = {
    transform: `translate(${offset.x}px, ${offset.y}px)`,
    cursor: dragging ? "grabbing" : "grab",
    userSelect: dragging ? "none" : undefined, // only while dragging
    position: "relative",
    zIndex: dragging ? 10 : undefined,
  };

  return {
    handlers: { onPointerDown, onPointerMove, onPointerUp: end, onPointerCancel: end },
    style,
  };
}

export function Draggable({ children }: { children: ReactNode }) {
  const { handlers, style } = useDraggable();
  return <div {...handlers} style={style}>{children}</div>;
}