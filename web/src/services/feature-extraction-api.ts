import type {
  ApiEnvelope,
  ApiFeatureModelsData,
  ApiFeatureTaskData,
  ApiFeatureThresholdsData,
} from "../types/api";
import { requestApi } from "./http";

export type FeatureExtractionStartPayload = {
  strategy: "auto" | "rule" | "model";
  scope: "all" | "new_only";
  embedding_model: string;
  reranker_model: string;
  min_df: number;
  max_tags_per_video: number;
  max_terms: number;
  recall_top_k: number;
  recall_min_score: number;
  auto_apply: number;
  pending_review: number;
};

export function getFeatureTaskStatus(): Promise<ApiEnvelope<ApiFeatureTaskData>> {
  return requestApi<ApiFeatureTaskData>("/feature-extraction/status");
}

export function startFeatureExtraction(
  payload: FeatureExtractionStartPayload,
): Promise<ApiEnvelope<{ status: string; task: ApiFeatureTaskData }>> {
  return requestApi<{ status: string; task: ApiFeatureTaskData }>("/feature-extraction/start", {
    method: "POST",
    body: payload,
  });
}

export function stopFeatureExtraction(): Promise<ApiEnvelope<{ status: string }>> {
  return requestApi<{ status: string }>("/feature-extraction/stop", {
    method: "POST",
    body: {},
  });
}

export function getFeatureModels(): Promise<ApiEnvelope<ApiFeatureModelsData>> {
  return requestApi<ApiFeatureModelsData>("/feature-extraction/models");
}

export function selectFeatureModelRoot(path: string): Promise<ApiEnvelope<ApiFeatureModelsData>> {
  return requestApi<ApiFeatureModelsData>("/feature-extraction/models/select-root", {
    method: "POST",
    body: { path },
  });
}

export function importFeatureModelDirectory(path: string): Promise<ApiEnvelope<ApiFeatureModelsData>> {
  return requestApi<ApiFeatureModelsData>("/feature-extraction/models/import-directory", {
    method: "POST",
    body: { path },
  });
}

export function openFeatureModelPath(path: string): Promise<ApiEnvelope<{ status: string; path: string }>> {
  return requestApi<{ status: string; path: string }>("/feature-extraction/models/open-path", {
    method: "POST",
    body: { path },
  });
}

export function getFeatureThresholds(): Promise<ApiEnvelope<ApiFeatureThresholdsData>> {
  return requestApi<ApiFeatureThresholdsData>("/feature-extraction/thresholds");
}
