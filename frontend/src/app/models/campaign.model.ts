export interface ProofDocument {
  doc_type: string;
  title: string;
  file_url: string;
  verified: boolean;
}

export interface DimensionScores {
  specificity_score: number;
  benchmark_score: number;
  documentation_score: number;
  urgency_score: number;
  // legacy aliases
  plausibility?: number;
  specificity?: number;
  red_flag_score?: number;
  documentation?: number;
}

export interface Campaign {
  id: number;
  creator_id?: number;
  title: string;
  subtitle?: string;
  short_description: string;
  category: string;
  story: string;
  goal_amount: number;
  current_amount: number;
  currency: string;
  donor_count: number;
  percent_funded?: number;
  cover_image_url?: string;
  country?: string;
  state?: string;
  city?: string;
  postal_code?: string;
  beneficiary_type?: string;
  beneficiary_name?: string;
  relationship_to_beneficiary?: string;
  hospital_name?: string;
  hospital_patient_uhid?: string;
  is_80g_tax_exempt: boolean;
  direct_hospital_transfer: boolean;
  organizer_name?: string;
  organizer_phone?: string;
  status: string;
  proof_documents?: ProofDocument[];
  // AI verification
  ai_trust_score?: number;
  ai_dimension_scores?: DimensionScores;
  ai_red_flags?: string[];
  ai_recommendation?: string;
  ai_verified_at?: string;
  // Legacy field aliases (backend may use these)
  authenticity_score?: number;
  risk_level?: string;
  // Relations
  updates?: CampaignUpdate[];
  created_at?: string;
  updated_at?: string;
  deadline?: string;
}

export interface CampaignUpdate {
  id: number;
  campaign_id: number;
  content: string;
  created_at: string;
}

export interface CampaignListResponse {
  campaigns: Campaign[];
  total: number;
  page: number;
  limit: number;
  // Legacy alias
  items?: Campaign[];
}

export interface BenchmarkComparison {
  category: string;
  item_detected?: string;
  requested_amount: number;
  typical_range_min: number;
  typical_range_max: number;
  currency: string;
  ratio_to_benchmark: number;
  benchmark_status: string;
  insight: string;
}

export interface VerificationResult {
  overall_score: number;
  decision: string;
  explanation: string;
  dimension_scores: DimensionScores;
  red_flags?: string[];
  suggestions?: string[];
  // Legacy fields
  authenticity_score?: number;
  risk_level?: string;
  recommendation?: string;
  summary?: string;
  cost_benchmark?: BenchmarkComparison;
  positive_signals?: string[];
  missing_requirements?: string[];
  confidence?: number;
  model_used?: string;
}

export interface StoryEnhanceResponse {
  enhanced_story: string;
  suggested_title?: string;
  suggested_subtitle?: string;
  // Legacy fields
  structured_story?: string;
  recommended_itemized_breakdown?: Array<{
    item: string;
    estimated_amount: number;
    currency: string;
  }>;
  transparency_tips?: string[];
  suggested_tags?: string[];
}

export interface DonationReceipt {
  transaction_id?: string;
  transaction_ref?: string;
  campaign_id: number;
  campaign_title?: string;
  donor_name?: string;
  amount?: number;
  amount_received?: number;
  gateway_fee?: number;
  tip_amount?: number;
  total_charged?: number;
  currency?: string;
  payment_method?: string;
  tax_exemption_80g_eligible?: boolean;
  tax_exemption_80g_number?: string;
  gateway_order_id?: string;
  gateway_payment_id?: string;
  timestamp?: string;
  receipt_message?: string;
}

export interface CreateGatewayOrderResponse {
  order_id: string;
  amount: number;
  currency: string;
  key_id: string;
  campaign_id: number;
  campaign_title: string;
  beneficiary_name?: string;
}

export interface AdminDonationItem {
  id: number;
  campaign_id: number;
  campaign_title: string;
  beneficiary_name?: string;
  beneficiary_type?: string;
  hospital_name?: string;
  donor_id?: number;
  donor_name: string;
  is_anonymous: boolean;
  donor_email?: string;
  donor_phone?: string;
  donor_pan?: string;
  amount: number;
  tip_amount: number;
  fee_amount: number;
  net_amount: number;
  currency: string;
  payment_method: string;
  upi_id?: string;
  tax_exemption_80g_number?: string;
  support_message?: string;
  payment_status: string;
  transaction_ref?: string;
  gateway_order_id?: string;
  gateway_payment_id?: string;
  created_at: string;
}

export interface AdminDonationsSummary {
  total_donations_count: number;
  total_amount_raised: number;
  total_net_amount: number;
  total_fee_amount: number;
  average_donation: number;
}

export interface AdminDonationsResponse {
  items: AdminDonationItem[];
  total: number;
  page: number;
  limit: number;
  summary: AdminDonationsSummary;
}
