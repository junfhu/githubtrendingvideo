import {
  AbsoluteFill,
  Audio,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
  Img,
  staticFile,
  getInputProps,
} from 'remotion';
import {
  useEnterAnimation,
  useExitAnimation,
} from './Transitions';
import type { EnterStyle, ExitStyle, PageTransition } from './Transitions';

const FONT_FAMILY = '"Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif';

const COLORS = {
  bg: '#0d1117',
  card: '#161b22',
  border: '#30363d',
  blue: '#58a6ff',
  gold: '#f0c040',
  orange: '#ff6b35',
  text: '#c9d1d9',
  heading: '#f0f6fc',
  muted: '#8b949e',
  // Light-mode colors for white background scenes
  textDark: '#24292f',
  headingDark: '#1a1a2e',
  mutedDark: '#656d76',
  borderDark: '#d0d7de',
  cardDark: '#f6f8fa',
  blueDark: '#0969da',
};

interface Feature {
  name: string;
  desc: string;
  icon: string;
}

interface VideoProps {
  repo: string;
  name?: string;
  totalStars: string;
  weeklyStars: string;
  language: string;
  description: string;
  author: string;
  authorTitle: string;
  features: Feature[];
  screenshot: string;
  screenshotIntro?: string;
  starScreenshot?: string;
  audio: string;
  narrationTiming?: Record<string, number>;
  sceneDurations?: Record<string, number>;
  sceneAudio?: Record<string, string>;
}

const DEFAULT_FEATURES: Feature[] = [
  { name: '/feature-1', desc: 'Core capability description', icon: '🚀' },
  { name: '/feature-2', desc: 'Secondary feature overview', icon: '⚡' },
  { name: '/feature-3', desc: 'Additional functionality detail', icon: '🔧' },
  { name: '/feature-4', desc: 'Key workflow enhancement', icon: '📦' },
  { name: '/feature-5', desc: 'Advanced integration support', icon: '🎯' },
  { name: '/feature-6', desc: 'Enterprise-grade reliability', icon: '🛡️' },
];

// ==================== Background ====================

const GradientBg = () => (
  <div style={{ position: 'absolute', inset: 0, background: COLORS.bg }} />
);

// ==================== Typewriter Component ====================

const TypewriterText: React.FC<{
  text: string; startFrame: number; charDuration: number;
  frame: number; fps: number; color: string;
}> = ({ text, startFrame, charDuration, frame, color }) => {
  const totalChars = Math.floor(interpolate(
    frame, [startFrame, startFrame + text.length * charDuration],
    [0, text.length],
    { extrapolateRight: 'clamp' },
  ));
  return <span style={{ color }}>{text.slice(0, totalChars)}</span>;
};

// ==================== Scene timing & transition config ====================

interface SceneDef {
  name: string;
  start: number;
  end: number;
  enter: EnterStyle;
  exit: ExitStyle;
  nextTransition: PageTransition;
}

// Scene timing — calculated from narrationTiming in props
let SCENES: SceneDef[] = [];

