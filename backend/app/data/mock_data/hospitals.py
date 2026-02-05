"""Mock hospital data for Raleigh-Durham-Chapel Hill NC area hospitals."""

from typing import List, Dict, Optional

HOSPITALS = [
    {
        "id": "duke_main",
        "name": "Duke University Hospital",
        "address": "2301 Erwin Rd, Durham, NC 27710",
        "city": "Durham",
        "state": "NC",
        "zip": "27710",
        "type": "General Acute Care",
    },
    {
        "id": "duke_regional",
        "name": "Duke Regional Hospital",
        "address": "3643 N Roxboro St, Durham, NC 27704",
        "city": "Durham",
        "state": "NC",
        "zip": "27704",
        "type": "General Acute Care",
    },
    {
        "id": "duke_raleigh",
        "name": "Duke Raleigh Hospital",
        "address": "3400 Wake Forest Rd, Raleigh, NC 27609",
        "city": "Raleigh",
        "state": "NC",
        "zip": "27609",
        "type": "General Acute Care",
    },
    {
        "id": "unc_main",
        "name": "UNC Medical Center",
        "address": "101 Manning Dr, Chapel Hill, NC 27514",
        "city": "Chapel Hill",
        "state": "NC",
        "zip": "27514",
        "type": "General Acute Care",
    },
    {
        "id": "unc_rex",
        "name": "UNC Rex Hospital",
        "address": "4420 Lake Boone Trail, Raleigh, NC 27607",
        "city": "Raleigh",
        "state": "NC",
        "zip": "27607",
        "type": "General Acute Care",
    },
    {
        "id": "unc_hillsborough",
        "name": "UNC Hospitals Hillsborough Campus",
        "address": "429 Waterstone Dr, Hillsborough, NC 27278",
        "city": "Hillsborough",
        "state": "NC",
        "zip": "27278",
        "type": "General Acute Care",
    },
    {
        "id": "wakemed_raleigh",
        "name": "WakeMed Raleigh Campus",
        "address": "3000 New Bern Ave, Raleigh, NC 27610",
        "city": "Raleigh",
        "state": "NC",
        "zip": "27610",
        "type": "General Acute Care",
    },
    {
        "id": "wakemed_cary",
        "name": "WakeMed Cary Hospital",
        "address": "1900 Kildaire Farm Rd, Cary, NC 27518",
        "city": "Cary",
        "state": "NC",
        "zip": "27518",
        "type": "General Acute Care",
    },
    {
        "id": "wakemed_north",
        "name": "WakeMed North Hospital",
        "address": "10000 Falls of Neuse Rd, Raleigh, NC 27614",
        "city": "Raleigh",
        "state": "NC",
        "zip": "27614",
        "type": "General Acute Care",
    },
]


