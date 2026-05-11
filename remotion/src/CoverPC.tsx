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

export const CoverPC = () => {
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

  return (
    <AbsoluteFill style={{ backgroundColor: '#0a0e14', fontFamily }}>
      {/* Background glow */}
      <div style={{
        position: 'absolute', inset: 0,
        background: `
          radial-gradient(ellipse 50% 70% at 20% 50%, rgba(88,166,255,0.14) 0%, transparent 60%),
          radial-gradient(ellipse 50% 60% at 75% 40%, rgba(102,126,234,0.08) 0%, transparent 50%)
        `,
      }} />

      {/* Split layout: text left + visual right */}
      <div style={{
        position: 'relative', zIndex: 1,
        display: 'flex', height: '100%',
      }}>
        {/* ── LEFT: Text (50%) ── */}
        <div style={{
          flex: '0 0 50%',
          display: 'flex', flexDirection: 'column',
          justifyContent: 'center',
          padding: '56px 36px 56px 52px',
        }}>
          {/* Badge */}
          <div style={{
            alignSelf: 'flex-start',
            background: 'linear-gradient(135deg, rgba(102,126,234,0.2), rgba(118,75,162,0.2))',
            border: '1px solid rgba(102,126,234,0.25)',
            borderRadius: 16, padding: '5px 16px', marginBottom: 14,
          }}>
            <span style={{ color: '#a5b4fc', fontSize: 12, fontWeight: 600, letterSpacing: 2 }}>
              🔥 GITHUB TRENDING
            </span>
          </div>

          {/* Project name */}
          <div style={{
            color: '#f0f6fc', fontSize: 54, fontWeight: 900,
            lineHeight: 1.12, letterSpacing: '-0.02em',
            marginBottom: 10,
          }}>
            {displayName.length > 22 ? displayName.slice(0, 20) + '…' : displayName}
          </div>

          {/* Description */}
          {description && (
            <div style={{
              color: '#8b949e', fontSize: 17, lineHeight: 1.4,
              marginBottom: 18,
            }}>
              {description.length > 55 ? description.slice(0, 53) + '…' : description}
            </div>
          )}

          {/* Star cards */}
          <div style={{
            display: 'flex', gap: 12, marginBottom: 18, alignSelf: 'flex-start',
          }}>
            <div style={{
              background: 'rgba(22,27,34,0.9)', borderRadius: 12,
              padding: '14px 26px',
              border: '1px solid rgba(240,192,64,0.3)',
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', gap: 2,
            }}>
              <span style={{ color: '#f0c040', fontSize: 11, fontWeight: 700, letterSpacing: 2 }}>
                ⭐ STARS
              </span>
              <span style={{ color: '#ffffff', fontSize: 36, fontWeight: 900, lineHeight: 1 }}>
                {starsDisplay}
              </span>
            </div>
            {hasWeeklyStars && (
              <div style={{
                background: 'rgba(22,27,34,0.9)', borderRadius: 12,
                padding: '14px 26px',
                border: '1px solid rgba(255,107,53,0.3)',
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', gap: 2,
              }}>
                <span style={{ color: '#ff6b35', fontSize: 11, fontWeight: 700, letterSpacing: 2 }}>
                  🔥 WEEKLY
                </span>
                <span style={{ color: '#ffffff', fontSize: 36, fontWeight: 900, lineHeight: 1 }}>
                  +{weeklyStars}
                </span>
              </div>
            )}
          </div>

          {/* Tags */}
          <div style={{
            display: 'flex', gap: 8, flexWrap: 'wrap', alignSelf: 'flex-start',
          }}>
            {[language, 'Open Source'].filter(Boolean).map((tag) => (
              <span key={tag} style={{
                padding: '4px 13px', borderRadius: 13,
                background: 'rgba(88,166,255,0.08)',
                color: '#58a6ff', fontSize: 12, fontWeight: 500,
                border: '1px solid rgba(88,166,255,0.15)',
              }}>{tag}</span>
            ))}
          </div>
        </div>

        {/* ── RIGHT: Screenshot visual (50%) ── */}
        <div style={{
          flex: 1,
          position: 'relative',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {screenshotSrc ? (
            <div style={{
              width: '88%', height: '72%',
              borderRadius: 14, overflow: 'hidden',
              boxShadow: '0 6px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(88,166,255,0.15)',
            }}>
              <Img src={screenshotSrc} style={{
                width: '100%', height: '100%',
                objectFit: 'cover',
              }} />
              <div style={{
                position: 'absolute', inset: 0,
                background: 'linear-gradient(135deg, rgba(13,17,23,0.2) 0%, transparent 40%)',
              }} />
            </div>
          ) : (
            <div style={{
              width: '88%', height: '72%',
              borderRadius: 14,
              background: `
                radial-gradient(circle at 30% 30%, rgba(88,166,255,0.12) 0%, transparent 50%),
                radial-gradient(circle at 70% 70%, rgba(240,192,64,0.08) 0%, transparent 50%)
              `,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <span style={{
                color: 'rgba(88,166,255,0.35)', fontSize: 80,
                fontWeight: 900, fontFamily: 'monospace',
              }}>
                &lt;/&gt;
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Watermark */}
      <div style={{
        position: 'absolute', bottom: 24, right: 32, zIndex: 2,
      }}>
        <span style={{ color: 'rgba(255,255,255,0.12)', fontSize: 11, letterSpacing: 6 }}>
          @慕涯
        </span>
      </div>
    </AbsoluteFill>
  );
};