function buildScenes(totalFrames: number, _timing: Record<string, number> | undefined, durations: Record<string, number> | undefined): SceneDef[] {
  const T = totalFrames;
  const fps = 30;

  // Use exact audio durations for each scene
  const dur = (key: string, fallback: number) => {
    const sec = (durations && durations[key]) ? durations[key] : fallback;
    return Math.round(sec * fps);
  };

  const s1Frames = dur('s1', 80);
  const s2Frames = dur('s2', 30);
  const s3Frames = dur('s3', 70);
  const s4Frames = dur('s4', 60);
  const s5Frames = dur('s5', 300);
  const s6Frames = dur('s6', 200);
  const s7Frames = dur('s7', 80);

  // Cumulative start positions
  let t = 0;
  const s1 = { start: t, end: t + s1Frames }; t += s1Frames;
  const s2 = { start: t - 10, end: t + s2Frames }; t += s2Frames;
  const s3 = { start: t - 10, end: t + s3Frames }; t += s3Frames;
  const s4 = { start: t - 10, end: t + s4Frames }; t += s4Frames;
  const s5 = { start: t - 10, end: t + s5Frames - 8 }; t += s5Frames;
  const s6 = { start: t + 2,   end: t + s6Frames }; t += s6Frames;
  const s7 = { start: t + 2,   end: T };

  return [
    { name: 'intro_text',      start: s1.start, end: s1.end, enter: 'fade' as EnterStyle, exit: 'fade' as ExitStyle, nextTransition: 'none' as PageTransition },
    { name: 'intro_project',   start: s2.start, end: s2.end, enter: 'fade' as EnterStyle, exit: 'fade' as ExitStyle, nextTransition: 'none' as PageTransition },
    { name: 'screenshot',      start: s3.start, end: s3.end, enter: 'fade' as EnterStyle, exit: 'fade' as ExitStyle, nextTransition: 'none' as PageTransition },
    { name: 'star_detail',     start: s4.start, end: s4.end, enter: 'fade' as EnterStyle, exit: 'fade' as ExitStyle, nextTransition: 'none' as PageTransition },
    { name: 'intro_screenshot',start: s5.start, end: s5.end, enter: 'fade' as EnterStyle, exit: 'fade' as ExitStyle, nextTransition: 'none' as PageTransition },
    { name: 'features',        start: s6.start, end: s6.end, enter: 'fade' as EnterStyle, exit: 'fade' as ExitStyle, nextTransition: 'none' as PageTransition },
    { name: 'outro',           start: s7.start, end: s7.end, enter: 'fade' as EnterStyle, exit: 'none' as ExitStyle, nextTransition: 'none' as PageTransition },
  ];
}

// ==================== Main Composition ====================

