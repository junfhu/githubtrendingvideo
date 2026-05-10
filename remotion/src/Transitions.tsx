import { useCurrentFrame, useVideoConfig, interpolate, Easing } from 'remotion';

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

// ==================== Hook: useEnterAnimation ====================

export function useEnterAnimation(
  style: EnterStyle,
  startFrame: number,
  duration = 20,
) {
  const frame = useCurrentFrame();

  const progress = interpolate(
    frame,
    [startFrame, startFrame + duration],
    [0, 1],
    {
      easing: Easing.bezier(0.16, 1, 0.3, 1),
      extrapolateRight: 'clamp',
      extrapolateLeft: 'clamp',
    },
  );

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
        transform: `translateY(${interpolate(progress, [0, 1], [200, 0])}px)`,
        opacity,
      };
    case 'slideDown':
      return {
        transform: `translateY(${interpolate(progress, [0, 1], [-200, 0])}px)`,
        opacity,
      };
    case 'slideLeft':
      return {
        transform: `translateX(${interpolate(progress, [0, 1], [400, 0])}px)`,
        opacity,
      };
    case 'slideRight':
      return {
        transform: `translateX(${interpolate(progress, [0, 1], [-400, 0])}px)`,
        opacity,
      };
    case 'zoomIn':
      return {
        transform: `scale(${interpolate(progress, [0, 1], [0.7, 1])})`,
        opacity,
      };
    case 'floatUp': {
      const y = interpolate(progress, [0, 1], [150, 0]);
      const s = interpolate(progress, [0, 1], [0.95, 1]);
      return { transform: `translateY(${y}px) scale(${s})`, opacity };
    }
    case 'floatDown': {
      const y = interpolate(progress, [0, 1], [-100, 0]);
      const s = interpolate(progress, [0, 1], [0.95, 1]);
      return { transform: `translateY(${y}px) scale(${s})`, opacity };
    }
    case 'pop':
      return {
        transform: `scale(${interpolate(progress, [0, 1], [0.5, 1], { easing: Easing.bezier(0.34, 1.56, 0.64, 1) })})`,
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

  const progress = interpolate(
    frame,
    [exitFrame, exitFrame + duration],
    [0, 1],
    {
      easing: Easing.in(Easing.cubic),
      extrapolateRight: 'clamp',
      extrapolateLeft: 'clamp',
    },
  );

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
        transform: `translateY(${interpolate(progress, [0, 1], [0, -200])}px)`,
        opacity,
      };
    case 'slideDown':
      return {
        transform: `translateY(${interpolate(progress, [0, 1], [0, 200])}px)`,
        opacity,
      };
    case 'slideLeft':
      return {
        transform: `translateX(${interpolate(progress, [0, 1], [0, -400])}px)`,
        opacity,
      };
    case 'slideRight':
      return {
        transform: `translateX(${interpolate(progress, [0, 1], [0, 400])}px)`,
        opacity,
      };
    case 'zoomOut':
      return {
        transform: `scale(${interpolate(progress, [0, 1], [1, 1.3])})`,
        opacity,
      };
    case 'floatUp': {
      const y = interpolate(progress, [0, 1], [0, -120]);
      const s = interpolate(progress, [0, 1], [1, 0.9]);
      return { transform: `translateY(${y}px) scale(${s})`, opacity };
    }
    case 'floatDown': {
      const y = interpolate(progress, [0, 1], [0, 120]);
      return { transform: `translateY(${y}px)`, opacity };
    }
    case 'shrink':
      return {
        transform: `scale(${interpolate(progress, [0, 1], [1, 0.5])})`,
        opacity,
      };
    default:
      return { transform: 'none', opacity: 1 };
  }
}
