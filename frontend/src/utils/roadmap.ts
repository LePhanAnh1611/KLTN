import type { RoadmapStage } from '../api/roadmap';

const LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

/** Infer skipped levels even when an older API omits is_skipped. */
export function splitRoadmapStages(stages: RoadmapStage[], entryLevel: string) {
  const entryRank = LEVELS.indexOf(entryLevel);
  const normalized = stages.map((stage) => {
    const rank = LEVELS.indexOf(stage.cefr_level);
    return {
      ...stage,
      is_skipped: entryRank >= 0 && rank >= 0
        ? rank < entryRank : Boolean(stage.is_skipped),
    };
  });
  return {
    skippedStages: normalized.filter((stage) => stage.is_skipped),
    personalStages: normalized.filter((stage) => !stage.is_skipped),
  };
}
