import React, { type ReactNode } from 'react';
import { useCurrentFrame, useVideoConfig, spring, interpolate, AbsoluteFill } from 'remotion';

// ==================== Types ====================

export type EnterStyle =
  | 'fade'
  | 'slideUp'
  | 'slideDown'
  | 'slideLeft'
  | 'slideRight'
  | 'zoomIn'
  | 'floatUp'
  | 'floatDown'
  | 'pop'
  | 'none';

export type ExitStyle =
  | 'fade'
  | 'slideUp'
  | 'slideDown'
  | 'slideLeft'
  | 'slideRight'
  | 'zoomOut'
  | 'floatUp'
  | 'floatDown'
  | 'shrink'
  | 'none';

export type PageTransition =
  | 'pageFlipRight'
  | 'pageFlipLeft'
  | 'wipeRight'
  | 'wipeLeft'
  | 'wipeUp'
  | 'wipeDown'
  | 'glitch'
  | 'zoomCross'
  | 'none';

// ==================== Hook: useEnterAnimation ====================

export function useEnterAnimation(
  style: EnterStyle,
  startFrame: number,
  duration = 20,
) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame: frame - startFrame,
    fps,
    config: { damping: 14, stiffness: 80, mass: 0.6 },
  });
  const clamped = interpolate(progress, [0, 1], [0, 1], {
    extrapolateRight: 'clamp',
    extrapolateLeft: 'clamp',
  });

  const opacity = interpolate(
    frame,
    [startFrame, startFrame + duration * 0.5],
    [0, 1],
    { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' },
  );

  switch (style) {
    case 'fade':
      return { transform: 'none', opacity };
    case 'slideUp':
      return {
        transform: `translateY(${interpolate(clamped, [0, 1], [200, 0])}px)`,
        opacity,
      };
    case 'slideDown':
      return {
        transform: `translateY(${interpolate(clamped, [0, 1], [-200, 0])}px)`,
        opacity,
      };
    case 'slideLeft':
      return {
        transform: `translateX(${interpolate(clamped, [0, 1], [400, 0])}px)`,
        opacity,
      };
    case 'slideRight':
      return {
        transform: `translateX(${interpolate(clamped, [0, 1], [-400, 0])}px)`,
        opacity,
      };
    case 'zoomIn':
      return {
        transform: `scale(${interpolate(clamped, [0, 1], [0.7, 1])})`,
        opacity,
      };
    case 'floatUp': {
      const y = interpolate(clamped, [0, 1], [150, 0]);
      const s = interpolate(clamped, [0, 1], [0.95, 1]);
      return { transform: `translateY(${y}px) scale(${s})`, opacity };
    }
    case 'floatDown': {
      const y = interpolate(clamped, [0, 1], [-100, 0]);
      const s = interpolate(clamped, [0, 1], [0.95, 1]);
      return { transform: `translateY(${y}px) scale(${s})`, opacity };
    }
    case 'pop':
      return {
        transform: `scale(${spring({ frame: frame - startFrame, fps, config: { damping: 8, mass: 0.5 } })})`,
        opacity,
      };
    default:
      return { transform: 'none', opacity: 1 };
  }
}

// ==================== Hook: useExitAnimation ====================

export function useExitAnimation(
  style: ExitStyle,
  exitFrame: number,
  duration = 20,
) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame: frame - exitFrame,
    fps,
    config: { damping: 20, stiffness: 60, mass: 0.7 },
  });
  const clamped = Math.min(1, Math.max(0, progress));

  const opacity = interpolate(
    frame,
    [exitFrame, exitFrame + duration * 0.6],
    [1, 0],
    { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' },
  );

  switch (style) {
    case 'fade':
      return { transform: 'none', opacity };
    case 'slideUp':
      return {
        transform: `translateY(${interpolate(clamped, [0, 1], [0, -200])}px)`,
        opacity,
      };
    case 'slideDown':
      return {
        transform: `translateY(${interpolate(clamped, [0, 1], [0, 200])}px)`,
        opacity,
      };
    case 'slideLeft':
      return {
        transform: `translateX(${interpolate(clamped, [0, 1], [0, -400])}px)`,
        opacity,
      };
    case 'slideRight':
      return {
        transform: `translateX(${interpolate(clamped, [0, 1], [0, 400])}px)`,
        opacity,
      };
    case 'zoomOut':
      return {
        transform: `scale(${interpolate(clamped, [0, 1], [1, 1.3])})`,
        opacity,
      };
    case 'floatUp': {
      const y = interpolate(clamped, [0, 1], [0, -120]);
      const s = interpolate(clamped, [0, 1], [1, 0.9]);
      return { transform: `translateY(${y}px) scale(${s})`, opacity };
    }
    case 'floatDown': {
      const y = interpolate(clamped, [0, 1], [0, 120]);
      return { transform: `translateY(${y}px)`, opacity };
    }
    case 'shrink':
      return {
        transform: `scale(${interpolate(clamped, [0, 1], [1, 0.5])})`,
        opacity,
      };
    default:
      return { transform: 'none', opacity: 1 };
  }
}