export const MainComposition = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const props = getInputProps() as unknown as VideoProps;

  const repo = props.repo || 'owner/repo';
  const displayName = props.name || repo.split('/').pop() || repo;
  const totalStars = props.totalStars || '0';
  const weeklyStars = props.weeklyStars || '0';
  const language = props.language || 'Unknown';
  const description = props.description || '';
  const author = props.author || 'Unknown';
  const authorTitle = props.authorTitle || '';
  const features = props.features || DEFAULT_FEATURES;
  const screenshotSrc = props.screenshot ? staticFile(props.screenshot) : '';
  const screenshotIntroSrc = props.screenshotIntro ? staticFile(props.screenshotIntro) : '';
  const audioSrc = props.audio ? staticFile(props.audio) : '';

  // Build scenes from exact audio durations (7 concatenated files → one combined audio)
  SCENES = buildScenes(durationInFrames, props.narrationTiming, props.sceneDurations);
  const S = SCENES;

  // --- Per-scene enter/exit animations (7 scenes) ---
  const e0 = useEnterAnimation(S[0].enter, S[0].start); const x0 = useExitAnimation(S[0].exit, S[0].end - 15);
  const e1 = useEnterAnimation(S[1].enter, S[1].start); const x1 = useExitAnimation(S[1].exit, S[1].end - 15);
  const e2 = useEnterAnimation(S[2].enter, S[2].start); const x2 = useExitAnimation(S[2].exit, S[2].end - 15);
  const e3 = useEnterAnimation(S[3].enter, S[3].start); const x3 = useExitAnimation(S[3].exit, S[3].end - 15);
  const e4 = useEnterAnimation(S[4].enter, S[4].start); const x4 = useExitAnimation(S[4].exit, S[4].end - 15);
  const e5 = useEnterAnimation(S[5].enter, S[5].start); const x5 = useExitAnimation(S[5].exit, S[5].end - 15);
  const e6 = useEnterAnimation(S[6].enter, S[6].start);

  const enterAnims = [e0, e1, e2, e3, e4, e5, e6];
  const exitAnims = [x0, x1, x2, x3, x4, x5, { transform: 'none', opacity: 0 }];

  const isActive = (i: number) => frame >= S[i].start && frame <= S[i].end;

  const sceneStyle = (i: number) => {
    if (!isActive(i) && frame > S[i].end) return { transform: 'none', opacity: 0 };
    return frame < S[i].end - 15 ? enterAnims[i] : exitAnims[i];
  };

  // --- S1: Title ---

  // --- S2 ---
  const screenSpring = spring({ frame: frame - S[2].start, fps, config: { damping: 18, stiffness: 70 } });
  const screenScale = interpolate(screenSpring, [0, 1], [1.12, 1.0]);

  // --- S3: Star area zoom — matches "总计xxxx颗星" in narration ---
  const starActive = isActive(3);
  const starEnterProgress = spring({ frame: frame - S[3].start, fps, config: { damping: 14, stiffness: 70 } });
  const starZoom = interpolate(starEnterProgress, [0, 1], [1.0, 1.6]);
  const starPanX = interpolate(starEnterProgress, [0, 1], [0, -100]);
  const starPanY = interpolate(starEnterProgress, [0, 1], [0, -30]);

  const weeklyDelay = S[3].start + 5;
  const weeklyOpacity = interpolate(frame, [weeklyDelay, weeklyDelay + 12], [0, 1], { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' });
  const weeklySlideIn = spring({ frame: frame - weeklyDelay, fps, config: { damping: 14, stiffness: 70 } });

  // --- S6: Features — timing from exact audio duration ---
  const s6Dur = S[5].end - S[5].start;
  const featCount = Math.min(features.length, 6);
  const featureFrames = Array.from({length: featCount}, (_, i) =>
    Math.floor(s6Dur * 0.06 + i * (s6Dur * 0.84 / featCount))
  );
  let currentFeatureIdx = -1;
  for (let i = 0; i < featureFrames.length; i++) {
    if (frame >= S[5].start + featureFrames[i]) currentFeatureIdx = i;
  }

  // --- S6: Outro ---
  const outroFade = interpolate(frame, [S[6].end - 30, S[6].end], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg, fontFamily: FONT_FAMILY }}>
      {audioSrc && <Audio src={audioSrc} volume={1} />}
      <AbsoluteFill style={{ opacity: outroFade }}>
        <GradientBg />
        {/* Watermark — bottom-right corner, semi-transparent dark bg card */}
        <div style={{
          position: 'absolute', bottom: 28, right: 40, zIndex: 999,
          background: 'rgba(13,17,23,0.7)', borderRadius: 8,
          padding: '6px 18px', pointerEvents: 'none',
        }}>
          <span style={{ color: 'rgba(255,255,255,0.35)', fontSize: 20, fontWeight: 500, letterSpacing: 6 }}>
            慕涯
          </span>
        </div>


        {/* ===== S1: INTRO TEXT — modern frontend aesthetic ===== */}
        <AbsoluteFill style={{
          ...sceneStyle(0), justifyContent: 'center', alignItems: 'center',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        }}>
          <div style={{
            background: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(20px)',
            borderRadius: 20, padding: '48px 72px',
            border: '1px solid rgba(255,255,255,0.2)',
            boxShadow: '0 20px 60px rgba(0,0,0,0.15), 0 0 120px rgba(102,126,234,0.2)',
          }}>
            <div style={{
              color: '#ffffff', fontSize: 44, fontWeight: 600,
              letterSpacing: '0.04em', fontFamily: FONT_FAMILY,
              textShadow: '0 2px 4px rgba(0,0,0,0.1)',
            }}>
              <TypewriterText
                text="今天介绍的GitHub热门项目是"
                startFrame={5}
                charDuration={3}
                frame={frame}
                fps={fps}
                color="#ffffff"
              />
              {frame < 5 + 15 * 3 + 12 ? (
                <span style={{ color: '#ffd700', opacity: Math.abs(Math.sin(frame * 0.4)) > 0.3 ? 1 : 0, fontWeight: 300 }}>|</span>
              ) : null}
            </div>
          </div>
        </AbsoluteFill>

        {/* ===== S2: INTRO PROJECT — modern frontend card aesthetic ===== */}
        <AbsoluteFill style={{
          ...sceneStyle(1), justifyContent: 'center', alignItems: 'center',
          background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 900, width: '100%' }}>
            {/* Project header card */}
            <div style={{
              background: '#ffffff', borderRadius: 16, padding: '40px 52px',
              boxShadow: '0 8px 32px rgba(0,0,0,0.08), 0 2px 8px rgba(0,0,0,0.04)',
              opacity: interpolate(frame, [S[1].start + 5, S[1].start + 22], [0, 1], { extrapolateRight: 'clamp' }),
              transform: `translateY(${interpolate(spring({ frame: frame - S[1].start - 3, fps, config: { damping: 10, stiffness: 60, mass: 0.7 } }), [0, 1], [50, 0])}px)`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
                <div style={{
                  width: 44, height: 44, borderRadius: 12,
                  background: 'linear-gradient(135deg, #667eea, #764ba2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 22, color: '#fff',
                }}>📦</div>
                <div>
                  <div style={{ color: '#1a1a2e', fontSize: 32, fontWeight: 700, letterSpacing: '-0.01em' }}>{displayName}</div>
                  <div style={{ color: '#8b8fa3', fontSize: 14, marginTop: 2 }}>
                    <span style={{
                      display: 'inline-block', padding: '2px 10px', borderRadius: 6,
                      background: 'rgba(102,126,234,0.1)', color: '#667eea',
                      fontSize: 12, fontWeight: 600,
                      opacity: interpolate(frame, [S[1].start + 28, S[1].start + 45], [0, 1], { extrapolateRight: 'clamp' }),
                    }}>{language}</span>
                  </div>
                </div>
              </div>
              <div style={{
                color: '#4a4d5e', fontSize: 16, lineHeight: 1.6,
                opacity: interpolate(frame, [S[1].start + 18, S[1].start + 35], [0, 1], { extrapolateRight: 'clamp' }),
              }}>
                {description}
              </div>
            </div>

            {/* Stats cards row */}
            <div style={{
              display: 'flex', gap: 20,
              opacity: interpolate(frame, [S[1].start + 35, S[1].start + 52], [0, 1], { extrapolateRight: 'clamp' }),
            }}>
              <div style={{
                flex: 1, background: '#ffffff', borderRadius: 14, padding: '24px 28px',
                boxShadow: '0 4px 16px rgba(0,0,0,0.06)',
                borderLeft: '4px solid #f0c040',
              }}>
                <div style={{ color: '#8b8fa3', fontSize: 12, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>Total Stars</div>
                <div style={{ color: '#1a1a2e', fontSize: 42, fontWeight: 800, display: 'flex', alignItems: 'baseline', gap: 6 }}>
                  <span style={{ fontSize: 20, color: '#f0c040' }}>⭐</span>
                  {Number(totalStars.replace(/,/g, '')).toLocaleString()}
                </div>
              </div>
              <div style={{
                flex: 1, background: '#ffffff', borderRadius: 14, padding: '24px 28px',
                boxShadow: '0 4px 16px rgba(0,0,0,0.06)',
                borderLeft: '4px solid #ff6b35',
              }}>
                <div style={{ color: '#8b8fa3', fontSize: 12, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>This Week</div>
                <div style={{ color: '#1a1a2e', fontSize: 42, fontWeight: 800, display: 'flex', alignItems: 'baseline', gap: 6 }}>
                  <span style={{ fontSize: 20, color: '#ff6b35' }}>🔥</span>
                  +{weeklyStars}
                </div>
              </div>
            </div>
          </div>
        </AbsoluteFill>

        {/* ===== S3: SCREENSHOT + STAR TEXT OVERLAY ===== */}
        <div style={{ ...sceneStyle(2), position: 'absolute', inset: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', transform: sceneStyle(2).transform === 'none' ? `scale(${screenScale})` : `${sceneStyle(2).transform} scale(${screenScale})`, transformOrigin: 'center top' }}>
          {screenshotSrc ? (
            <>
              <div style={{ overflow: 'hidden', borderRadius: 8, boxShadow: '0 0 80px rgba(88,166,255,0.15), 0 16px 48px rgba(0,0,0,0.6)', border: '1px solid #21262d' }}>
                <Img src={screenshotSrc} style={{ width: 1920, height: 1080, objectFit: 'cover' }} />
              </div>
              {/* Star count text overlay */}
              <AbsoluteFill style={{ pointerEvents: 'none', opacity: interpolate(frame, [270, 285], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) }}>
                <div style={{
                  position: 'absolute', left: '6%', top: '52%',
                  opacity: interpolate(frame, [175, 190], [0, 1], { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' }),
                  background: 'rgba(13,17,23,0.85)', borderRadius: 16, padding: '20px 36px',
                }}>
                  <div style={{ color: '#f0c040', fontSize: 16, fontWeight: 700, letterSpacing: 3, marginBottom: 6 }}>⭐ Total Stars</div>
                  <div style={{ color: '#ffffff', fontSize: 56, fontWeight: 900, lineHeight: 1 }}>{Number(totalStars.replace(/,/g, '')).toLocaleString()}</div>
                </div>
                <div style={{
                  position: 'absolute', left: '6%', top: '72%',
                  opacity: interpolate(frame, [180, 195], [0, 1], { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' }),
                  transform: `translateX(${interpolate(spring({ frame: frame - 180, fps, config: { damping: 14, stiffness: 70 } }), [0, 1], [40, 0])}px)`,
                  background: 'rgba(13,17,23,0.85)', borderRadius: 14, padding: '16px 32px',
                }}>
                  <div style={{ color: '#ff6b35', fontSize: 14, fontWeight: 700, letterSpacing: 2, marginBottom: 4 }}>🔥 This Week</div>
                  <div style={{ color: '#ffffff', fontSize: 36, fontWeight: 900 }}>+{weeklyStars} <span style={{ color: '#c0c0c0', fontSize: 18, fontWeight: 500 }}>stars</span></div>
                </div>
              </AbsoluteFill>
            </>
          ) : (
            /* Fallback: star cards without screenshot */
            <div style={{ display: 'flex', gap: 32, justifyContent: 'center', alignItems: 'center' }}>
              <div style={{ background: COLORS.card, borderRadius: 20, padding: '40px 60px', border: `1px solid ${COLORS.border}`, textAlign: 'center' }}>
                <div style={{ color: '#f0c040', fontSize: 18, fontWeight: 700, letterSpacing: 3, marginBottom: 12 }}>⭐ Total Stars</div>
                <div style={{ color: COLORS.heading, fontSize: 72, fontWeight: 900 }}>{Number(totalStars.replace(/,/g, '')).toLocaleString()}</div>
              </div>
              <div style={{ background: COLORS.card, borderRadius: 20, padding: '40px 60px', border: `1px solid ${COLORS.border}`, textAlign: 'center' }}>
                <div style={{ color: '#ff6b35', fontSize: 18, fontWeight: 700, letterSpacing: 3, marginBottom: 12 }}>🔥 This Week</div>
                <div style={{ color: COLORS.heading, fontSize: 72, fontWeight: 900 }}>+{weeklyStars}</div>
              </div>
            </div>
          )}
        </div>

        {/* ===== S4: STAR AREA WITH RED CIRCLE ===== */}
        {starActive && screenshotSrc && (
          <AbsoluteFill style={{ ...sceneStyle(3), background: '#ffffff' }}>
            {/* Screenshot zoomed into far top-right where star button is (~89% left, ~9% top) */}
            <div style={{
              position: 'absolute', inset: 0,
              transform: `scale(${starZoom}) translateX(${starPanX}px) translateY(${starPanY}px)`,
              transformOrigin: '92% 9%',
            }}>
              <Img src={screenshotSrc} style={{ width: 1920, height: 1080, objectFit: 'contain' }} />
            </div>

            {/* Semi-transparent overlay for text readability */}
            <div style={{
              position: 'absolute', inset: 0,
              background: 'linear-gradient(135deg, rgba(13,17,23,0.55) 0%, rgba(13,17,23,0.25) 40%, rgba(13,17,23,0.1) 100%)',
            }} />

            {/* Total stars count — dark card background */}
            <div style={{
              position: 'absolute', left: '6%', top: '48%',
              opacity: interpolate(frame, [S[3].start + 5, S[3].start + 20], [0, 1], { extrapolateRight: 'clamp' }),
              background: 'rgba(13,17,23,0.85)', borderRadius: 16, padding: '20px 36px',
            }}>
              <div style={{ color: '#f0c040', fontSize: 16, fontWeight: 700, letterSpacing: 3, marginBottom: 6 }}>⭐ Total Stars</div>
              <div style={{ color: '#ffffff', fontSize: 64, fontWeight: 900, lineHeight: 1 }}>{Number(totalStars.replace(/,/g, '')).toLocaleString()}</div>
            </div>

            {/* Weekly stars — dark card background */}
            <div style={{
              position: 'absolute', left: '6%', top: '68%',
              opacity: weeklyOpacity,
              transform: `translateX(${interpolate(weeklySlideIn, [0, 1], [50, 0])}px)`,
              background: 'rgba(13,17,23,0.85)', borderRadius: 14, padding: '16px 32px',
            }}>
              <div style={{ color: '#ff6b35', fontSize: 14, fontWeight: 700, letterSpacing: 2, marginBottom: 4 }}>🔥 This Week</div>
              <div style={{ color: '#ffffff', fontSize: 36, fontWeight: 900 }}>+{weeklyStars} <span style={{ color: '#c0c0c0', fontSize: 18, fontWeight: 500 }}>stars</span></div>
            </div>
          </AbsoluteFill>
        )}

        {/* ===== S5: INTRO SCREENSHOT — slow scroll-up ===== */}
        <AbsoluteFill style={{ ...sceneStyle(4), background: '#ffffff', overflow: 'hidden' }}>
          {screenshotIntroSrc ? (
            (() => {
              // Smooth scroll from top to bottom of the tall screenshot
              const sceneProgress = interpolate(
                frame, [S[4].start, S[4].end], [0, 1],
                { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
              );
              const scrollY = interpolate(sceneProgress, [0, 1], [0, -200]);
              return (
                <div style={{
                  width: '100%', height: '100%',
                  transform: `translateY(${scrollY}%)`,
                  transition: 'transform 0.1s linear',
                }}>
                  <Img src={screenshotIntroSrc} style={{
                    width: '100%', height: 'auto', minHeight: '100%',
                  }} />
                </div>
              );
            })()
          ) : (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: COLORS.mutedDark, fontSize: 20 }}>
              {description || 'Project introduction'}
            </div>
          )}
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0, height: 120,
            background: 'linear-gradient(transparent, rgba(255,255,255,0.7))',
            pointerEvents: 'none',
          }} />
        </AbsoluteFill>

        {/* ===== S6: FEATURES ===== */}
        <AbsoluteFill style={{ ...sceneStyle(5), justifyContent: 'center', alignItems: 'center', flexDirection: 'row', gap: 40, padding: '0 120px', background: '#ffffff' }}>
          <div style={{ flex: '0 0 55%', display: 'flex', flexDirection: 'column', gap: 12, zIndex: 1 }}>
            <div style={{ color: COLORS.blueDark, fontSize: 16, fontWeight: 600, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 8 }}>Core Features</div>
            {features.map((feat, i) => {
              const isActive = i === currentFeatureIdx;
              const isPast = i < currentFeatureIdx;
              const cardOpacity = isActive ? 1 : isPast ? 0.5 : 0.3;
              const isEntering = isActive
                ? spring({ frame: frame - S[5].start - featureFrames[i], fps, config: { damping: 12, stiffness: 80 } })
                : 1;
              return (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 16,
                  padding: '14px 24px', borderRadius: 10,
                  background: isActive ? `rgba(9,105,218,0.06)` : 'rgba(255,255,255,0.7)',
                  border: `1px solid ${isActive ? COLORS.blueDark : COLORS.borderDark}`,
                  borderLeft: `4px solid ${isActive ? COLORS.blueDark : COLORS.borderDark}`,
                  opacity: cardOpacity,
                  transform: `translateX(${interpolate(isEntering, [0, 1], [60, 0])}px) scale(${isActive ? 1.03 : 1})`,
                  backdropFilter: 'blur(4px)',
                }}>
                  <span style={{ fontSize: 28, flexShrink: 0 }}>{feat.icon}</span>
                  <div>
                    <div style={{ color: COLORS.headingDark, fontSize: 20, fontWeight: 700, fontFamily: 'monospace' }}>{feat.name}</div>
                    <div style={{ color: COLORS.mutedDark, fontSize: 14, marginTop: 2 }}>{feat.desc}</div>
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ flex: '0 0 35%', background: COLORS.cardDark, borderRadius: 16, padding: 32, border: `1px solid ${COLORS.borderDark}`, boxShadow: '0 4px 16px rgba(0,0,0,0.08)', zIndex: 1 }}>
            <div style={{ color: COLORS.mutedDark, fontSize: 12, letterSpacing: 2, textTransform: 'uppercase', marginBottom: 8 }}>About This Project</div>
            <div style={{ color: COLORS.headingDark, fontSize: 22, fontWeight: 700, marginBottom: 16, lineHeight: 1.4 }}>{description}</div>
            <div style={{ color: COLORS.textDark, fontSize: 15, lineHeight: 1.6 }}>{language !== 'Unknown' ? `Built with ${language} and designed for professional workflows.` : ''} Star the repo to stay updated with new features and releases.</div>
            <div style={{ marginTop: 20, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {[language, 'GitHub Trending', 'Open Source', 'DevTools'].slice(0, 4).map((tag) => (
                <span key={tag} style={{ padding: '4px 12px', borderRadius: 20, background: 'rgba(9,105,218,0.08)', color: COLORS.blueDark, fontSize: 12, fontWeight: 500 }}>{tag}</span>
              ))}
            </div>
          </div>
        </AbsoluteFill>

        {/* ===== S7: OUTRO — modern frontend aesthetic ===== */}
        <AbsoluteFill style={{
          ...sceneStyle(6), justifyContent: 'center', alignItems: 'center',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        }}>
          <div style={{
            background: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(20px)',
            borderRadius: 20, padding: '52px 72px',
            border: '1px solid rgba(255,255,255,0.2)',
            boxShadow: '0 20px 60px rgba(0,0,0,0.15), 0 0 120px rgba(102,126,234,0.2)',
            textAlign: 'center',
          }}>
            <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: 14, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 16 }}>
              GitHub Trending · 2026
            </div>
            <div style={{
              color: '#ffffff', fontSize: 42, fontWeight: 600,
              letterSpacing: '0.04em', fontFamily: FONT_FAMILY,
              textShadow: '0 2px 4px rgba(0,0,0,0.1)', lineHeight: 1.4,
            }}>
              关注我，获得最新的<br/>实用项目信息
            </div>
          </div>
        </AbsoluteFill>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
