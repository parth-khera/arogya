'use client';

'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence, useMotionValue, useSpring } from 'motion/react';

const SAMPLE_PROMPTS = [
  { text: 'I have a fever and headache since morning...', icon: '🤒' },
  { text: 'What is Ayushman Bharat scheme?', icon: '🏛️' },
  { text: 'My child has had fever for 3 days...', icon: '👶' },
  { text: 'Where can I find a government hospital?', icon: '🏥' },
  { text: 'I have diabetes. What foods to avoid?', icon: '🍎' },
  { text: 'How do I get a health card made?', icon: '💳' },
];

const STATS = [
  { value: '55ms', label: 'TTS Latency' },
  { value: '150+', label: 'Indian Voices' },
  { value: '10+', label: 'Languages' },
  { value: '99%', label: 'Accuracy' },
];

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
}

function Particle({ x, y, size, duration, delay }: { x: number; y: number; size: number; duration: number; delay: number }) {
  return (
    <motion.div
      className="absolute rounded-full pointer-events-none"
      style={{
        left: `${x}%`,
        top: `${y}%`,
        width: size,
        height: size,
        background: 'radial-gradient(circle, rgba(255,153,51,0.6) 0%, rgba(19,136,8,0.3) 100%)',
      }}
      animate={{
        y: [0, -30, 0],
        opacity: [0, 0.8, 0],
        scale: [0, 1, 0],
      }}
      transition={{
        duration,
        delay,
        repeat: Infinity,
        ease: 'easeInOut',
      }}
    />
  );
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  const [promptIndex, setPromptIndex] = useState(0);
  const [isPressed, setIsPressed] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const springX = useSpring(mouseX, { stiffness: 50, damping: 20 });
  const springY = useSpring(mouseY, { stiffness: 50, damping: 20 });

  useEffect(() => {
    const interval = setInterval(() => {
      setPromptIndex((i) => (i + 1) % SAMPLE_PROMPTS.length);
    }, 2800);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width - 0.5) * 20;
      const y = ((e.clientY - rect.top) / rect.height - 0.5) * 20;
      mouseX.set(x);
      mouseY.set(y);
      setMousePos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [mouseX, mouseY]);

  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const particles = useMemo(() => Array.from({ length: 12 }, () => ({
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: Math.random() * 6 + 3,
    duration: Math.random() * 3 + 2,
    delay: Math.random() * 4,
  })), []);

  return (
    <div ref={ref} className="relative w-full min-h-screen overflow-hidden flex items-center justify-center">

      {/* Deep gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-orange-50 via-white to-green-50 dark:from-gray-950 dark:via-gray-900 dark:to-gray-950" />

      {/* Mesh gradient orbs */}
      <motion.div
        className="absolute top-0 left-0 w-[700px] h-[700px] rounded-full blur-3xl opacity-30 dark:opacity-15 pointer-events-none"
        style={{ background: 'radial-gradient(circle, #FF9933 0%, transparent 70%)', x: springX, y: springY }}
      />
      <motion.div
        className="absolute bottom-0 right-0 w-[600px] h-[600px] rounded-full blur-3xl opacity-25 dark:opacity-10 pointer-events-none"
        style={{ background: 'radial-gradient(circle, #138808 0%, transparent 70%)' }}
        animate={{ scale: [1, 1.15, 1] }}
        transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="absolute top-1/3 right-1/4 w-[400px] h-[400px] rounded-full blur-3xl opacity-20 dark:opacity-10 pointer-events-none"
        style={{ background: 'radial-gradient(circle, #0ea5e9 0%, transparent 70%)' }}
        animate={{ scale: [1, 1.2, 1], x: [0, 30, 0] }}
        transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Floating particles — client only to avoid hydration mismatch */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden" ref={containerRef}>
        {mounted && particles.map((p, i) => <Particle key={i} {...p} />)}
      </div>

      {/* Grid pattern overlay */}
      <div
        className="absolute inset-0 opacity-[0.03] dark:opacity-[0.05] pointer-events-none"
        style={{
          backgroundImage: 'linear-gradient(#000 1px, transparent 1px), linear-gradient(90deg, #000 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      {/* Main content */}
      <div className="relative z-10 w-full max-w-5xl mx-auto px-4 py-12 flex flex-col lg:flex-row items-center gap-12">

        {/* Left column */}
        <div className="flex-1 text-center lg:text-left">

          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold mb-6 border"
            style={{
              background: 'linear-gradient(135deg, rgba(255,153,51,0.15) 0%, rgba(19,136,8,0.15) 100%)',
              borderColor: 'rgba(255,153,51,0.3)',
              color: '#c47a00',
            }}
          >
            <motion.span
              animate={{ scale: [1, 1.3, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            >🇮🇳</motion.span>
            #VoiceForBharat · Health Access Track
          </motion.div>

          {/* Title */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <h1 className="text-6xl lg:text-7xl font-black tracking-tight text-foreground leading-none mb-2">
              Aarogya
            </h1>
            <p className="text-xl text-muted-foreground font-light mb-1">आरोग्य</p>
            <p className="text-lg text-muted-foreground mb-6">
              Voice AI Health Assistant for <span className="font-semibold text-foreground">India</span>
            </p>
          </motion.div>

          {/* Description */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-muted-foreground text-sm leading-relaxed mb-8 max-w-md mx-auto lg:mx-0"
          >
            Speak naturally in your language. Get instant health guidance, find nearby clinics,
            and understand government schemes — all through voice.
          </motion.p>

          {/* Stats row */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="flex gap-6 justify-center lg:justify-start mb-10"
          >
            {STATS.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.4 + i * 0.08 }}
                className="text-center"
              >
                <div className="text-xl font-black text-foreground">{s.value}</div>
                <div className="text-xs text-muted-foreground">{s.label}</div>
              </motion.div>
            ))}
          </motion.div>

          {/* CTA Button */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            <motion.button
              onTapStart={() => setIsPressed(true)}
              onTap={() => setIsPressed(false)}
              onTapCancel={() => setIsPressed(false)}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={onStartCall}
              className="relative group inline-flex items-center gap-3 px-8 py-4 rounded-2xl text-white font-bold text-base shadow-2xl overflow-hidden cursor-pointer"
              style={{ background: 'linear-gradient(135deg, #FF9933 0%, #e67e00 40%, #138808 100%)' }}
            >
              {/* Glow */}
              <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                style={{ background: 'linear-gradient(135deg, #ffb347 0%, #ff9933 40%, #1aaa0a 100%)' }} />

              {/* Pulse ring */}
              <motion.div
                className="absolute inset-0 rounded-2xl"
                animate={{ boxShadow: isPressed ? '0 0 0 0px rgba(255,153,51,0.4)' : ['0 0 0 0px rgba(255,153,51,0.4)', '0 0 0 12px rgba(255,153,51,0)'] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />

              <motion.span
                className="relative text-xl"
                animate={{ rotate: isPressed ? [0, -15, 15, 0] : 0 }}
                transition={{ duration: 0.4 }}
              >
                🎙️
              </motion.span>
              <span className="relative tracking-wide">{startButtonText}</span>
              <motion.span
                className="relative"
                animate={{ x: [0, 4, 0] }}
                transition={{ duration: 1.2, repeat: Infinity }}
              >
                →
              </motion.span>
            </motion.button>

            <p className="text-xs text-muted-foreground mt-3">
              No app needed · Just speak · Powered by{' '}
              <a href="https://murf.ai/api" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-foreground transition-colors">
                Murf Falcon
              </a>
            </p>
          </motion.div>
        </div>

        {/* Right column — interactive card */}
        <motion.div
          initial={{ opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3, duration: 0.6 }}
          className="flex-1 w-full max-w-sm"
          style={{ rotateX: springY, rotateY: springX, transformPerspective: 1000 }}
        >
          {/* Glass card */}
          <div className="relative rounded-3xl overflow-hidden border border-white/40 dark:border-white/10 shadow-2xl"
            style={{ background: 'rgba(255,255,255,0.7)', backdropFilter: 'blur(20px)' }}
          >
            <div className="dark:hidden absolute inset-0 rounded-3xl"
              style={{ background: 'rgba(255,255,255,0.7)', backdropFilter: 'blur(20px)' }} />
            <div className="hidden dark:block absolute inset-0 rounded-3xl"
              style={{ background: 'rgba(15,15,15,0.7)', backdropFilter: 'blur(20px)' }} />

            <div className="relative z-10 p-6">
              {/* Card header */}
              <div className="flex items-center gap-3 mb-5">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xl shadow-md"
                  style={{ background: 'linear-gradient(135deg, #FF9933, #138808)' }}>
                  🏥
                </div>
                <div>
                  <p className="font-bold text-foreground text-sm">Aarogya Assistant</p>
                  <div className="flex items-center gap-1.5">
                    <motion.div
                      className="w-2 h-2 rounded-full bg-green-500"
                      animate={{ opacity: [1, 0.3, 1] }}
                      transition={{ duration: 1.5, repeat: Infinity }}
                    />
                    <p className="text-xs text-muted-foreground">Ready to help</p>
                  </div>
                </div>
              </div>

              {/* Animated prompt */}
              <div className="rounded-2xl p-4 mb-4 border border-border/50"
                style={{ background: 'rgba(255,153,51,0.06)' }}>
                <p className="text-xs text-muted-foreground mb-2 font-mono uppercase tracking-wider">Try asking...</p>
                <div className="h-10 flex items-center overflow-hidden">
                  <AnimatePresence mode="wait">
                    <motion.div
                      key={promptIndex}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ duration: 0.35 }}
                      className="flex items-center gap-2"
                    >
                      <span className="text-lg">{SAMPLE_PROMPTS[promptIndex].icon}</span>
                      <p className="text-sm font-medium text-foreground leading-snug">
                        &ldquo;{SAMPLE_PROMPTS[promptIndex].text}&rdquo;
                      </p>
                    </motion.div>
                  </AnimatePresence>
                </div>
                {/* Progress dots */}
                <div className="flex gap-1 mt-3">
                  {SAMPLE_PROMPTS.map((_, i) => (
                    <motion.div
                      key={i}
                      className="h-1 rounded-full"
                      animate={{
                        width: i === promptIndex ? 20 : 6,
                        background: i === promptIndex ? '#FF9933' : '#e5e7eb',
                      }}
                      transition={{ duration: 0.3 }}
                    />
                  ))}
                </div>
              </div>

              {/* Feature list */}
              {[
                { icon: '🎙️', text: 'Voice-first, no typing needed' },
                { icon: '🧠', text: 'Gender-adaptive Indian voice' },
                { icon: '🏛️', text: 'Ayushman Bharat guidance' },
                { icon: '⚡', text: '55ms Murf Falcon response' },
              ].map((f, i) => (
                <motion.div
                  key={f.text}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.6 + i * 0.1 }}
                  className="flex items-center gap-3 py-2 border-b border-border/30 last:border-0"
                >
                  <span className="text-base">{f.icon}</span>
                  <span className="text-xs text-muted-foreground">{f.text}</span>
                  <motion.div
                    className="ml-auto w-4 h-4 rounded-full flex items-center justify-center text-white text-xs"
                    style={{ background: '#138808' }}
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: 0.8 + i * 0.1, type: 'spring' }}
                  >
                    ✓
                  </motion.div>
                </motion.div>
              ))}

              {/* Tech stack pills */}
              <div className="flex flex-wrap gap-1.5 mt-4">
                {['Murf Falcon', 'Deepgram', 'Groq LLaMA', 'LiveKit'].map((t) => (
                  <span key={t} className="px-2 py-0.5 rounded-full text-xs border border-border/50 text-muted-foreground bg-background/50">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
};
