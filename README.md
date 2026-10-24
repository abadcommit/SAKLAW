# SAKLAW: SPATIAL ANALYSIS OF KEY LOCATIONS FOR ACCESSIBLE WELLNESS FACILITIES

---
## Running SAKLAW

1. Clone the project
- Open file explorer
- Create a folder
- Right click the folder and choose "open with terminal"
run `git clone https://github.com/abadcommit/SAKLAW.git`

2. Install the model requirements
in the same terminal, run `pip install -r requirements.txt`

3. Download the model data
install this [file](https://l.messenger.com/l.php?u=https%3A%2F%2Fdrive.google.com%2Fdrive%2Ffolders%2F1Yv2Ikq1jjDUp1XXRZQ7H5h8FHSs110rg%3Fusp%3Dsharing&h=AUAXBMUSsAnCLlzXhIZ7hCRP1xEYlPwOQEgixoqUwHtnuTtfmooarsuQzCrhWtt3dUXCYcPnSF5F-IL9uB2sVHpwdtEDH9QCpzk_bDUbAoklmYgt9aMG4fGx4mEqTMcrlZiYy71p_4oI23Y`)

4. Move the downloaded file into the model > data folder (./model/data)
5. Run the SAKLAW API with this command:\
`python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000`
6. Install [NodeJS](https://nodejs.org/en/download)
7. Open another terminal and navigate to this folder (repeat step 1 **__except__** the command)
8. Navigate to the client folder with:\
`cd ./client`
9. Install the dependencies
`npm install`
10. Run the frontend server
`npm run dev`
11. Go to the [SAKLAW web app](http://localhost:5173)


## Executive Summary

Unequal access to healthcare and overcrowding in healthcare facilities remain persistent challenges in the Philippines. Existing facility locations may not adequately address the needs of surrounding communities, while healthcare planning tools may lack localized information on facility capacity, population distribution, and geographic accessibility. These gaps highlight the need for a data-driven approach to healthcare infrastructure planning that can identify underserved communities and support more equitable access to healthcare services. To address this need, our team proposes SAKLAW (Spatial Analysis of Key Locations for Accessible Wellness Facilities), a GIS-based decision-support system designed to assess healthcare accessibility and support preliminary site identification for new public healthcare facilities. Using publicly available data, SAKLAW analyzes estimated road-network travel times between communities and existing healthcare facilities, population distribution, and available information on healthcare service capacity to identify potential gaps in the existing healthcare network. Beyond assessing current accessibility, SAKLAW identifies and evaluates candidate locations for additional healthcare facilities based on their potential to improve population coverage, reduce travel times, and address underserved areas. Through configurable scenarios, government planning officials can compare alternative facility locations, examine trade-offs between accessibility and community needs, and assess how different planning priorities affect healthcare coverage. By providing localized spatial analysis and transparent, data-driven comparisons, SAKLAW aims to support more informed preliminary site identification and healthcare infrastructure planning, particularly for communities with limited access to healthcare services.

### Naming Conventions
**PascalCase** when naming components and classes\
**kebab-case** when naming css variables\
**camelCase** when naming props\
`'strings'` must be wrapped with single quotes unless otherwise necessary

### File Structure
Component files go in `./src/components`\
Stylesheets for components go in `./src/stylesheets`