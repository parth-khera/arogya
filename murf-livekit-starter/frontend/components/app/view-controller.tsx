'use client';

import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';
import { AnimatePresence, motion } from 'motion/react';
import { useSessionContext } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { AgentSessionView_01 } from '@/components/agents-ui/blocks/agent-session-view-01';
import { WelcomeView } from '@/components/app/welcome-view';

type AppState = 'ready' | 'connecting' | 'connected' | 'ended' | 'mic-error';

const MotionWelcomeView = motion.create(WelcomeView);
const MotionSessionView = motion.create(AgentSessionView_01);

const FADE = {
  variants: { visible: { opacity: 1 }, hidden: { opacity: 0 } },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: { duration: 0.45, ease: 'easeInOut' },
};

// ── Connecting screen ─────────────────────────────────────────────────────────
function ConnectingView() {
  const steps = ['Connecting to Aarogya...', 'Setting up your voice...', 'Almost ready...'];
  const [step, setStep] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, steps.length - 1)), 1400);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="fixed inset-0 flex flex-col items-center justify-center bg-gradient-to-br from-orange-50 via-white to-green-50 dark:from-gray-950 dark:via-gray-900 dark:to-gray-950">
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="flex flex-col items-center gap-6"
      >
        {/* Pulsing logo */}
        <div className="relative">
          <motion.div
            className="absolute inset-0 rounded-full"
            style={{ background: 'radial-gradient(circle, rgba(255,153,51,0.4) 0%, transparent 70%)' }}
            animate={{ scale: [1, 1.6, 1], opacity: [0.6, 0, 0.6] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
          <div className="relative w-20 h-20 rounded-2xl flex items-center justify-center text-4xl shadow-xl"
            style={{ background: 'linear-gradient(135deg, #FF9933, #138808)' }}>
            🏥
          </div>
        </div>

        {/* Spinner dots */}
        <div className="flex gap-2">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className="w-2.5 h-2.5 rounded-full"
              style={{ background: i === 0 ? '#FF9933' : i === 1 ? '#c47a00' : '#138808' }}
              animate={{ y: [0, -10, 0], opacity: [0.4, 1, 0.4] }}
              transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.2 }}
            />
          ))}
        </div>

        <AnimatePresence mode="wait">
          <motion.p
            key={step}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="text-sm font-medium text-muted-foreground"
          >
            {steps[step]}
          </motion.p>
        </AnimatePresence>

        <p className="text-xs text-muted-foreground/60">Powered by Murf Falcon · 55ms latency</p>
      </motion.div>
    </div>
  );
}

// ── Mic error screen ──────────────────────────────────────────────────────────
function MicErrorView({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="fixed inset-0 flex flex-col items-center justify-center px-6 bg-gradient-to-br from-red-50 via-white to-orange-50 dark:from-gray-950 dark:via-gray-900 dark:to-gray-950">
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="w-full max-w-sm text-center"
      >
        <div className="w-16 h-16 rounded-2xl bg-red-100 dark:bg-red-900/30 flex items-center justify-center text-3xl mx-auto mb-4">
          🎙️
        </div>
        <h2 className="text-xl font-bold text-foreground mb-2">Microphone Access Needed</h2>
        <p className="text-sm text-muted-foreground mb-6 leading-relaxed">
          Aarogya needs your microphone to hear you. Your browser has blocked access.
        </p>

        <div className="bg-card border border-border rounded-2xl p-4 text-left mb-6 space-y-3">
          <p className="text-xs font-semibold text-foreground uppercase tracking-wider">How to fix this:</p>
          {[
            { icon: '🔒', text: 'Click the lock icon in your browser address bar' },
            { icon: '🎙️', text: 'Set Microphone to "Allow"' },
            { icon: '🔄', text: 'Refresh the page and try again' },
          ].map((s) => (
            <div key={s.text} className="flex items-start gap-3">
              <span className="text-base mt-0.5">{s.icon}</span>
              <p className="text-xs text-muted-foreground">{s.text}</p>
            </div>
          ))}
        </div>

        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={onRetry}
          className="w-full py-3 rounded-xl text-white font-bold text-sm cursor-pointer"
          style={{ background: 'linear-gradient(135deg, #FF9933, #138808)' }}
        >
          Try Again
        </motion.button>
      </motion.div>
    </div>
  );
}