// ==================== SceneWrapper ====================

interface SceneWrapperProps {
  children: ReactNode;
  isActive: boolean;
  enter?: EnterStyle;
  exit?: ExitStyle;
  enterStart?: number;
  exitStart?: number;
  className?: string;
}

export const SceneWrapper: React.FC<SceneWrapperProps> = ({
  children,
  isActive,
  enter = 'fade',
  exit = 'fade',
  enterStart = 0,
  exitStart = 0,
}) => {
  const frame = useCurrentFrame();
  const enterAnim = useEnterAnimation(enter, enterStart);
  const exitAnim = useExitAnimation(exit, exitStart);

  if (!isActive) return null;

  const style = frame < exitStart ? enterAnim : exitAnim;

  return (
    <div style={{ ...style, position: 'absolute', inset: 0 }}>
      {children}
    </div>
  );
};

// ==================== Page Flip Transition ====================

interface PageFlipProps {
  triggerFrame: number;
  direction?: 'right' | 'left';
}

export const PageFlipTransition: React.FC<PageFlipProps> = ({
  triggerFrame,
  direction = 'right',
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame: frame - triggerFrame,
    fps,
    config: { damping: 12, stiffness: 90, mass: 0.6 },
  });
  const clamped = Math.min(1, Math.max(0, progress));
  const visible = clamped > 0 && clamped < 0.99;

  if (!visible) return null;

  // Subtle gradient wipe only, no shadow flash
  const edgeOpacity = interpolate(clamped, [0, 0.5, 1], [0, 0.08, 0]);

  return (
    <AbsoluteFill style={{
      pointerEvents: 'none',
      zIndex: 100,
    }}>
      <div style={{
        position: 'absolute',
        inset: 0,
        background: direction === 'right'
          ? `linear-gradient(to right, transparent 0%, rgba(0,0,0,${edgeOpacity}) 50%, transparent 100%)`
          : `linear-gradient(to left, transparent 0%, rgba(0,0,0,${edgeOpacity}) 50%, transparent 100%)`,
      }} />
    </AbsoluteFill>
  );
};

// ==================== Wipe Transition ====================

interface WipeTransitionProps {
  triggerFrame: number;
  direction?: 'right' | 'left' | 'up' | 'down';
}

export const WipeTransition: React.FC<WipeTransitionProps> = ({
  triggerFrame,
  direction = 'right',
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame: frame - triggerFrame,
    fps,
    config: { damping: 15, stiffness: 100 },
  });
  const clamped = Math.min(1, Math.max(0, progress));

  if (clamped <= 0 || clamped >= 1) return null;

  let clipPath: string;
  switch (direction) {
    case 'right':
      clipPath = `inset(0 ${(1 - clamped) * 100}% 0 0)`;
      break;
    case 'left':
      clipPath = `inset(0 0 0 ${(1 - clamped) * 100}%)`;
      break;
    case 'up':
      clipPath = `inset(${(1 - clamped) * 100}% 0 0 0)`;
      break;
    case 'down':
      clipPath = `inset(0 0 ${(1 - clamped) * 100}% 0)`;
      break;
  }

  return (
    <AbsoluteFill style={{
      clipPath,
      background: 'rgba(13,17,23,0.06)',
      pointerEvents: 'none',
      zIndex: 99,
    }} />
  );
};

