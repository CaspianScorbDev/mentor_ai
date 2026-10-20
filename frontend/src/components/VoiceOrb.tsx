import { useEffect, useRef } from "react";

export type VoicePhase = "idle" | "listening" | "thinking" | "speaking";

interface VoiceOrbProps {
  phase: VoicePhase;
  levelRef: { current: number };
}

interface Particle {
  angle: number;
  radius: number;
  size: number;
  speed: number;
  seed: number;
}

const PALETTE: Record<VoicePhase, [number, number, number]> = {
  idle: [150, 142, 128],
  listening: [96, 176, 204],
  thinking: [150, 132, 214],
  speaking: [222, 168, 104],
};

const PARTICLE_COUNT = 220;

function buildParticles(): Particle[] {
  const particles: Particle[] = [];
  for (let i = 0; i < PARTICLE_COUNT; i += 1) {
    const radius = Math.sqrt(Math.random());
    particles.push({
      angle: Math.random() * Math.PI * 2,
      radius,
      size: 0.6 + Math.random() * 1.8,
      speed: 0.06 + Math.random() * 0.22,
      seed: Math.random() * Math.PI * 2,
    });
  }
  return particles;
}

export function VoiceOrb({ phase, levelRef }: VoiceOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const phaseRef = useRef<VoicePhase>(phase);

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const particles = buildParticles();
    let raf = 0;
    let t = 0;
    let smooth = 0;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const draw = () => {
      const rect = canvas.getBoundingClientRect();
      const w = rect.width;
      const h = rect.height;
      const cx = w / 2;
      const cy = h / 2;
      const base = Math.min(w, h) * 0.34;

      smooth += (levelRef.current - smooth) * 0.12;
      const current = phaseRef.current;
      const [r, g, b] = PALETTE[current];

      t += 0.016;
      ctx.clearRect(0, 0, w, h);

      // Soft core glow.
      const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, base * (1.6 + smooth * 0.6));
      glow.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.34)`);
      glow.addColorStop(0.55, `rgba(${r}, ${g}, ${b}, 0.10)`);
      glow.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(cx, cy, base * (1.7 + smooth * 0.6), 0, Math.PI * 2);
      ctx.fill();

      ctx.globalCompositeOperation = "lighter";

      const swirl = current === "thinking" ? 1.7 : current === "speaking" ? 1.2 : 0.7;
      const breathe = 1 + Math.sin(t * (current === "idle" ? 0.9 : 2.1)) * 0.05;

      for (const p of particles) {
        const spin = p.speed * swirl * 0.5;
        const angle = p.angle + t * spin + Math.sin(t * 0.6 + p.seed) * 0.35;
        const wave = Math.sin(t * 1.6 + p.seed * 3 + p.radius * 6.2) * 0.08;
        const push = 1 + smooth * (0.55 + p.radius * 0.7) + wave;
        const rad = base * p.radius * breathe * push;
        const x = cx + Math.cos(angle) * rad;
        const y = cy + Math.sin(angle) * rad;
        const alpha = 0.25 + p.radius * 0.5 + smooth * 0.35;
        const size = p.size * (1 + smooth * 0.9);

        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${Math.min(1, alpha)})`;
        ctx.beginPath();
        ctx.arc(x, y, size, 0, Math.PI * 2);
        ctx.fill();

        if (p.radius > 0.7) {
          ctx.fillStyle = `rgba(255, 255, 255, ${Math.min(0.5, alpha * 0.5)})`;
          ctx.beginPath();
          ctx.arc(x, y, size * 0.5, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      ctx.globalCompositeOperation = "source-over";
      raf = requestAnimationFrame(draw);
    };

    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, [levelRef]);

  return <canvas ref={canvasRef} className="voice-orb-canvas" />;
}
