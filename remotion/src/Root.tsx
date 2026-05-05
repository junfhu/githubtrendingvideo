import { Composition, getInputProps } from 'remotion';
import { MainComposition } from './MainComposition';

const defaultProps = {
  repo: 'owner/repo',
  name: 'project',
  totalStars: '0',
  weeklyStars: '0',
  language: 'TypeScript',
  description: 'Select a project in the dashboard',
  author: 'author',
  authorTitle: 'Developer',
  features: [
    { name: 'feature-1', desc: 'Select a project first', icon: '🚀' },
    { name: 'feature-2', desc: 'Choose from trending list', icon: '⚡' },
    { name: 'feature-3', desc: 'Then generate video', icon: '🔧' },
    { name: 'feature-4', desc: 'Preview and build', icon: '📦' },
    { name: 'feature-5', desc: 'Share your video', icon: '🎯' },
    { name: 'feature-6', desc: 'Enjoy!', icon: '🛡️' },
  ],
  narration: '请先在管理台选择一个项目。',
  narrationTiming: {},
  screenshot: '',
  audio: '',
  durationSeconds: 30,
  sceneDurations: {},
};

export const RemotionRoot = () => {
  const props = getInputProps() as unknown as Record<string, unknown>;
  const durationSec = (props.durationSeconds as number) || defaultProps.durationSeconds;
  const durationInFrames = Math.ceil(durationSec * 30) + 15;

  return (
    <>
      <Composition
        id="MainComposition"
        component={MainComposition}
        durationInFrames={durationInFrames}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={defaultProps}
      />
    </>
  );
};