// ── Call ended screen ─────────────────────────────────────────────────────────
function CallEndedView({ onRestart }: { onRestart: () => void }) {
  const tips = [
    'For emergencies, always call 112',
    'Ayushman Bharat helpline: 14555',
    'Find your nearest PHC at nhp.gov.in',
    'Jan Aushadhi stores offer medicines at low cost',
  ];
  const [tip] = useState(() => tips[Math.floor(Math.random() * tips.length)]);

  return (
    <div className="fixed inset-0 flex flex-col items-center justify-center px-6 bg-gradient-to-br from-green-50 via-white to-orange-50 dark:from-gray-950 dark:via-gray-900 dark:to-gray-950">
      <motion.div
        initial={{ scale: 0.9, opacity: 0, y: 20 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 200 }}
        className="w-full max-w-sm text-center"
      >
        {/* Checkmark */}
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.2, type: 'spring', stiffness: 300 }}
          className="w-16 h-16 rounded-full flex items-center justify-center text-3xl mx-auto mb-4"
          style={{ background: 'linear-gradient(135deg, #138808, #0d6b06)' }}
        >
          ✓
        </motion.div>

        <h2 className="text-2xl font-bold text-foreground mb-1">Call Ended</h2>
        <p className="text-sm text-muted-foreground mb-6">
          Thank you for using Aarogya. Stay healthy!
        </p>

        {/* Health tip */}
        <div className="bg-card border border-border rounded-2xl p-4 mb-6 text-left"
          style={{ borderLeft: '3px solid #FF9933' }}>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Health Tip</p>
          <p className="text-sm text-foreground">{tip}</p>
        </div>

        {/* Emergency numbers */}
        <div className="grid grid-cols-2 gap-3 mb-6">
          {[
            { label: 'Emergency', number: '112', color: '#dc2626' },
            { label: 'Health Helpline', number: '104', color: '#138808' },
          ].map((e) => (
            <a key={e.number} href={`tel:${e.number}`}
              className="flex flex-col items-center p-3 rounded-xl border border-border bg-card hover:bg-accent transition-colors">
              <span className="text-lg font-black" style={{ color: e.color }}>{e.number}</span>
              <span className="text-xs text-muted-foreground">{e.label}</span>
            </a>
          ))}
        </div>

        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={onRestart}
          className="w-full py-3 rounded-xl text-white font-bold text-sm cursor-pointer"
          style={{ background: 'linear-gradient(135deg, #FF9933, #138808)' }}
        >
          🎙️ Start New Conversation
        </motion.button>
      </motion.div>
    </div>
  );
}

// ── Main controller ───────────────────────────────────────────────────────────
interface ViewControllerProps {
  appConfig: AppConfig;
}

export function ViewController({ appConfig }: ViewControllerProps) {
  const { isConnected, start, end } = useSessionContext();
  const { resolvedTheme } = useTheme();
  const [appState, setAppState] = useState<AppState>('ready');

  // Sync connected state
  useEffect(() => {
    if (isConnected && appState === 'connecting') {
      setAppState('connected');
    }
  }, [isConnected, appState]);

  const handleStart = async () => {
    // Check mic permission first
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setAppState('mic-error');
      return;
    }
    setAppState('connecting');
    start();
  };

  const handleEnd = () => {
    end();
    setAppState('ended');
  };

  const handleRestart = () => {
    setAppState('ready');
  };

  return (
    <AnimatePresence mode="wait">
      {/* READY */}
      {appState === 'ready' && (
        <MotionWelcomeView
          key="welcome"
          {...FADE}
          startButtonText={appConfig.startButtonText}
          onStartCall={handleStart}
        />
      )}

      {/* CONNECTING */}
      {appState === 'connecting' && (
        <motion.div key="connecting" {...FADE}>
          <ConnectingView />
        </motion.div>
      )}

      {/* CONNECTED / LISTENING / SPEAKING */}
      {appState === 'connected' && (
        <MotionSessionView
          key="session"
          {...FADE}
          supportsChatInput={appConfig.supportsChatInput}
          supportsVideoInput={appConfig.supportsVideoInput}
          supportsScreenShare={appConfig.supportsScreenShare}
          isPreConnectBufferEnabled={appConfig.isPreConnectBufferEnabled}
          audioVisualizerType={appConfig.audioVisualizerType}
          audioVisualizerColor={
            resolvedTheme === 'dark'
              ? appConfig.audioVisualizerColorDark
              : appConfig.audioVisualizerColor
          }
          audioVisualizerColorShift={appConfig.audioVisualizerColorShift}
          audioVisualizerBarCount={appConfig.audioVisualizerBarCount}
          audioVisualizerGridRowCount={appConfig.audioVisualizerGridRowCount}
          audioVisualizerGridColumnCount={appConfig.audioVisualizerGridColumnCount}
          audioVisualizerRadialBarCount={appConfig.audioVisualizerRadialBarCount}
          audioVisualizerRadialRadius={appConfig.audioVisualizerRadialRadius}
          audioVisualizerWaveLineWidth={appConfig.audioVisualizerWaveLineWidth}
          onCallEnd={handleEnd}
          className="fixed inset-0"
        />
      )}

      {/* MIC ERROR */}
      {appState === 'mic-error' && (
        <motion.div key="mic-error" {...FADE}>
          <MicErrorView onRetry={() => setAppState('ready')} />
        </motion.div>
      )}

      {/* CALL ENDED */}
      {appState === 'ended' && (
        <motion.div key="ended" {...FADE}>
          <CallEndedView onRestart={handleRestart} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
