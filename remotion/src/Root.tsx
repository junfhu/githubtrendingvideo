import { Composition, Still, CalculateMetadataFunction } from 'remotion';
import { z } from 'zod';
import { MainComposition } from './MainComposition';
import { CoverMobile } from './CoverMobile';
import { CoverPC } from './CoverPC';

const FeatureSchema = z.object({
  name: z.string(),
  desc: z.string(),
  icon: z.string(),
});

export const VideoPropsSchema = z.object({
  repo: z.string(),
  name: z.string().optional(),
  totalStars: z.string(),
  weeklyStars: z.string(),
  language: z.string(),
  description: z.string(),
  author: z.string(),
  authorTitle: z.string(),
  features: z.array(FeatureSchema),
  screenshot: z.string(),
  screenshotIntro: z.string().optional(),
  screenshotIntroHeight: z.number().optional(),
  demoImages: z.array(z.string()).optional(),
  starScreenshot: z.string().optional(),
  audio: z.string(),
  narrationTiming: z.record(z.string(), z.number()).optional(),
  sceneDurations: z.record(z.string(), z.number()).optional(),
  sceneAudio: z.record(z.string(), z.string()).optional(),
  durationSeconds: z.number(),
});

const defaultProps: z.infer<typeof VideoPropsSchema> = {
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
  screenshot: '',
  audio: '',
  durationSeconds: 30,
};

const calculateMetadata: CalculateMetadataFunction<
  z.infer<typeof VideoPropsSchema>
> = async ({ props }) => {
  const durationInFrames = Math.ceil(props.durationSeconds * 30) + 15;
  const shortName = (props.name || props.repo.split('/').pop() || 'video');
  return {
    durationInFrames,
    defaultOutName: `${shortName}-promo`,
  };
};

export const CoverPropsSchema = z.object({
  repo: z.string(),
  name: z.string().optional(),
  totalStars: z.string(),
  weeklyStars: z.string(),
  language: z.string(),
  description: z.string(),
  screenshot: z.string().optional(),
});

export const RemotionRoot = () => {
  return (
    <>
      <Composition
        id="MainComposition"
        component={MainComposition}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={defaultProps}
        schema={VideoPropsSchema}
        calculateMetadata={calculateMetadata}
      />
      <Still
        id="CoverMobile"
        component={CoverMobile}
        width={1080}
        height={1440}
        defaultProps={{
          repo: 'owner/repo',
          totalStars: '0',
          weeklyStars: '0',
          language: 'TypeScript',
          description: 'Select a project in the dashboard',
        }}
        schema={CoverPropsSchema}
      />
      <Still
        id="CoverPC"
        component={CoverPC}
        width={1440}
        height={1080}
        defaultProps={{
          repo: 'owner/repo',
          totalStars: '0',
          weeklyStars: '0',
          language: 'TypeScript',
          description: 'Select a project in the dashboard',
        }}
        schema={CoverPropsSchema}
      />
    </>
  );
};