# Mock price data: hospital_id -> cpt_code -> price info
# Prices vary by hospital to simulate real-world variance
HOSPITAL_PRICES: Dict[str, Dict[str, Dict]] = {
    "duke_main": {
        "99213": {"gross_charge": 385.00, "negotiated_rate": 192.00, "description": "Office visit, established patient, low complexity"},
        "99214": {"gross_charge": 495.00, "negotiated_rate": 247.00, "description": "Office visit, established patient, moderate complexity"},
        "99215": {"gross_charge": 635.00, "negotiated_rate": 317.00, "description": "Office visit, established patient, high complexity"},
        "85025": {"gross_charge": 105.00, "negotiated_rate": 52.00, "description": "Complete blood count (CBC)"},
        "80053": {"gross_charge": 205.00, "negotiated_rate": 102.00, "description": "Comprehensive metabolic panel"},
        "80048": {"gross_charge": 165.00, "negotiated_rate": 82.00, "description": "Basic metabolic panel"},
        "71046": {"gross_charge": 725.00, "negotiated_rate": 362.00, "description": "Chest X-ray, 2 views"},
        "71045": {"gross_charge": 505.00, "negotiated_rate": 252.00, "description": "Chest X-ray, single view"},
        "36415": {"gross_charge": 52.00, "negotiated_rate": 26.00, "description": "Venipuncture"},
        "93000": {"gross_charge": 385.00, "negotiated_rate": 192.00, "description": "Electrocardiogram (ECG/EKG)"},
        "73030": {"gross_charge": 465.00, "negotiated_rate": 232.00, "description": "X-ray shoulder, 2+ views"},
        "72148": {"gross_charge": 3150.00, "negotiated_rate": 1575.00, "description": "MRI lumbar spine without contrast"},
        "70553": {"gross_charge": 3550.00, "negotiated_rate": 1775.00, "description": "MRI brain with and without contrast"},
        "74177": {"gross_charge": 2750.00, "negotiated_rate": 1375.00, "description": "CT abdomen/pelvis with contrast"},
        "43239": {"gross_charge": 5100.00, "negotiated_rate": 2550.00, "description": "Upper GI endoscopy with biopsy"},
        "45380": {"gross_charge": 4350.00, "negotiated_rate": 2175.00, "description": "Colonoscopy with biopsy"},
    },
    "duke_regional": {
        "99213": {"gross_charge": 325.00, "negotiated_rate": 162.00, "description": "Office visit, established patient, low complexity"},
        "99214": {"gross_charge": 420.00, "negotiated_rate": 210.00, "description": "Office visit, established patient, moderate complexity"},
        "99215": {"gross_charge": 540.00, "negotiated_rate": 270.00, "description": "Office visit, established patient, high complexity"},
        "85025": {"gross_charge": 88.00, "negotiated_rate": 44.00, "description": "Complete blood count (CBC)"},
        "80053": {"gross_charge": 172.00, "negotiated_rate": 86.00, "description": "Comprehensive metabolic panel"},
        "80048": {"gross_charge": 138.00, "negotiated_rate": 69.00, "description": "Basic metabolic panel"},
        "71046": {"gross_charge": 612.00, "negotiated_rate": 306.00, "description": "Chest X-ray, 2 views"},
        "71045": {"gross_charge": 425.00, "negotiated_rate": 212.00, "description": "Chest X-ray, single view"},
        "36415": {"gross_charge": 44.00, "negotiated_rate": 22.00, "description": "Venipuncture"},
        "93000": {"gross_charge": 325.00, "negotiated_rate": 162.00, "description": "Electrocardiogram (ECG/EKG)"},
        "73030": {"gross_charge": 392.00, "negotiated_rate": 196.00, "description": "X-ray shoulder, 2+ views"},
        "72148": {"gross_charge": 2650.00, "negotiated_rate": 1325.00, "description": "MRI lumbar spine without contrast"},
        "70553": {"gross_charge": 2995.00, "negotiated_rate": 1497.00, "description": "MRI brain with and without contrast"},
        "74177": {"gross_charge": 2320.00, "negotiated_rate": 1160.00, "description": "CT abdomen/pelvis with contrast"},
        "43239": {"gross_charge": 4300.00, "negotiated_rate": 2150.00, "description": "Upper GI endoscopy with biopsy"},
        "45380": {"gross_charge": 3670.00, "negotiated_rate": 1835.00, "description": "Colonoscopy with biopsy"},
    },
    "duke_raleigh": {
        "99213": {"gross_charge": 340.00, "negotiated_rate": 170.00, "description": "Office visit, established patient, low complexity"},
        "99214": {"gross_charge": 440.00, "negotiated_rate": 220.00, "description": "Office visit, established patient, moderate complexity"},
        "99215": {"gross_charge": 565.00, "negotiated_rate": 282.00, "description": "Office visit, established patient, high complexity"},
        "85025": {"gross_charge": 92.00, "negotiated_rate": 46.00, "description": "Complete blood count (CBC)"},
        "80053": {"gross_charge": 180.00, "negotiated_rate": 90.00, "description": "Comprehensive metabolic panel"},
        "80048": {"gross_charge": 145.00, "negotiated_rate": 72.00, "description": "Basic metabolic panel"},
        "71046": {"gross_charge": 640.00, "negotiated_rate": 320.00, "description": "Chest X-ray, 2 views"},
        "71045": {"gross_charge": 445.00, "negotiated_rate": 222.00, "description": "Chest X-ray, single view"},
        "36415": {"gross_charge": 46.00, "negotiated_rate": 23.00, "description": "Venipuncture"},
        "93000": {"gross_charge": 340.00, "negotiated_rate": 170.00, "description": "Electrocardiogram (ECG/EKG)"},
        "73030": {"gross_charge": 410.00, "negotiated_rate": 205.00, "description": "X-ray shoulder, 2+ views"},
        "72148": {"gross_charge": 2775.00, "negotiated_rate": 1387.00, "description": "MRI lumbar spine without contrast"},
        "70553": {"gross_charge": 3135.00, "negotiated_rate": 1567.00, "description": "MRI brain with and without contrast"},
        "74177": {"gross_charge": 2430.00, "negotiated_rate": 1215.00, "description": "CT abdomen/pelvis with contrast"},
        "43239": {"gross_charge": 4500.00, "negotiated_rate": 2250.00, "description": "Upper GI endoscopy with biopsy"},
        "45380": {"gross_charge": 3845.00, "negotiated_rate": 1922.00, "description": "Colonoscopy with biopsy"},
    },
    "unc_main": {
        "99213": {"gross_charge": 365.00, "negotiated_rate": 182.00, "description": "Office visit, established patient, low complexity"},
        "99214": {"gross_charge": 470.00, "negotiated_rate": 235.00, "description": "Office visit, established patient, moderate complexity"},
        "99215": {"gross_charge": 605.00, "negotiated_rate": 302.00, "description": "Office visit, established patient, high complexity"},
        "85025": {"gross_charge": 98.00, "negotiated_rate": 49.00, "description": "Complete blood count (CBC)"},
        "80053": {"gross_charge": 192.00, "negotiated_rate": 96.00, "description": "Comprehensive metabolic panel"},
        "80048": {"gross_charge": 154.00, "negotiated_rate": 77.00, "description": "Basic metabolic panel"},
        "71046": {"gross_charge": 680.00, "negotiated_rate": 340.00, "description": "Chest X-ray, 2 views"},
        "71045": {"gross_charge": 475.00, "negotiated_rate": 237.00, "description": "Chest X-ray, single view"},
        "36415": {"gross_charge": 48.00, "negotiated_rate": 24.00, "description": "Venipuncture"},
        "93000": {"gross_charge": 365.00, "negotiated_rate": 182.00, "description": "Electrocardiogram (ECG/EKG)"},
        "73030": {"gross_charge": 440.00, "negotiated_rate": 220.00, "description": "X-ray shoulder, 2+ views"},
        "72148": {"gross_charge": 2950.00, "negotiated_rate": 1475.00, "description": "MRI lumbar spine without contrast"},
        "70553": {"gross_charge": 3325.00, "negotiated_rate": 1662.00, "description": "MRI brain with and without contrast"},
        "74177": {"gross_charge": 2580.00, "negotiated_rate": 1290.00, "description": "CT abdomen/pelvis with contrast"},
        "43239": {"gross_charge": 4780.00, "negotiated_rate": 2390.00, "description": "Upper GI endoscopy with biopsy"},
        "45380": {"gross_charge": 4080.00, "negotiated_rate": 2040.00, "description": "Colonoscopy with biopsy"},
    },
    "unc_rex": {
        "99213": {"gross_charge": 310.00, "negotiated_rate": 155.00, "description": "Office visit, established patient, low complexity"},
        "99214": {"gross_charge": 400.00, "negotiated_rate": 200.00, "description": "Office visit, established patient, moderate complexity"},
        "99215": {"gross_charge": 515.00, "negotiated_rate": 257.00, "description": "Office visit, established patient, high complexity"},
        "85025": {"gross_charge": 82.00, "negotiated_rate": 41.00, "description": "Complete blood count (CBC)"},
        "80053": {"gross_charge": 160.00, "negotiated_rate": 80.00, "description": "Comprehensive metabolic panel"},
        "80048": {"gross_charge": 128.00, "negotiated_rate": 64.00, "description": "Basic metabolic panel"},
        "71046": {"gross_charge": 565.00, "negotiated_rate": 282.00, "description": "Chest X-ray, 2 views"},
        "71045": {"gross_charge": 395.00, "negotiated_rate": 197.00, "description": "Chest X-ray, single view"},
        "36415": {"gross_charge": 40.00, "negotiated_rate": 20.00, "description": "Venipuncture"},
        "93000": {"gross_charge": 310.00, "negotiated_rate": 155.00, "description": "Electrocardiogram (ECG/EKG)"},
        "73030": {"gross_charge": 372.00, "negotiated_rate": 186.00, "description": "X-ray shoulder, 2+ views"},
        "72148": {"gross_charge": 2450.00, "negotiated_rate": 1225.00, "description": "MRI lumbar spine without contrast"},
        "70553": {"gross_charge": 2765.00, "negotiated_rate": 1382.00, "description": "MRI brain with and without contrast"},
        "74177": {"gross_charge": 2145.00, "negotiated_rate": 1072.00, "description": "CT abdomen/pelvis with contrast"},
        "43239": {"gross_charge": 3975.00, "negotiated_rate": 1987.00, "description": "Upper GI endoscopy with biopsy"},
        "45380": {"gross_charge": 3395.00, "negotiated_rate": 1697.00, "description": "Colonoscopy with biopsy"},
    },
    "unc_hillsborough": {
        "99213": {"gross_charge": 285.00, "negotiated_rate": 142.00, "description": "Office visit, established patient, low complexity"},
        "99214": {"gross_charge": 368.00, "negotiated_rate": 184.00, "description": "Office visit, established patient, moderate complexity"},
        "99215": {"gross_charge": 475.00, "negotiated_rate": 237.00, "description": "Office visit, established patient, high complexity"},
        "85025": {"gross_charge": 75.00, "negotiated_rate": 37.00, "description": "Complete blood count (CBC)"},
        "80053": {"gross_charge": 148.00, "negotiated_rate": 74.00, "description": "Comprehensive metabolic panel"},
        "80048": {"gross_charge": 118.00, "negotiated_rate": 59.00, "description": "Basic metabolic panel"},
        "71046": {"gross_charge": 520.00, "negotiated_rate": 260.00, "description": "Chest X-ray, 2 views"},
        "71045": {"gross_charge": 365.00, "negotiated_rate": 182.00, "description": "Chest X-ray, single view"},
        "36415": {"gross_charge": 36.00, "negotiated_rate": 18.00, "description": "Venipuncture"},
        "93000": {"gross_charge": 285.00, "negotiated_rate": 142.00, "description": "Electrocardiogram (ECG/EKG)"},
        "73030": {"gross_charge": 342.00, "negotiated_rate": 171.00, "description": "X-ray shoulder, 2+ views"},
        "72148": {"gross_charge": 2250.00, "negotiated_rate": 1125.00, "description": "MRI lumbar spine without contrast"},
        "70553": {"gross_charge": 2540.00, "negotiated_rate": 1270.00, "description": "MRI brain with and without contrast"},
        "74177": {"gross_charge": 1970.00, "negotiated_rate": 985.00, "description": "CT abdomen/pelvis with contrast"},
        "43239": {"gross_charge": 3650.00, "negotiated_rate": 1825.00, "description": "Upper GI endoscopy with biopsy"},
        "45380": {"gross_charge": 3120.00, "negotiated_rate": 1560.00, "description": "Colonoscopy with biopsy"},
    },
    "wakemed_raleigh": {
        "99213": {"gross_charge": 295.00, "negotiated_rate": 147.00, "description": "Office visit, established patient, low complexity"},
        "99214": {"gross_charge": 380.00, "negotiated_rate": 190.00, "description": "Office visit, established patient, moderate complexity"},
        "99215": {"gross_charge": 490.00, "negotiated_rate": 245.00, "description": "Office visit, established patient, high complexity"},
        "85025": {"gross_charge": 78.00, "negotiated_rate": 39.00, "description": "Complete blood count (CBC)"},
        "80053": {"gross_charge": 152.00, "negotiated_rate": 76.00, "description": "Comprehensive metabolic panel"},
        "80048": {"gross_charge": 122.00, "negotiated_rate": 61.00, "description": "Basic metabolic panel"},
        "71046": {"gross_charge": 538.00, "negotiated_rate": 269.00, "description": "Chest X-ray, 2 views"},
        "71045": {"gross_charge": 375.00, "negotiated_rate": 187.00, "description": "Chest X-ray, single view"},
        "36415": {"gross_charge": 38.00, "negotiated_rate": 19.00, "description": "Venipuncture"},
        "93000": {"gross_charge": 295.00, "negotiated_rate": 147.00, "description": "Electrocardiogram (ECG/EKG)"},
        "73030": {"gross_charge": 355.00, "negotiated_rate": 177.00, "description": "X-ray shoulder, 2+ views"},
        "72148": {"gross_charge": 2325.00, "negotiated_rate": 1162.00, "description": "MRI lumbar spine without contrast"},
        "70553": {"gross_charge": 2625.00, "negotiated_rate": 1312.00, "description": "MRI brain with and without contrast"},
        "74177": {"gross_charge": 2035.00, "negotiated_rate": 1017.00, "description": "CT abdomen/pelvis with contrast"},
        "43239": {"gross_charge": 3775.00, "negotiated_rate": 1887.00, "description": "Upper GI endoscopy with biopsy"},
        "45380": {"gross_charge": 3225.00, "negotiated_rate": 1612.00, "description": "Colonoscopy with biopsy"},
    },
    "wakemed_cary": {
        "99213": {"gross_charge": 305.00, "negotiated_rate": 152.00, "description": "Office visit, established patient, low complexity"},
        "99214": {"gross_charge": 395.00, "negotiated_rate": 197.00, "description": "Office visit, established patient, moderate complexity"},
        "99215": {"gross_charge": 508.00, "negotiated_rate": 254.00, "description": "Office visit, established patient, high complexity"},
        "85025": {"gross_charge": 80.00, "negotiated_rate": 40.00, "description": "Complete blood count (CBC)"},
        "80053": {"gross_charge": 158.00, "negotiated_rate": 79.00, "description": "Comprehensive metabolic panel"},
        "80048": {"gross_charge": 126.00, "negotiated_rate": 63.00, "description": "Basic metabolic panel"},
        "71046": {"gross_charge": 558.00, "negotiated_rate": 279.00, "description": "Chest X-ray, 2 views"},
        "71045": {"gross_charge": 390.00, "negotiated_rate": 195.00, "description": "Chest X-ray, single view"},
        "36415": {"gross_charge": 39.00, "negotiated_rate": 19.00, "description": "Venipuncture"},
        "93000": {"gross_charge": 305.00, "negotiated_rate": 152.00, "description": "Electrocardiogram (ECG/EKG)"},
        "73030": {"gross_charge": 368.00, "negotiated_rate": 184.00, "description": "X-ray shoulder, 2+ views"},
        "72148": {"gross_charge": 2415.00, "negotiated_rate": 1207.00, "description": "MRI lumbar spine without contrast"},
        "70553": {"gross_charge": 2725.00, "negotiated_rate": 1362.00, "description": "MRI brain with and without contrast"},
        "74177": {"gross_charge": 2115.00, "negotiated_rate": 1057.00, "description": "CT abdomen/pelvis with contrast"},
        "43239": {"gross_charge": 3920.00, "negotiated_rate": 1960.00, "description": "Upper GI endoscopy with biopsy"},
        "45380": {"gross_charge": 3350.00, "negotiated_rate": 1675.00, "description": "Colonoscopy with biopsy"},
    },
    "wakemed_north": {
        "99213": {"gross_charge": 280.00, "negotiated_rate": 140.00, "description": "Office visit, established patient, low complexity"},
        "99214": {"gross_charge": 362.00, "negotiated_rate": 181.00, "description": "Office visit, established patient, moderate complexity"},
        "99215": {"gross_charge": 465.00, "negotiated_rate": 232.00, "description": "Office visit, established patient, high complexity"},
        "85025": {"gross_charge": 72.00, "negotiated_rate": 36.00, "description": "Complete blood count (CBC)"},
        "80053": {"gross_charge": 142.00, "negotiated_rate": 71.00, "description": "Comprehensive metabolic panel"},
        "80048": {"gross_charge": 114.00, "negotiated_rate": 57.00, "description": "Basic metabolic panel"},
        "71046": {"gross_charge": 505.00, "negotiated_rate": 252.00, "description": "Chest X-ray, 2 views"},
        "71045": {"gross_charge": 352.00, "negotiated_rate": 176.00, "description": "Chest X-ray, single view"},
        "36415": {"gross_charge": 35.00, "negotiated_rate": 17.00, "description": "Venipuncture"},
        "93000": {"gross_charge": 280.00, "negotiated_rate": 140.00, "description": "Electrocardiogram (ECG/EKG)"},
        "73030": {"gross_charge": 335.00, "negotiated_rate": 167.00, "description": "X-ray shoulder, 2+ views"},
        "72148": {"gross_charge": 2185.00, "negotiated_rate": 1092.00, "description": "MRI lumbar spine without contrast"},
        "70553": {"gross_charge": 2465.00, "negotiated_rate": 1232.00, "description": "MRI brain with and without contrast"},
        "74177": {"gross_charge": 1915.00, "negotiated_rate": 957.00, "description": "CT abdomen/pelvis with contrast"},
        "43239": {"gross_charge": 3550.00, "negotiated_rate": 1775.00, "description": "Upper GI endoscopy with biopsy"},
        "45380": {"gross_charge": 3035.00, "negotiated_rate": 1517.00, "description": "Colonoscopy with biopsy"},
    },
}


