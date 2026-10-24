# SAKLAW: SPATIAL ANALYSIS OF KEY LOCATIONS FOR ACCESSIBLE WELLNESS FACILITIES

---

## Executive Summary

Unequal access to healthcare and overcrowding in healthcare facilities remain persistent challenges in the Philippines. Existing facility locations may not adequately address the needs of surrounding communities, while healthcare planning tools may lack localized information on facility capacity, population distribution, and geographic accessibility. These gaps highlight the need for a data-driven approach to healthcare infrastructure planning that can identify underserved communities and support more equitable access to healthcare services. To address this need, our team proposes SAKLAW (Spatial Analysis of Key Locations for Accessible Wellness Facilities), a GIS-based decision-support system designed to assess healthcare accessibility and support preliminary site identification for new public healthcare facilities. Using publicly available data, SAKLAW analyzes estimated road-network travel times between communities and existing healthcare facilities, population distribution, and available information on healthcare service capacity to identify potential gaps in the existing healthcare network. Beyond assessing current accessibility, SAKLAW identifies and evaluates candidate locations for additional healthcare facilities based on their potential to improve population coverage, reduce travel times, and address underserved areas. Through configurable scenarios, government planning officials can compare alternative facility locations, examine trade-offs between accessibility and community needs, and assess how different planning priorities affect healthcare coverage. By providing localized spatial analysis and transparent, data-driven comparisons, SAKLAW aims to support more informed preliminary site identification and healthcare infrastructure planning, particularly for communities with limited access to healthcare services.

---
## Getting Started

Follow the instructions below to run SAKLAW locally.

### Prerequisites

Make sure you have the following installed:

- Git
- Python
- Node.js and npm

### 1. Clone the Repository

Open a terminal in the directory where you want to store the project and run:

```bash
git clone https://github.com/abadcommit/SAKLAW.git
cd SAKLAW
```

### 2. Install the Python Dependencies

From the project root directory, run:

```bash
pip install -r requirements.txt
```

If you use a Python virtual environment, activate it before installing the dependencies.

### 3. Download the Model Data

Download the required model data from the provided Google Drive folder.

After downloading, extract the files if necessary and place them in the following directory:

```text
SAKLAW/
└── model/
    └── data/
```

**Required file:** Download [this file](https://drive.google.com/file/d/1DDvg6RYoWW_M4eLA1kND9kbvXR9o8jvq/view?usp=sharing) and place it inside `model/data/`.

Make sure the downloaded file is in the correct directory and retains the filename expected by the model.

### 4. Start the Backend API

From the project root directory, run:

```bash
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Keep this terminal running while using the application. The backend API will be available at `http://127.0.0.1:8000`.

### 5. Install the Frontend Dependencies

Open a second terminal and navigate to the project directory. Enter the client directory:

```bash
cd SAKLAW/client
```

If your terminal is already in the project root, run only:

```bash
cd client
```

Install the required packages:

```bash
npm install
```

### 6. Start the Frontend

In the same terminal, run:

```bash
npm run dev
```

### 7. Open the Web Application

Open your browser and navigate to:

```text
http://localhost:5173
```

Both the backend API and frontend development server must remain running for the application to work correctly.
