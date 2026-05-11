import {
  AbsoluteFill,
  Img,
  staticFile,
  getInputProps,
} from 'remotion';
import { loadFont } from '@remotion/google-fonts/NotoSansSC';

const { fontFamily } = loadFont('normal', { weights: ['400', '700', '900'], ignoreTooManyRequestsWarning: true });

interface CoverProps {
  repo: string;
  name?: string;
  totalStars: string;
  weeklyStars: string;
  language: string;
  description: string;
  screenshot?: string;
}

export const CoverMobile = () => {
  const props = getInputProps() as unknown as CoverProps;

  const repo = props.repo || 'owner/repo';
  const displayName = props.name || repo.split('/').pop() || repo;
  const totalStars = props.totalStars || '0';
  const weeklyStars = props.weeklyStars || '0';
  const hasWeeklyStars = weeklyStars && weeklyStars !== '?' && weeklyStars !== '0';
  const language = props.language || 'Unknown';
  const description = props.description || '';
  const screenshotSrc = props.screenshot ? staticFile(props.screenshot) : '';

  const starsNum = Number(totalStars.replace(/,/g, ''));
  const starsDisplay = starsNum >= 1000
    ? (starsNum / 1000).toFixed(1).replace(/\.0$/, '') + 'k'
    : starsNum.toLocaleString();

  // Truncate long project names for the cover title
  const titleText = displayName.length > 20
    ? displayName.slice(0, 18) + '…'
    : displayName;

  return (
    <AbsoluteFill style={{ backgroundColor: '#0f0f23', fontFamily }}>
      {/* ═══ HERO LAYER: Screenshot fills the canvas ═══ */}
      {screenshotSrc ? (
        <AbsoluteFill>
          <Img
            src={screenshotSrc}
            style={{
              width: '100%', height: '100%',
              objectFit: 'cover',
              objectPosition: 'center top',
            }}
          />
        </AbsoluteFill>
      ) : (
        /* Fallback: vibrant gradient when no screenshot */
        <AbsoluteFill style={{
          background: `
            linear-gradient(160deg, #1a1a3e 0%, #2d1b69 30%, #4a0e4e 60%, #1a1a3e 100%)
          `,
        }}>
          {/* Animated glow spots */}
          <div style={{
            position: 'absolute',
            top: '20%', left: '30%',
            width: 300, height: 300, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(120,100,255,0.4) 0%, transparent 70%)',
          }} />
          <div style={{
            position: 'absolute',
            bottom: '30%', right: '20%',
            width: 250, height: 250, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(255,150,50,0.3) 0%, transparent 70%)',
          }} />
        </AbsoluteFill>
      )}

      {/* ═══ GRADIENT OVERLAY: ensures text readability ═══ */}
      <AbsoluteFill style={{
        background: `
          linear-gradient(0deg, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.25) 40%, rgba(0,0,0,0.05) 70%, rgba(0,0,0,0.2) 100%)
        `,
      }} />

      {/* ═══ TOP ZONE (top 15%): subtle badge ═══ */}
      <div style={{
        position: 'absolute', top: 30, right: 30, zIndex: 1,
        background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(8px)',
        borderRadius: 16, padding: '6px 18px',
        border: '1px solid rgba(255,255,255,0.1)',
      }}>
        <span style={{
          color: 'rgba(255,255,255,0.7)', fontSize: 11,
          fontWeight: 600, letterSpacing: 2,
        }}>
          🔥 TRENDING
        </span>
      </div>

      {/* ═══ BOTTOM ZONE (bottom 30%): text overlay ═══ */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 1,
        padding: '40px 36px 32px',
        display: 'flex', flexDirection: 'column', gap: 14,
      }}>
        {/* Title — large, bold, white with shadow for readability */}
        <div style={{
          color: '#ffffff',
          fontSize: 72,
          fontWeight: 900,
          lineHeight: 1.1,
          letterSpacing: '-0.02em',
          textShadow: '0 2px 8px rgba(0,0,0,0.6), 0 0 30px rgba(0,0,0,0.4)',
          maxWidth: '100%',
        }}>
          {titleText}
        </div>

        {/* Description — one punchy line */}
        {description && (
          <div style={{
            color: 'rgba(255,255,255,0.85)',
            fontSize: 20,
            lineHeight: 1.3,
            textShadow: '0 1px 4px rgba(0,0,0,0.5)',
            maxWidth: '90%',
          }}>
            {description.length > 40 ? description.slice(0, 38) + '…' : description}
          </div>
        )}

        {/* Bottom row: stars + tag */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 16,
        }}>
          {/* Star badge */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(8px)',
            borderRadius: 12, padding: '8px 16px',
            border: '1px solid rgba(240,192,64,0.3)',
          }}>
            <span style={{ fontSize: 16 }}>⭐</span>
            <span style={{
              color: '#f0c040', fontSize: 22, fontWeight: 900,
              textShadow: '0 1px 4px rgba(0,0,0,0.5)',
            }}>
              {starsDisplay}
            </span>
          </div>

          {/* Weekly stars */}
          {hasWeeklyStars && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 4,
              background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(8px)',
              borderRadius: 12, padding: '8px 16px',
              border: '1px solid rgba(255,107,53,0.3)',
            }}>
              <span style={{ fontSize: 14 }}>🔥</span>
              <span style={{
                color: '#ff6b35', fontSize: 22, fontWeight: 900,
                textShadow: '0 1px 4px rgba(0,0,0,0.5)',
              }}>
                +{weeklyStars}
              </span>
            </div>
          )}

          {/* Language pill */}
          {language && language !== 'Unknown' && (
            <div style={{
              background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(8px)',
              borderRadius: 12, padding: '8px 16px',
              border: '1px solid rgba(255,255,255,0.15)',
            }}>
              <span style={{
                color: 'rgba(255,255,255,0.75)', fontSize: 16, fontWeight: 600,
              }}>
                {language}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ═══ WATERMARK — bottom-right ═══ */}
      <div style={{
        position: 'absolute', bottom: 28, right: 28, zIndex: 2,
      }}>
        <span style={{
          color: 'rgba(255,255,255,0.2)', fontSize: 11, letterSpacing: 4,
        }}>
          @慕涯
        </span>
      </div>
    </AbsoluteFill>
  );
};
