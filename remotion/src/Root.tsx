import { Composition } from 'remotion';
import { MainComposition } from './MainComposition';

const defaultProps = {
  repo: 'mattpocock/skills',
  totalStars: '57,273',
  weeklyStars: '34,848',
  language: 'Shell',
  description: 'Skills for Real Engineers — straight from the .claude directory of TypeScript educator Matt Pocock',
  author: 'Matt Pocock',
  authorTitle: 'TypeScript Educator · Author · DevTools Builder',
  features: [
    { name: '/grill-me', desc: 'Align agent with your intent before coding starts', icon: '🎯' },
    { name: '/tdd', desc: 'Test-driven development — red, green, refactor loop', icon: '🧪' },
    { name: '/diagnose', desc: 'Structured debugging: reproduce, minimise, fix', icon: '🔍' },
    { name: '/triage', desc: 'State-machine-based issue triage with labels', icon: '🏷️' },
    { name: '/to-prd', desc: 'Convert context into PRDs and vertical-slice issues', icon: '📋' },
    { name: '/zoom-out', desc: 'High-level context on unfamiliar code sections', icon: '🔭' },
  ],
  screenshot: 'clean.png',
  audio: 'narration.wav',
};

export const RemotionRoot = () => {
  return (
    <>
      <Composition
        id="MainComposition"
        component={MainComposition}
        durationInFrames={930}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={defaultProps}
      />
    </>
  );
};
