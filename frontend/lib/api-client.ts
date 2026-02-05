const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;

    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  async healthCheck() {
    return this.request("/health");
  }

  async uploadPdf(file: File) {
    const formData = new FormData();
    formData.append("file", file);

    const url = `${this.baseUrl}/api/upload`;
    const response = await fetch(url, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status}`);
    }

    return response.json();
  }

  async extractLineItems(fileId: string) {
    return this.request("/api/extract", {
      method: "POST",
      body: JSON.stringify({ file_id: fileId }),
    });
  }

  async searchHospitals(query: string) {
    return this.request(`/api/hospitals?search=${encodeURIComponent(query)}`);
  }

  async compareCharges(data: {
    line_items: Array<{
      code?: string;
      description: string;
      quantity: number;
      amount: number;
    }>;
    hospital_id: string;
    radius_miles?: number;
  }) {
    return this.request("/api/compare", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }
}

export const apiClient = new ApiClient();
