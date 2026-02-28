export type FeatureModelItemFixture = {
  id: string;
  type: "embedding" | "reranker";
  name: string;
  source: "preset" | "custom";
  downloaded: boolean;
  downloadStatus: "downloaded" | "missing";
  localPath: string;
  downloadUrl: string;
  repoId: string;
  selectValue: string;
  selected: boolean;
};

export type FeatureTaskResultFixture = {
  status: string;
  processedVideos: number;
  selectedTerms: number;
  taggedVideos: number;
  createdRelations: number;
  pendingCandidateTerms: number;
  fallbackReason: string;
  topTerms: string[];
};

export type FeatureTaskSnapshotFixture = {
  status: "idle" | "running" | "stopping" | "completed" | "cancelled" | "failed";
  phase: string;
  message: string;
  progressPercent: number;
  current: number;
  total: number;
  strategy: "auto" | "rule" | "model";
  scope: "all" | "new_only";
  embeddingModel: string;
  rerankerModel: string;
  minDf: number;
  maxTagsPerVideo: number;
  maxTerms: number;
  recallTopK: number;
  recallMinScore: number;
  autoApply: number;
  pendingReview: number;
  dependencyStatus: string;
  dependencyMessage: string;
  runningLockModelSwitch: boolean;
  result: FeatureTaskResultFixture;
};

export type FeatureExtractionFixture = {
  modelRoot: string;
  models: FeatureModelItemFixture[];
  task: FeatureTaskSnapshotFixture;
};

const fixture: FeatureExtractionFixture = {
  modelRoot: "E:/Models/FeatureExtraction",
  models: [
    {
      id: "embedding:bge-small-zh-v1.5",
      type: "embedding",
      name: "bge-small-zh-v1.5",
      source: "preset",
      downloaded: true,
      downloadStatus: "downloaded",
      localPath: "E:/Models/FeatureExtraction/bge-small-zh-v1.5",
      downloadUrl: "https://huggingface.co/BAAI/bge-small-zh-v1.5",
      repoId: "BAAI/bge-small-zh-v1.5",
      selectValue: "E:/Models/FeatureExtraction/bge-small-zh-v1.5",
      selected: true,
    },
    {
      id: "embedding:bge-m3",
      type: "embedding",
      name: "bge-m3",
      source: "preset",
      downloaded: false,
      downloadStatus: "missing",
      localPath: "",
      downloadUrl: "https://huggingface.co/BAAI/bge-m3",
      repoId: "BAAI/bge-m3",
      selectValue: "bge-m3",
      selected: false,
    },
    {
      id: "reranker:bge-reranker-large",
      type: "reranker",
      name: "bge-reranker-large",
      source: "preset",
      downloaded: true,
      downloadStatus: "downloaded",
      localPath: "E:/Models/FeatureExtraction/bge-reranker-large",
      downloadUrl: "https://huggingface.co/BAAI/bge-reranker-large",
      repoId: "BAAI/bge-reranker-large",
      selectValue: "E:/Models/FeatureExtraction/bge-reranker-large",
      selected: true,
    },
    {
      id: "reranker:mylab-reranker-v1",
      type: "reranker",
      name: "mylab-reranker-v1",
      source: "custom",
      downloaded: true,
      downloadStatus: "downloaded",
      localPath: "E:/Models/FeatureExtraction/custom/mylab-reranker-v1",
      downloadUrl: "",
      repoId: "",
      selectValue: "E:/Models/FeatureExtraction/custom/mylab-reranker-v1",
      selected: false,
    },
  ],
  task: {
    status: "running",
    phase: "model_loading",
    message: "正在检查模型与依赖...",
    progressPercent: 47,
    current: 47,
    total: 100,
    strategy: "auto",
    scope: "new_only",
    embeddingModel: "E:/Models/FeatureExtraction/bge-small-zh-v1.5",
    rerankerModel: "E:/Models/FeatureExtraction/bge-reranker-large",
    minDf: 2,
    maxTagsPerVideo: 8,
    maxTerms: 400,
    recallTopK: 12,
    recallMinScore: 0.45,
    autoApply: 0.8,
    pendingReview: 0.6,
    dependencyStatus: "normal",
    dependencyMessage: "依赖加载正常",
    runningLockModelSwitch: true,
    result: {
      status: "running",
      processedVideos: 124,
      selectedTerms: 318,
      taggedVideos: 92,
      createdRelations: 266,
      pendingCandidateTerms: 41,
      fallbackReason: "embedding 不可用",
      topTerms: ["动作片", "悬疑", "纪录片", "冒险"],
    },
  },
};

export function getFeatureExtractionFixture(): FeatureExtractionFixture {
  return JSON.parse(JSON.stringify(fixture)) as FeatureExtractionFixture;
}
