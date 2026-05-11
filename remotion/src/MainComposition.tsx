import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
  Img,
  staticFile,
  getInputProps,
} from 'remotion';
import { Audio } from '@remotion/media';
import {
  useEnterAnimation,
  useExitAnimation,
} from './Transitions';
import type { EnterStyle, ExitStyle } from './Transitions';
import { loadFont } from '@remotion/google-fonts/NotoSansSC';

const { fontFamily } = loadFont('normal', { weights: ['400', '700'], ignoreTooManyRequestsWarning: true });

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
  screenshotIntroHeight?: number;
  demoImages?: string[];
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
  const s5Frames = dur('s5', 500);
  const s6Frames = dur('s7', 80);

  // Cumulative start positions (S6 removed, S7→S6)
  let t = 0;
  const s1 = { start: t, end: t + s1Frames }; t += s1Frames;
  const s2 = { start: t - 10, end: t + s2Frames }; t += s2Frames;
  const s3 = { start: t - 10, end: t + s3Frames }; t += s3Frames;
  const s4 = { start: t - 10, end: t + s4Frames }; t += s4Frames;
  const s5 = { start: t - 10, end: t + s5Frames - 8 }; t += s5Frames;
  const s6 = { start: t + 2,   end: T };

  return [
    { name: 'intro_text',      start: s1.start, end: s1.end, enter: 'fade' as EnterStyle, exit: 'fade' as ExitStyle },
    { name: 'intro_project',   start: s2.start, end: s2.end, enter: 'fade' as EnterStyle, exit: 'fade' as ExitStyle },
    { name: 'screenshot',      start: s3.start, end: s3.end, enter: 'fade' as EnterStyle, exit: 'fade' as ExitStyle },
    { name: 'star_detail',     start: s4.start, end: s4.end, enter: 'fade' as EnterStyle, exit: 'fade' as ExitStyle },
    { name: 'intro_screenshot',start: s5.start, end: s5.end, enter: 'fade' as EnterStyle, exit: 'fade' as ExitStyle },
    { name: 'outro',           start: s6.start, end: s6.end, enter: 'fade' as EnterStyle, exit: 'none' as ExitStyle },
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
  const hasWeeklyStars = props.weeklyStars && props.weeklyStars !== '?' && props.weeklyStars !== '0';
  const language = props.language || 'Unknown';
  const description = props.description || '';
  const author = props.author || 'Unknown';
  const authorTitle = props.authorTitle || '';
  const features = props.features || DEFAULT_FEATURES;
  const screenshotSrc = props.screenshot ? staticFile(props.screenshot) : '';
  const screenshotIntroSrc = props.screenshotIntro ? staticFile(props.screenshotIntro) : '';
  const introHeight = props.screenshotIntroHeight || 0;
  const introFitsScreen = introHeight > 0 && introHeight <= 1080;
  const demoImages = (props.demoImages || []).filter(Boolean);
  const hasDemoImages = demoImages.length > 0;
  const audioSrc = props.audio ? staticFile(props.audio) : '';

  // Build scenes from exact audio durations (7 concatenated files → one combined audio)
  SCENES = buildScenes(durationInFrames, props.narrationTiming, props.sceneDurations);
  const S = SCENES;

  // --- Per-scene enter/exit animations (6 scenes) ---
  const e0 = useEnterAnimation(S[0].enter, S[0].start); const x0 = useExitAnimation(S[0].exit, S[0].end - 15);
  const e1 = useEnterAnimation(S[1].enter, S[1].start); const x1 = useExitAnimation(S[1].exit, S[1].end - 15);
  const e2 = useEnterAnimation(S[2].enter, S[2].start); const x2 = useExitAnimation(S[2].exit, S[2].end - 15);
  const e3 = useEnterAnimation(S[3].enter, S[3].start); const x3 = useExitAnimation(S[3].exit, S[3].end - 15);
  const e4 = useEnterAnimation(S[4].enter, S[4].start); const x4 = useExitAnimation(S[4].exit, S[4].end - 15);
  const e5 = useEnterAnimation(S[5].enter, S[5].start);

  const enterAnims = [e0, e1, e2, e3, e4, e5];
  const exitAnims = [x0, x1, x2, x3, x4, { transform: 'none', opacity: 0 }];

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

  // --- Outro fade ---
  const outroFade = interpolate(frame, [S[5].end - 30, S[5].end], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg, fontFamily: fontFamily }}>
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
              letterSpacing: '0.04em', fontFamily: fontFamily,
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
              {hasWeeklyStars && (
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
              )}
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
                {hasWeeklyStars && (
                <div style={{
                  position: 'absolute', left: '6%', top: '72%',
                  opacity: interpolate(frame, [180, 195], [0, 1], { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' }),
                  transform: `translateX(${interpolate(spring({ frame: frame - 180, fps, config: { damping: 14, stiffness: 70 } }), [0, 1], [40, 0])}px)`,
                  background: 'rgba(13,17,23,0.85)', borderRadius: 14, padding: '16px 32px',
                }}>
                  <div style={{ color: '#ff6b35', fontSize: 14, fontWeight: 700, letterSpacing: 2, marginBottom: 4 }}>🔥 This Week</div>
                  <div style={{ color: '#ffffff', fontSize: 36, fontWeight: 900 }}>+{weeklyStars} <span style={{ color: '#c0c0c0', fontSize: 18, fontWeight: 500 }}>stars</span></div>
                </div>
                )}
              </AbsoluteFill>
            </>
          ) : (
            /* Fallback: star cards without screenshot */
            <div style={{ display: 'flex', gap: 32, justifyContent: 'center', alignItems: 'center' }}>
              <div style={{ background: COLORS.card, borderRadius: 20, padding: '40px 60px', border: `1px solid ${COLORS.border}`, textAlign: 'center' }}>
                <div style={{ color: '#f0c040', fontSize: 18, fontWeight: 700, letterSpacing: 3, marginBottom: 12 }}>⭐ Total Stars</div>
                <div style={{ color: COLORS.heading, fontSize: 72, fontWeight: 900 }}>{Number(totalStars.replace(/,/g, '')).toLocaleString()}</div>
              </div>
              {hasWeeklyStars && (
              <div style={{ background: COLORS.card, borderRadius: 20, padding: '40px 60px', border: `1px solid ${COLORS.border}`, textAlign: 'center' }}>
                <div style={{ color: '#ff6b35', fontSize: 18, fontWeight: 700, letterSpacing: 3, marginBottom: 12 }}>🔥 This Week</div>
                <div style={{ color: COLORS.heading, fontSize: 72, fontWeight: 900 }}>+{weeklyStars}</div>
              </div>
              )}
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
            {hasWeeklyStars && (
            <div style={{
              position: 'absolute', left: '6%', top: '68%',
              opacity: weeklyOpacity,
              transform: `translateX(${interpolate(weeklySlideIn, [0, 1], [50, 0])}px)`,
              background: 'rgba(13,17,23,0.85)', borderRadius: 14, padding: '16px 32px',
            }}>
              <div style={{ color: '#ff6b35', fontSize: 14, fontWeight: 700, letterSpacing: 2, marginBottom: 4 }}>🔥 This Week</div>
              <div style={{ color: '#ffffff', fontSize: 36, fontWeight: 900 }}>+{weeklyStars} <span style={{ color: '#c0c0c0', fontSize: 18, fontWeight: 500 }}>stars</span></div>
            </div>
            )}
          </AbsoluteFill>
        )}

        {/* ===== S5: PROJECT INTRODUCTION + DEMO IMAGES ===== */}
        <AbsoluteFill style={{ ...sceneStyle(4), background: '#0d1117', overflow: 'hidden' }}>
          {hasDemoImages ? (
            // Demo image carousel with ken-burns effect + project description overlay
            (() => {
              const s5Dur = S[4].end - S[4].start;
              const imgCount = demoImages.length;
              const framesPerImg = Math.max(30, Math.floor(s5Dur / imgCount));
              const currentImgIdx = Math.min(
                imgCount - 1,
                Math.floor((frame - S[4].start) / framesPerImg)
              );
              const imgLocalFrame = (frame - S[4].start) - currentImgIdx * framesPerImg;
              const imgProgress = imgLocalFrame / framesPerImg;

              const kbZoom = interpolate(imgProgress, [0, 1], [1.0, 1.08]);
              const kbPanX = interpolate(imgProgress, [0, 1], [0, -20]);
              const kbPanY = interpolate(imgProgress, [0, 1], [0, -10]);

              const fadeFrames = 12;
              const fadeIn = interpolate(imgLocalFrame, [0, fadeFrames], [0, 1], { extrapolateRight: 'clamp' });
              const fadeOut = (imgIdx: number) => imgIdx < imgCount - 1
                ? interpolate(imgLocalFrame, [framesPerImg - fadeFrames, framesPerImg], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
                : 1;

              return (
                <AbsoluteFill style={{ background: '#0d1117' }}>
                  {demoImages.map((imgName, idx) => {
                    const isCurrent = idx === currentImgIdx;
                    if (!isCurrent && idx !== currentImgIdx - 1) return null;
                    const opacity = idx === currentImgIdx
                      ? fadeIn * fadeOut(idx)
                      : (idx === currentImgIdx - 1 ? interpolate(imgLocalFrame, [0, fadeFrames], [1, 0], { extrapolateRight: 'clamp' }) : 0);
                    return (
                      <div key={idx} style={{
                        position: 'absolute', inset: 0,
                        opacity: Math.max(0, opacity),
                        display: 'flex', justifyContent: 'center', alignItems: 'center',
                      }}>
                        <div style={{
                          transform: isCurrent ? `scale(${kbZoom}) translate(${kbPanX}px, ${kbPanY}px)` : 'none',
                          transformOrigin: 'center center',
                          width: '100%', height: '100%',
                          display: 'flex', justifyContent: 'center', alignItems: 'center',
                        }}>
                          <Img src={staticFile(imgName)} style={{
                            maxWidth: '100%', maxHeight: '100%',
                            objectFit: 'contain',
                            borderRadius: 8,
                            boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
                          }} />
                        </div>
                      </div>
                    );
                  })}
                  {/* Image counter indicator */}
                  <div style={{
                    position: 'absolute', bottom: 140, left: '50%',
                    transform: 'translateX(-50%)',
                    display: 'flex', gap: 8, zIndex: 10,
                  }}>
                    {demoImages.map((_, idx) => (
                      <div key={idx} style={{
                        width: idx === currentImgIdx ? 24 : 8,
                        height: 8,
                        borderRadius: 4,
                        background: idx === currentImgIdx ? '#58a6ff' : 'rgba(255,255,255,0.3)',
                        transition: 'all 0.3s',
                      }} />
                    ))}
                  </div>
                  {/* Project description card overlay */}
                  <div style={{
                    position: 'absolute', bottom: 0, left: 0, right: 0,
                    background: 'linear-gradient(transparent 0%, rgba(13,17,23,0.92) 30%)',
                    padding: '60px 80px 40px',
                    opacity: interpolate(frame, [S[4].start + 8, S[4].start + 25], [0, 1], { extrapolateRight: 'clamp' }),
                  }}>
                    <div style={{ color: '#58a6ff', fontSize: 13, fontWeight: 600, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 10 }}>
                      Project Overview
                    </div>
                    <div style={{ color: '#f0f6fc', fontSize: 22, fontWeight: 700, lineHeight: 1.5, marginBottom: 10 }}>
                      {displayName}
                    </div>
                    <div style={{ color: '#8b949e', fontSize: 16, lineHeight: 1.6, maxWidth: 1200 }}>
                      {description || 'An open-source project on GitHub Trending.'}
                    </div>
                    <div style={{ display: 'flex', gap: 12, marginTop: 14, flexWrap: 'wrap' }}>
                      {[language, 'GitHub Trending', 'Open Source'].filter(Boolean).map((tag) => (
                        <span key={tag} style={{ padding: '3px 12px', borderRadius: 20, background: 'rgba(88,166,255,0.12)', color: '#58a6ff', fontSize: 12, fontWeight: 500 }}>{tag}</span>
                      ))}
                    </div>
                  </div>
                </AbsoluteFill>
              );
            })()
          ) : screenshotIntroSrc ? (
            // README screenshot with scroll + project description overlay
            (() => {
              const sceneProgress = interpolate(
                frame, [S[4].start, S[4].end], [0, 1],
                { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
              );
              return (
                <AbsoluteFill style={{ background: '#0d1117' }}>
                  {introFitsScreen ? (
                    <div style={{
                      width: '100%', height: '100%', display: 'flex',
                      alignItems: 'center', justifyContent: 'center',
                      background: '#ffffff',
                    }}>
                      <Img src={screenshotIntroSrc} style={{
                        width: '100%', height: 'auto', maxHeight: '100%',
                        objectFit: 'contain',
                      }} />
                    </div>
                  ) : (
                    <div style={{
                      width: '100%', height: '100%',
                      transform: `translateY(${interpolate(sceneProgress, [0, 0.1, 1], [0, 0, -65])}%) scale(${interpolate(sceneProgress, [0, 0.12, 1], [1, 1.02, 1.06])})`,
                      transformOrigin: 'center top',
                      background: '#ffffff',
                    }}>
                      <Img src={screenshotIntroSrc} style={{
                        width: '100%', height: 'auto', minHeight: '100%',
                      }} />
                    </div>
                  )}
                  {/* Project description overlay */}
                  <div style={{
                    position: 'absolute', bottom: 0, left: 0, right: 0,
                    background: 'linear-gradient(transparent 0%, rgba(13,17,23,0.92) 30%)',
                    padding: '60px 80px 40px',
                    opacity: interpolate(frame, [S[4].start + 8, S[4].start + 25], [0, 1], { extrapolateRight: 'clamp' }),
                  }}>
                    <div style={{ color: '#58a6ff', fontSize: 13, fontWeight: 600, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 10 }}>
                      Project Overview
                    </div>
                    <div style={{ color: '#f0f6fc', fontSize: 22, fontWeight: 700, lineHeight: 1.5, marginBottom: 10 }}>
                      What {displayName} Can Do
                    </div>
                    <div style={{ color: '#8b949e', fontSize: 16, lineHeight: 1.6, maxWidth: 1200 }}>
                      {description || 'A powerful open-source tool built for developers.'}
                    </div>
                    <div style={{ display: 'flex', gap: 12, marginTop: 14, flexWrap: 'wrap' }}>
                      {[language, 'GitHub Trending', 'Open Source'].filter(Boolean).map((tag) => (
                        <span key={tag} style={{ padding: '3px 12px', borderRadius: 20, background: 'rgba(88,166,255,0.12)', color: '#58a6ff', fontSize: 12, fontWeight: 500 }}>{tag}</span>
                      ))}
                    </div>
                  </div>
                </AbsoluteFill>
              );
            })()
          ) : (
            // Fallback: project description card
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', padding: '0 160px' }}>
              <div style={{
                background: 'linear-gradient(135deg, #161b22 0%, #0d1117 100%)',
                borderRadius: 20, padding: '56px 64px',
                border: '1px solid #30363d',
                boxShadow: '0 12px 48px rgba(0,0,0,0.4)',
                maxWidth: 1200, width: '100%', textAlign: 'center',
                opacity: interpolate(frame, [S[4].start + 3, S[4].start + 20], [0, 1], { extrapolateRight: 'clamp' }),
                transform: `translateY(${interpolate(spring({ frame: frame - S[4].start, fps, config: { damping: 12, stiffness: 70 } }), [0, 1], [40, 0])}px)`,
              }}>
                <div style={{ color: '#58a6ff', fontSize: 14, fontWeight: 600, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 16 }}>
                  What This Project Can Do
                </div>
                <div style={{ color: '#f0f6fc', fontSize: 36, fontWeight: 700, marginBottom: 16 }}>
                  {displayName}
                </div>
                <div style={{ color: '#8b949e', fontSize: 20, lineHeight: 1.7, maxWidth: 900, margin: '0 auto' }}>
                  {description || `An innovative ${language} project — check it out on GitHub to learn more.`}
                </div>
                <div style={{ display: 'flex', gap: 14, justifyContent: 'center', marginTop: 24, flexWrap: 'wrap' }}>
                  {[language, 'Open Source', 'GitHub Trending'].filter(Boolean).map((tag) => (
                    <span key={tag} style={{ padding: '6px 18px', borderRadius: 24, background: 'rgba(88,166,255,0.1)', color: '#58a6ff', fontSize: 14, fontWeight: 500, border: '1px solid rgba(88,166,255,0.2)' }}>{tag}</span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </AbsoluteFill>

        {/* ===== S6: OUTRO — modern frontend aesthetic ===== */}
        <AbsoluteFill style={{
          ...sceneStyle(5), justifyContent: 'center', alignItems: 'center',
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
              letterSpacing: '0.04em', fontFamily: fontFamily,
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
