export type Provider = {
  id: string;
  name: string;
  slug: string;
  website_url?: string;
  official_domain?: string;
  aliases?: string[];
  oauth_support_status?: "supported" | "unsupported" | "unknown";
};
export type Workspace = {
  id: string;
  title: string;
  provider: Provider;
  use_case: string;
  status: string;
  main_thread_id: string;
  guide_available: boolean;
  guide_is_stale?: boolean;
  research_needed: boolean;
  resolution_status: string;
  progress?: number | { completed: number; total: number };
  active_guide_version_id?: string;
};
export type Source = {
  id: string;
  title: string;
  url: string;
  retrieved_at?: string;
  claims?: string[];
  excerpt?: string;
  text_fragment_url?: string;
  excerpt_verified?: boolean;
  step_text_fragment_urls?: Record<string, string>;
};
export type ClaimCitation = {
  field: string;
  index?: number | null;
  source_ids: string[];
  scope?: "claim" | "step";
};
export type Step = {
  id: string;
  stable_key: string;
  title: string;
  description: string;
  why_it_matters?: string;
  instructions: string[];
  status: string;
  actor: string;
  source_ids: string[];
  citations?: ClaimCitation[];
  warnings: string[];
  action_url?: string;
  estimated_minutes?: number | null;
  verification_status?: string;
  notes?: { id: string; content: string }[];
};
export type Guide = {
  id: string;
  version_number: number;
  provider: Provider;
  oauth_support_status?: "supported" | "unsupported" | "unknown";
  clarification_needed?: boolean;
  clarification_questions?: string[];
  summary: string;
  recommended_auth_path: string;
  difficulty: string;
  estimated_setup_minutes: number | null;
  estimated_approval_days: number | null;
  approval_requirement: string;
  approval_confidence: string;
  prerequisites: string[];
  blockers: (
    | string
    | {
        description: string;
        impact?: string;
        resolution?: string;
        human_required?: boolean;
        source_ids?: string[];
      }
  )[];
  sources: Source[];
  steps: Step[];
  citations?: ClaimCitation[];
  conversation_anchor_message_id?: string | null;
  clarification_message_id?: string | null;
  next_best_action: string;
  share_slug: string;
  last_verified_at?: string;
  guide_is_stale?: boolean;
  freshness_days?: number;
  setup_confidence?: string;
  assumptions?: string[];
  approval_materials?: string[];
  while_waiting?: string[];
  uncertainties?: string[];
};
export type Thread = {
  id: string;
  type: "main" | "step";
  step_id?: string;
  step_stable_key?: string;
  parent_thread_id?: string;
  title: string;
  guide_version_id?: string;
};
export type Message = {
  id: string;
  role: string;
  content: string;
  citations?: unknown[];
  status?: string;
  created_at?: string;
};
export type StreamEvent = { event: string; data: Record<string, unknown> };
