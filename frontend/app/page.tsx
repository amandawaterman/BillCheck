"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { Upload, Search, Building2, ArrowLeft, CheckCircle, AlertTriangle, XCircle, HelpCircle } from "lucide-react";

// Types
interface LineItem {
  code?: string;
  description: string;
  quantity: number;
  amount: number;
}

interface Hospital {
  id: string;
  name: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  type: string;
}

interface RegionalStats {
  min: number;
  max: number;
  median: number;
  average: number;
  count: number;
}

interface PriceComparison {
  hospital_name: string;
  gross_charge: number;
  negotiated_rate: number;
}

interface CMSData {
  medicare_avg_payment?: number;
  medicare_min_payment?: number;
  medicare_max_payment?: number;
  avg_submitted_charge?: number;
  facility_avg_payment?: number;
  data_source?: string;
  description?: string;
}

interface LineItemComparison {
  code?: string;
  description: string;
  billed_amount: number;
  quantity: number;
  cms_data?: CMSData;
  cms_description?: string;
  hospital_gross_charge?: number;
  hospital_negotiated_rate?: number;
  regional_stats?: RegionalStats;
  status: string;
  variance_percent?: number;
  potential_savings?: number;
  other_hospitals: PriceComparison[];
}

interface CompareResponse {
  hospital_name: string;
  hospital_id: string;
  total_billed: number;
  total_fair_value?: number;
  total_potential_savings?: number;
  overall_assessment: string;
  line_items: LineItemComparison[];
  data_sources: string[];
}

interface DetectedHospital {
  hospital_id?: string;
  hospital_name?: string;
  confidence: string;
  detected_name?: string;
}

interface ExtractResponse {
  line_items: LineItem[];
  detected_hospital?: DetectedHospital;
}

type Step = "upload" | "review" | "hospital" | "results";

