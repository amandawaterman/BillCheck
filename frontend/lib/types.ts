export interface LineItem {
  id: string;
  code?: string;
  description: string;
  quantity: number;
  amount: number;
  confidence?: "high" | "medium" | "low";
  isUserEdited?: boolean;
}

export interface ExtractionResult {
  lineItems: LineItem[];
  statistics: {
    totalItems: number;
    comparableItems: number;
    totalCharges: number;
  };
  rawText?: string;
}

export interface Hospital {
  id: string;
  name: string;
  address: string;
  city: string;
  state: string;
  zipCode: string;
  latitude: number;
  longitude: number;
  cmsProviderId: string;
}

export interface HospitalPostedPrice {
  grossCharge?: number;
  discountedCashPrice?: number;
  priceUsed: number;
  priceType: "gross" | "cash" | "negotiated";
}

export interface LocalComparison {
  min: number;
  max: number;
  median: number;
  percentile: number;
  hospitalCount: number;
}

export interface Interpretation {
  severity: "low" | "medium" | "high";
  explanation: string;
}

export interface Provenance {
  sourceFile: string;
  sourceDate: string;
  confidenceLevel: "high" | "medium" | "low";
  radiusMiles: number;
}

export interface ComparisonResult {
  lineItemId: string;
  userCharge: number;
  hospitalPostedPrice?: HospitalPostedPrice;
  localComparison: LocalComparison;
  interpretation: Interpretation;
  provenance: Provenance;
}

export interface BillSummary {
  totalCharged: number;
  totalComparable: number;
  overallPercentile: number;
  interpretation: string;
  recommendations: string[];
}
