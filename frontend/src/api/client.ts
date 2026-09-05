// Typed API Client Foundation for GeM Procurement Verification Engine

import {
  HealthResponse,
  AggregatedVerification,
  VerificationDossier,
  HumanReviewItem,
} from "../types";

export class ApiError extends Error {
  public status: number;
  public detail?: string | null;

  constructor(status: number, message: string, detail?: string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
    });

    if (!response.ok) {
      let errorMsg = `HTTP Error ${response.status}: ${response.statusText}`;
      let detail: string | null = null;
      try {
        const errorJson = await response.json();
        if (errorJson && (errorJson.error || errorJson.detail)) {
          errorMsg = errorJson.error || errorJson.detail;
          detail = errorJson.detail || null;
        }
      } catch {
        // Fallback to text status
      }
      throw new ApiError(response.status, errorMsg, detail);
    }

    return (await response.json()) as T;
  } catch (err: any) {
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(0, err.message || "Failed to communicate with verification backend.");
  }
}

export const apiClient = {
  /**
   * Health Check
   */
  async getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },

  /**
   * Retrieves full aggregated verification by ID
   */
  async getVerification(verificationId: string): Promise<AggregatedVerification> {
    return request<AggregatedVerification>(`/api/v1/verification/${encodeURIComponent(verificationId)}`);
  },

  /**
   * Retrieves complete machine-readable verification dossier by ID
   */
  async getDossier(verificationId: string): Promise<VerificationDossier> {
    return request<VerificationDossier>(`/api/v1/verification/${encodeURIComponent(verificationId)}/dossier`);
  },

  /**
   * Retrieves human review queue items for a verification
   */
  async getReviewItems(verificationId: string): Promise<HumanReviewItem[]> {
    return request<HumanReviewItem[]>(`/api/v1/verification/${encodeURIComponent(verificationId)}/review-items`);
  },

  /**
   * Executes verification on uploaded tender & bid documents
   */
  async verifyBid(formData: FormData): Promise<AggregatedVerification> {
    return request<AggregatedVerification>("/api/v1/verify", {
      method: "POST",
      body: formData,
    });
  },
};
