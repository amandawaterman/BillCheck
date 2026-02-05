# BillCheck

Hospital bill sanity checker powered by CMS price transparency data.

## Overview

BillCheck helps patients understand if their hospital bills are reasonable by comparing charges against CMS price transparency data and local hospital prices.

## Tech Stack

- **Frontend**: Next.js 15, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: FastAPI (Python 3.11+), pdfplumber
- **Data**: Mock CMS hospital price data for Boston area hospitals

## Project Structure

```
billcheck/
├── frontend/          # Next.js application
├── backend/           # FastAPI application
└── docker-compose.yml # Local development environment
```

## Getting Started

### Option 1: Using Docker (Recommended)

```bash
# Start both frontend and backend
docker-compose up

# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Option 2: Manual Setup

#### Frontend

```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:3000
```

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload
# Runs on http://localhost:8000
# API docs at http://localhost:8000/docs
```

## Development

### Frontend Development

The frontend uses Next.js 15 with the App Router. Key directories:

- `app/` - Pages and routes
- `components/` - React components
- `lib/` - Utility functions and API client
- `hooks/` - Custom React hooks
- `context/` - Global state management

### Backend Development

The backend uses FastAPI. Key directories:

- `app/api/routes/` - API endpoints
- `app/services/` - Business logic
- `app/models/` - Pydantic data models
- `app/data/mock_data/` - Sample hospital data
- `app/utils/` - Utility functions

### Running Tests

```bash
# Frontend tests
cd frontend
npm test

# Backend tests
cd backend
pytest
```

## User Flow

1. **Upload**: User uploads a hospital bill PDF
2. **Review**: System extracts line items, user can edit/correct
3. **Hospital**: User selects their hospital from searchable list
4. **Results**: View comparison of charges vs. CMS data and local hospitals
5. **Summary**: Overall bill assessment and recommendations

## API Endpoints

- `POST /api/upload` - Upload PDF file
- `POST /api/extract` - Extract line items from PDF
- `GET /api/hospitals` - Search hospitals
- `POST /api/compare` - Compare line items to hospital prices

## Mock Data

The MVP uses mock data for Triangle, NC area hospitals

## License

MIT