def search_hospitals(query: str) -> List[Dict]:
    """Search hospitals by name, city, or address."""
    query_lower = query.lower()
    results = []
    for hospital in HOSPITALS:
        if (query_lower in hospital["name"].lower() or
            query_lower in hospital["city"].lower() or
            query_lower in hospital["address"].lower()):
            results.append(hospital)
    return results


def get_hospital(hospital_id: str) -> Optional[Dict]:
    """Get a hospital by ID."""
    for hospital in HOSPITALS:
        if hospital["id"] == hospital_id:
            return hospital
    return None


def get_hospital_prices(hospital_id: str) -> Dict[str, Dict]:
    """Get all prices for a hospital."""
    return HOSPITAL_PRICES.get(hospital_id, {})


def get_price_for_code(hospital_id: str, cpt_code: str) -> Optional[Dict]:
    """Get price for a specific CPT code at a hospital."""
    hospital_prices = HOSPITAL_PRICES.get(hospital_id, {})
    return hospital_prices.get(cpt_code)


def get_all_prices_for_code(cpt_code: str) -> List[Dict]:
    """Get prices for a CPT code across all hospitals."""
    results = []
    for hospital_id, prices in HOSPITAL_PRICES.items():
        if cpt_code in prices:
            hospital = get_hospital(hospital_id)
            if hospital:
                results.append({
                    "hospital": hospital,
                    "price": prices[cpt_code],
                })
    return results


def get_regional_stats(cpt_code: str) -> Optional[Dict]:
    """Get regional statistics for a CPT code."""
    prices = []
    for hospital_id, hospital_prices in HOSPITAL_PRICES.items():
        if cpt_code in hospital_prices:
            prices.append(hospital_prices[cpt_code]["gross_charge"])

    if not prices:
        return None

    prices.sort()
    return {
        "min": min(prices),
        "max": max(prices),
        "median": prices[len(prices) // 2],
        "average": sum(prices) / len(prices),
        "count": len(prices),
    }