// ==================== Glitch Transition ====================

interface GlitchTransitionProps {
  triggerFrame: number;
}

export const GlitchTransition: React.FC<GlitchTransitionProps> = ({
  triggerFrame,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const duration = 15;

  const progress = spring({
    frame: frame - triggerFrame,
    fps,
    config: { damping: 8, stiffness: 200, mass: 0.3 },
  });

  if (progress <= 0 || progress >= 1.5) return null;

  // RGB split effect
  const splitX = interpolate(Math.sin(frame * 1.5), [-1, 1], [-8, 8]);
  const splitY = interpolate(Math.cos(frame * 2.1), [-1, 1], [-3, 3]);
  const flash = interpolate(Math.abs(Math.sin(frame * 3)), [0, 1], [0, 0.15]);

  return (
    <AbsoluteFill style={{
      pointerEvents: 'none',
      zIndex: 100,
      background: `rgba(88,166,255,${flash})`,
      mixBlendMode: 'screen',
    }}>
      {/* scan line slices */}
      {Array.from({ length: 6 }).map((_, i) => {
        const y = interpolate(
          Math.sin(frame * 0.7 + i * 1.2),
          [-1, 1],
          [0, 100],
        );
        const h = interpolate(Math.random(), [0, 1], [2, 8]);
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              top: `${y}%`,
              height: `${h}%`,
              background: `rgba(255,${i % 2 === 0 ? 107 : 88},53,0.3)`,
              transform: `translateX(${splitX * (i % 3 - 1)}px) translateY(${splitY}px)`,
              opacity: progress > 1 ? 1 - (progress - 1) * 2 : progress,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

// ==================== Zoom Cross Transition ====================

interface ZoomCrossTransitionProps {
  triggerFrame: number;
}

export const ZoomCrossTransition: React.FC<ZoomCrossTransitionProps> = ({
  triggerFrame,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const duration = 18;

  const progress = spring({
    frame: frame - triggerFrame,
    fps,
    config: { damping: 12, stiffness: 70, mass: 0.5 },
  });
  const clamped = Math.min(1, Math.max(0, progress));

  if (clamped <= 0 || clamped >= 1) return null;

  const scale = interpolate(clamped, [0, 0.5, 1], [1, 0.85, 1]);
  const blur = interpolate(clamped, [0, 0.5, 1], [0, 6, 0]);
  const flashOpacity = interpolate(clamped, [0.4, 0.5, 0.6], [0, 0.3, 0]);

  return (
    <AbsoluteFill style={{
      pointerEvents: 'none',
      zIndex: 99,
      transform: `scale(${scale})`,
      filter: `blur(${blur}px)`,
      background: `rgba(13,17,23,${flashOpacity * 2})`,
    }}>
      {/* radial flash */}
      <div style={{
        position: 'absolute',
        inset: 0,
        background: `radial-gradient(ellipse at center, rgba(88,166,255,${flashOpacity}) 0%, transparent 70%)`,
      }} />
    </AbsoluteFill>
  );
};

// ==================== Combined Transition Overlay ====================

interface TransitionOverlayProps {
  type: PageTransition;
  triggerFrame: number;
}

export const TransitionOverlay: React.FC<TransitionOverlayProps> = ({
  type,
  triggerFrame,
}) => {
  switch (type) {
    case 'pageFlipRight':
      return <PageFlipTransition triggerFrame={triggerFrame} direction="right" />;
    case 'pageFlipLeft':
      return <PageFlipTransition triggerFrame={triggerFrame} direction="left" />;
    case 'wipeRight':
      return <WipeTransition triggerFrame={triggerFrame} direction="right" />;
    case 'wipeLeft':
      return <WipeTransition triggerFrame={triggerFrame} direction="left" />;
    case 'wipeUp':
      return <WipeTransition triggerFrame={triggerFrame} direction="up" />;
    case 'wipeDown':
      return <WipeTransition triggerFrame={triggerFrame} direction="down" />;
    case 'glitch':
      return <GlitchTransition triggerFrame={triggerFrame} />;
    case 'zoomCross':
      return <ZoomCrossTransition triggerFrame={triggerFrame} />;
    default:
      return null;
  }
};