export default function Home() {
  const [apiStatus, setApiStatus] = useState<"checking" | "connected" | "error">("checking");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [step, setStep] = useState<Step>("upload");

  // Upload state
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Line items state
  const [lineItems, setLineItems] = useState<LineItem[]>([]);

  // Hospital state
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [hospitalSearch, setHospitalSearch] = useState("");
  const [selectedHospital, setSelectedHospital] = useState<Hospital | null>(null);
  const [loadingHospitals, setLoadingHospitals] = useState(false);

  // Comparison state
  const [comparing, setComparing] = useState(false);
  const [comparisonResult, setComparisonResult] = useState<CompareResponse | null>(null);

  // Detected hospital state
  const [detectedHospital, setDetectedHospital] = useState<DetectedHospital | null>(null);

  useEffect(() => {
    const checkApi = async () => {
      try {
        await apiClient.healthCheck();
        setApiStatus("connected");
      } catch (error) {
        setApiStatus("error");
        setErrorMessage(error instanceof Error ? error.message : "Unknown error");
      }
    };
    checkApi();
  }, []);

  // Load hospitals on mount
  useEffect(() => {
    const loadHospitals = async () => {
      try {
        const result = await apiClient.searchHospitals("") as { hospitals: Hospital[] };
        setHospitals(result.hospitals);
      } catch (error) {
        console.error("Failed to load hospitals:", error);
      }
    };
    loadHospitals();
  }, []);

  const handleFile = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setUploadError("Please upload a PDF file");
      return;
    }

    setUploadError(null);
    setUploading(true);

    try {
      const uploadResult = await apiClient.uploadPdf(file) as { file_id: string };
      setUploading(false);
      setExtracting(true);

      const extractResult = await apiClient.extractLineItems(uploadResult.file_id) as ExtractResponse;
      setLineItems(extractResult.line_items);

      // Handle detected hospital
      if (extractResult.detected_hospital) {
        setDetectedHospital(extractResult.detected_hospital);

        // Auto-select hospital if we have a high confidence match
        if (extractResult.detected_hospital.hospital_id && extractResult.detected_hospital.confidence === "high") {
          const matchedHospital = hospitals.find(h => h.id === extractResult.detected_hospital?.hospital_id);
          if (matchedHospital) {
            setSelectedHospital(matchedHospital);
          }
        }
      } else {
        setDetectedHospital(null);
      }

      setStep("review");
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setUploading(false);
      setExtracting(false);
    }
  }, [hospitals]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const searchHospitals = useCallback(async (query: string) => {
    setLoadingHospitals(true);
    try {
      const result = await apiClient.searchHospitals(query) as { hospitals: Hospital[] };
      setHospitals(result.hospitals);
    } catch (error) {
      console.error("Hospital search failed:", error);
    } finally {
      setLoadingHospitals(false);
    }
  }, []);

  const handleCompare = useCallback(async () => {
    if (!selectedHospital) return;

    setComparing(true);
    try {
      const result = await apiClient.compareCharges({
        line_items: lineItems.map(item => ({
          code: item.code,
          description: item.description,
          quantity: item.quantity,
          amount: item.amount,
        })),
        hospital_id: selectedHospital.id,
      }) as CompareResponse;

      setComparisonResult(result);
      setStep("results");
    } catch (error) {
      console.error("Comparison failed:", error);
    } finally {
      setComparing(false);
    }
  }, [selectedHospital, lineItems]);

  const resetAll = () => {
    setStep("upload");
    setLineItems([]);
    setSelectedHospital(null);
    setComparisonResult(null);
    setUploadError(null);
    setDetectedHospital(null);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "low":
      case "fair":
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case "high":
        return <AlertTriangle className="h-5 w-5 text-yellow-500" />;
      case "very_high":
        return <XCircle className="h-5 w-5 text-red-500" />;
      default:
        return <HelpCircle className="h-5 w-5 text-muted-foreground" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "low":
      case "fair":
        return "text-green-600 bg-green-50";
      case "high":
        return "text-yellow-600 bg-yellow-50";
      case "very_high":
        return "text-red-600 bg-red-50";
      default:
        return "text-muted-foreground bg-muted";
    }
  };

  const getAssessmentMessage = (assessment: string) => {
    switch (assessment) {
      case "fair":
        return { text: "Your bill appears to be fairly priced", color: "text-green-600" };
      case "slightly_overcharged":
        return { text: "Some charges are slightly above typical rates", color: "text-yellow-600" };
      case "moderately_overcharged":
        return { text: "Several charges are above typical rates", color: "text-orange-600" };
      case "significantly_overcharged":
        return { text: "Many charges are significantly above typical rates", color: "text-red-600" };
      default:
        return { text: "Unable to assess - limited matching data", color: "text-muted-foreground" };
    }
  };

  return (
    <main className="min-h-screen p-4 md:p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">BillCheck</h1>
          <p className="text-muted-foreground">Hospital Bill Sanity Checker</p>
        </div>

        {/* Progress Steps */}
        <div className="flex justify-center gap-2 mb-8">
          {["upload", "review", "hospital", "results"].map((s, i) => (
            <div key={s} className="flex items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium
                ${step === s ? "bg-primary text-primary-foreground" :
                  ["upload", "review", "hospital", "results"].indexOf(step) > i ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground"}`}>
                {i + 1}
              </div>
              {i < 3 && <div className={`w-8 h-0.5 ${["upload", "review", "hospital", "results"].indexOf(step) > i ? "bg-primary/20" : "bg-muted"}`} />}
            </div>
          ))}
        </div>

        {apiStatus === "error" && (
          <div className="mb-8 p-4 rounded-lg border border-red-300 bg-red-50 text-center">
            <p className="text-red-600 font-semibold">Backend not connected</p>
            <p className="text-sm text-red-500 mt-2">{errorMessage}</p>
          </div>
        )}

        {/* Step 1: Upload */}
        {step === "upload" && (
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors
              ${isDragging ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary/50"}
              ${apiStatus !== "connected" ? "opacity-50 pointer-events-none" : ""}`}
            onClick={() => document.getElementById("file-input")?.click()}
          >
            <input id="file-input" type="file" accept=".pdf" onChange={handleFileInput} className="hidden" />
            {uploading || extracting ? (
              <div>
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4" />
                <p className="text-lg font-medium">{uploading ? "Uploading..." : "Extracting line items..."}</p>
              </div>
            ) : (
              <>
                <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-lg font-medium mb-2">Drop your hospital bill here</p>
                <p className="text-sm text-muted-foreground">or click to browse (PDF only)</p>
              </>
            )}
            {uploadError && <p className="mt-4 text-red-600 text-sm">{uploadError}</p>}
          </div>
        )}

        {/* Step 2: Review Line Items */}
        {step === "review" && (
          <div className="border rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Review Extracted Items</h2>
              <button onClick={resetAll} className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1">
                <ArrowLeft className="h-4 w-4" /> Start over
              </button>
            </div>

            <p className="text-sm text-muted-foreground mb-4">
              We found {lineItems.length} line items. Review them below, then select your hospital to compare prices.
            </p>

            <div className="overflow-x-auto mb-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-2">Code</th>
                    <th className="text-left py-2 px-2">Description</th>
                    <th className="text-right py-2 px-2">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {lineItems.map((item, index) => (
                    <tr key={index} className="border-b last:border-b-0">
                      <td className="py-2 px-2 font-mono text-xs">{item.code || "-"}</td>
                      <td className="py-2 px-2">{item.description}</td>
                      <td className="py-2 px-2 text-right">${item.amount.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="font-semibold">
                    <td colSpan={2} className="py-2 px-2 text-right">Total:</td>
                    <td className="py-2 px-2 text-right">${lineItems.reduce((sum, item) => sum + item.amount, 0).toFixed(2)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>

            <button
              onClick={() => setStep("hospital")}
              className="w-full py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90"
            >
              Continue to Hospital Selection
            </button>
          </div>
        )}

        {/* Step 3: Select Hospital */}
        {step === "hospital" && (
          <div className="border rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Select Your Hospital</h2>
              <button onClick={() => setStep("review")} className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1">
                <ArrowLeft className="h-4 w-4" /> Back
              </button>
            </div>

            {/* Hospital selection notification */}
            {selectedHospital && (
              <div className={`mb-4 p-3 rounded-lg flex items-center gap-2 ${
                detectedHospital?.hospital_id === selectedHospital.id
                  ? "bg-green-50 border border-green-200"
                  : "bg-blue-50 border border-blue-200"
              }`}>
                <CheckCircle className={`h-5 w-5 flex-shrink-0 ${
                  detectedHospital?.hospital_id === selectedHospital.id ? "text-green-600" : "text-blue-600"
                }`} />
                <div className="flex-1">
                  {detectedHospital?.hospital_id === selectedHospital.id ? (
                    <>
                      <p className="text-sm text-green-800">
                        <span className="font-medium">Auto-detected:</span> {selectedHospital.name}
                      </p>
                      <p className="text-xs text-green-600">We found this hospital in your bill. You can change it below if needed.</p>
                    </>
                  ) : (
                    <>
                      <p className="text-sm text-blue-800">
                        <span className="font-medium">Selected:</span> {selectedHospital.name}
                      </p>
                      <p className="text-xs text-blue-600">You can change your selection below if needed.</p>
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Low confidence detection */}
            {detectedHospital && !detectedHospital.hospital_id && detectedHospital.detected_name && (
              <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-yellow-600 flex-shrink-0" />
                <div className="flex-1">
                  <p className="text-sm text-yellow-800">
                    <span className="font-medium">Detected:</span> {detectedHospital.detected_name}
                  </p>
                  <p className="text-xs text-yellow-600">Please select the matching hospital from the list below.</p>
                </div>
              </div>
            )}

            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search hospitals..."
                value={hospitalSearch}
                onChange={(e) => {
                  setHospitalSearch(e.target.value);
                  searchHospitals(e.target.value);
                }}
                className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>

            <div className="space-y-2 max-h-80 overflow-y-auto mb-6">
              {loadingHospitals ? (
                <p className="text-center text-muted-foreground py-4">Loading...</p>
              ) : hospitals.length === 0 ? (
                <p className="text-center text-muted-foreground py-4">No hospitals found</p>
              ) : (
                hospitals.map((hospital) => (
                  <div
                    key={hospital.id}
                    onClick={() => setSelectedHospital(hospital)}
                    className={`p-4 border rounded-lg cursor-pointer transition-colors
                      ${selectedHospital?.id === hospital.id ? "border-primary bg-primary/5" : "hover:bg-muted/50"}`}
                  >
                    <div className="flex items-start gap-3">
                      <Building2 className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="font-medium">{hospital.name}</p>
                        <p className="text-sm text-muted-foreground">{hospital.address}</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            <button
              onClick={handleCompare}
              disabled={!selectedHospital || comparing}
              className="w-full py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {comparing ? "Comparing..." : "Compare Prices"}
            </button>
          </div>
        )}

        {/* Step 4: Results */}
        {step === "results" && comparisonResult && (
          <div className="space-y-6">
            {/* Summary Card */}
            <div className="border rounded-lg p-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h2 className="text-xl font-semibold">Bill Analysis</h2>
                  <p className="text-sm text-muted-foreground">{comparisonResult.hospital_name}</p>
                </div>
                <button onClick={resetAll} className="text-sm text-muted-foreground hover:text-foreground">
                  Analyze another bill
                </button>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">Total Billed</p>
                  <p className="text-2xl font-bold">${comparisonResult.total_billed.toFixed(2)}</p>
                </div>
                {comparisonResult.total_fair_value && (
                  <div className="p-4 bg-muted/50 rounded-lg">
                    <p className="text-sm text-muted-foreground">Fair Value Est.</p>
                    <p className="text-2xl font-bold">${comparisonResult.total_fair_value.toFixed(2)}</p>
                  </div>
                )}
                {comparisonResult.total_potential_savings && comparisonResult.total_potential_savings > 0 && (
                  <div className="p-4 bg-green-50 rounded-lg">
                    <p className="text-sm text-green-600">Potential Savings</p>
                    <p className="text-2xl font-bold text-green-600">${comparisonResult.total_potential_savings.toFixed(2)}</p>
                  </div>
                )}
              </div>

              <div className={`p-4 rounded-lg ${getAssessmentMessage(comparisonResult.overall_assessment).color === "text-green-600" ? "bg-green-50" :
                getAssessmentMessage(comparisonResult.overall_assessment).color === "text-yellow-600" ? "bg-yellow-50" :
                getAssessmentMessage(comparisonResult.overall_assessment).color === "text-orange-600" ? "bg-orange-50" :
                getAssessmentMessage(comparisonResult.overall_assessment).color === "text-red-600" ? "bg-red-50" : "bg-muted"}`}>
                <p className={`font-medium ${getAssessmentMessage(comparisonResult.overall_assessment).color}`}>
                  {getAssessmentMessage(comparisonResult.overall_assessment).text}
                </p>
              </div>

              {/* Data Sources */}
              {comparisonResult.data_sources && comparisonResult.data_sources.length > 0 && (
                <div className="mt-4 pt-4 border-t">
                  <p className="text-xs text-muted-foreground">
                    Data sources: {comparisonResult.data_sources.join(", ")}
                  </p>
                </div>
              )}
            </div>

            {/* Line Item Details */}
            <div className="border rounded-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Line Item Comparison</h3>

              <div className="space-y-4">
                {comparisonResult.line_items.map((item, index) => (
                  <div key={index} className="border rounded-lg p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          {getStatusIcon(item.status)}
                          <span className="font-medium">{item.description}</span>
                          {item.code && <span className="text-xs font-mono text-muted-foreground">({item.code})</span>}
                        </div>
                        {item.cms_description && item.cms_description !== item.description && (
                          <p className="text-sm text-muted-foreground ml-7">{item.cms_description}</p>
                        )}
                      </div>
                      <div className="text-right">
                        <p className="font-semibold">${item.billed_amount.toFixed(2)}</p>
                        {item.variance_percent !== null && item.variance_percent !== undefined && (
                          <span className={`text-xs px-2 py-0.5 rounded ${getStatusColor(item.status)}`}>
                            {item.variance_percent > 0 ? "+" : ""}{item.variance_percent}%
                          </span>
                        )}
                      </div>
                    </div>

                    {/* CMS Medicare Data */}
                    {item.cms_data && (
                      <div className="mt-3 pt-3 border-t">
                        <p className="text-xs text-muted-foreground mb-2">CMS Medicare Data</p>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          {item.cms_data.medicare_avg_payment && (
                            <div>
                              <p className="text-muted-foreground">Medicare Avg</p>
                              <p className="font-medium">${item.cms_data.medicare_avg_payment.toFixed(2)}</p>
                            </div>
                          )}
                          {item.cms_data.facility_avg_payment && (
                            <div>
                              <p className="text-muted-foreground">Facility Avg</p>
                              <p className="font-medium">${item.cms_data.facility_avg_payment.toFixed(2)}</p>
                            </div>
                          )}
                          {item.cms_data.medicare_min_payment && item.cms_data.medicare_max_payment && (
                            <>
                              <div>
                                <p className="text-muted-foreground">Medicare Min</p>
                                <p className="font-medium">${item.cms_data.medicare_min_payment.toFixed(2)}</p>
                              </div>
                              <div>
                                <p className="text-muted-foreground">Medicare Max</p>
                                <p className="font-medium">${item.cms_data.medicare_max_payment.toFixed(2)}</p>
                              </div>
                            </>
                          )}
                        </div>
                        {item.cms_data.description && item.cms_data.description !== item.description && (
                          <p className="text-xs text-muted-foreground mt-2">{item.cms_data.description}</p>
                        )}
                      </div>
                    )}

                    {/* Hospital/Regional Data (fallback) */}
                    {(item.hospital_negotiated_rate || item.regional_stats) && (
                      <div className={`mt-3 pt-3 border-t grid grid-cols-2 md:grid-cols-4 gap-4 text-sm ${item.cms_data ? 'opacity-70' : ''}`}>
                        {item.hospital_negotiated_rate && (
                          <div>
                            <p className="text-muted-foreground">Typical Rate</p>
                            <p className="font-medium">${item.hospital_negotiated_rate.toFixed(2)}</p>
                          </div>
                        )}
                        {item.hospital_gross_charge && (
                          <div>
                            <p className="text-muted-foreground">List Price</p>
                            <p className="font-medium">${item.hospital_gross_charge.toFixed(2)}</p>
                          </div>
                        )}
                        {item.regional_stats && (
                          <>
                            <div>
                              <p className="text-muted-foreground">Regional Low</p>
                              <p className="font-medium">${item.regional_stats.min.toFixed(2)}</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Regional High</p>
                              <p className="font-medium">${item.regional_stats.max.toFixed(2)}</p>
                            </div>
                          </>
                        )}
                      </div>
                    )}

                    {item.potential_savings && item.potential_savings > 0 && (
                      <p className="mt-2 text-sm text-green-600">
                        Potential savings: ${item.potential_savings.toFixed(2)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        <p className="text-center mt-8 text-xs text-muted-foreground">
          Data sourced from CMS Hospital Price Transparency files (mock data for demo)
        </p>
      </div>
    </main>
  );
}
