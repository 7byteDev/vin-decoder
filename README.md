# VIN-Decoder

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](VERSION)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/github-%23181717.svg?logo=github&logoColor=white)](https://github.com/7byteDev/vin-decoder)

Webbasierter, mehrsprachiger (EN/DE/TR) VIN-Decoder mit eigener PostgreSQL-Datenbank,
Multi-Source-Abgleich und **Konfidenz- und Quellenangabe pro Feld**. Schwerpunkt:
europäische und türkische Fahrzeuge – der Bereich, den die freien US-Quellen nur
lückenhaft abdecken.

## ⚠️ Important: Password Replacement

This project has been prepared for public release. All sensitive passwords in `.env.example`
have been replaced with placeholder values:

- `POSTGRES_PASSWORD=YOURPASSWORD`
- `DATABASE_URL=postgresql+asyncpg://vindb:YOURPASSWORD@db:5432/vindb`
- `DATABASE_URL_SYNC=postgresql://vindb:YOURPASSWORD@db:5432/vindb`

Please set your actual PostgreSQL password before running the application.

---

## 📋 Table of Contents

- [Quickstart](#-quickstart)
- [Database External Fill Solution](#-database-external-fill-solution)
- [Installation](#-installation)
- [Usage](#-usage)
- [Versioning](#-versioning)
- [License](#-license)

---

## 🚀 Quickstart

### With Docker (recommended)

```bash
# 1. Copy .env.example and set your PostgreSQL password
cp .env.example .env

# 2. Edit .env and set YOURPASSWORD
#    POSTGRES_PASSWORD=your_actual_password

# 3. Start the stack
docker compose up -d db api frontend

# 4. Import data (first run)
docker compose run --rm etl python -m etl.run_import all

# 5. Access the UI at http://localhost:3000 and API at http://localhost:8000/docs
```

### Without Docker (local installation)

```bash
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# 2. Install backend dependencies
pip install -e "backend[dev,etl]"

# 3. Install frontend dependencies
npm --prefix frontend install

# 4. Copy .env.example and configure
cp .env.example .env
# Set your PostgreSQL connection details in .env

# 5. Start the API server
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 6. Start the frontend (in another terminal)
npm --prefix frontend run dev

# 7. Access the UI at http://localhost:3000 and API at http://localhost:8000/docs
```

---

## 🗄️ Database External Fill Solution

Since the database size is significant (containing Swiss type approval data, NHTSA WMI data,
and vehicle images), here's how users can fill the database from outside:

### **Solution: Parameterized ETL Import Scripts**

The project already includes comprehensive ETL (Extract-Transform-Load) scripts that can be
run from outside the application to populate the database with custom data.

### **How to Use:**

#### **1. Set up database connection**

Create a `.env` file with your PostgreSQL connection:

```env
DATABASE_URL_SYNC=postgresql://vindb:YOURPASSWORD@localhost:5432/vindb
```

#### **2. Run specific import commands**

```bash
# Migrate schema and seed sources
python -m etl.run_import migrate

# Import NHTSA vPIC WMI data (limited pages for testing)
python -m etl.run_import nhtsa-wmi --max-pages 2 --concurrency 2

# Import vininfo manufacturer rules
python -m etl.run_import vininfo

# Import Swiss TARGA type approval data (automobile dataset)
python -m etl.run_import targa

# Import Wikimedia images
python -m etl.run_import images --limit 50

# Full import of all data
python -m etl.run_import all
```

#### **3. Custom import options**

All ETL commands support additional parameters:

```bash
# Import only specific brand
python -m etl.run_import catalog --brand MERCEDES-BENZ

# Limit image count
python -m etl.run_import images --limit 100

# Rate limiting (seconds between requests)
python -m etl.run_import targa --rate 2.0

# Focus on Europe/Turkey only
python -m etl.run_import nhtsa-wmi --focus-only
```

### **Idempotency**

All imports are **idempotent** - running them multiple times will:
- Update existing records rather than creating duplicates
- Refresh the `record_count` and `last_import_at` timestamps
- Respect existing data and only add new entries

### **Adding Your Own Data Sources**

To add external data sources, you can:

1. **SQL scripts**: Add migration files in `db/migrations/` following the existing pattern
2. **ETL importers**: Create new importer scripts in `etl/importers/` following the existing API
3. **Direct SQL**: Use `psql` or `asyncpg` to execute custom SQL against the database

### **Database Status Check**

Check the current database state:

```bash
python -m etl.run_import status
```

This will display:
- Which data sources are imported
- Record counts for WMI codes, patterns, type approvals
- Last import timestamps
- Total lookup statistics

---

## 🛠️ Installation

### Prerequisites

- Docker & Docker Compose (recommended)
- Python 3.11+
- Node.js 18+
- PostgreSQL 13+

### Docker Installation

```bash
# Clone the repository
git clone https://github.com/7byteDev/vin-decoder.git
cd vin-decoder

# Copy and configure .env
cp .env.example .env
# Set your PostgreSQL password

# Start all services
docker compose up -d

# Import data
docker compose run --rm etl python -m etl.run_import all

# Start the application
# UI: http://localhost:3000
# API: http://localhost:8000
```

### Local Installation

```bash
# 1. Clone the repository
git clone https://github.com/7byteDev/vin-decoder.git
cd vin-decoder

# 2. Backend setup
python -m venv .venv
.venv\Scripts\activate
pip install -e "backend[dev,etl]"

# 3. Frontend setup
npm --prefix frontend install

# 4. Configure environment
cp .env.example .env
# Set DATABASE_URL, POSTGRES_PASSWORD, and other settings

# 5. Initialize database
cd backend
createdb vindb  # or use Docker
python -m etl.run_import migrate

# 6. Start services
# API: uvicorn app.main:app --reload --port 8000
# Frontend: npm --prefix frontend run dev
```

---

## 📦 Usage

### API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/v1/decode/{vin}` | Decode a VIN (GET) |
| `POST /api/v1/decode` | Decode a VIN (POST) |
| `GET /api/v1/health` | Health check |
| `GET /api/v1/sources` | List data sources |
| `GET /api/v1/stats` | Database statistics |
| `GET /api/v1/brands` | List all brands |
| `GET /api/v1/brands/{brand}` | List models for a brand |

### Web UI

Navigate to `http://localhost:3000` and:

1. **Select language** (EN/DE/TR) using the language switcher
2. **Enter a VIN** in the search field
3. **View results** including:
   - Structural decoding (WMI, VDS, VIS)
   - Confidence scores per field
   - Source attribution
   - Matching type approval records
   - Technical specifications (engine, power, dimensions, etc.)

### Multilingual Support

The UI is fully translated in English, German, and Turkish. Use the language
selector in the header to switch between languages.

---

## 🔡 Versioning

This project follows [Semantic Versioning](https://semver.org/) `MAJOR.MINOR.PATCH`:

- **1.0.0** - Initial public release
  - VIN decoding with structural and database-assisted lookups
  - Multilingual UI (EN/DE/TR)
  - Docker support with PostgreSQL
  - ETL import scripts for all data sources
  - Professional README with installation instructions

### Version History

See the [GitHub tags](https://github.com/7byteDev/vin-decoder/tags) for the complete version history.

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

### Data Sources Licenses

- **Swiss TARGA type approval data**: Open Government Data, CC-BY 4.0
- **NHTSA vPIC API**: Free public API, usage terms apply
- **Wikimedia Commons images**: Various free licenses
- **vininfo manufacturer rules**: BSD-3-Clause

---

## 👁️ Screenshot

**VIN Decoder Search Engine**

![VIN Decoder Search Engine](docs/screenshots/vin_decoder_1.png)

**Brand/Model Overview**

![Brand/Model Overview](docs/screenshots/vin_decoder_2.png)

**Vehicle Details/Specs**

![Vehicle Details/Specs](docs/screenshots/vin_decoder_3.png)

*Three key screenshots of the VIN-Decoder web interface:*

1. **VIN Decoder Search** - The main search interface where users enter a VIN to decode
2. **Brand/Model Overview** - Overview of vehicle brands and models with search results
3. **Vehicle Details/Specs** - Complete technical specifications including engine, power, dimensions, and features

---

## 🤝 Credits

- ADAC Autokatalog for type approval data
- NHTSA vPIC for North American vehicle data
- Wikimedia Commons for vehicle images
- Swiss Federal Office for Spatial Development (ARE) for TARGA data

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/7byteDev/vin-decoder/issues)
- **Discussions**: [GitHub Discussions](https://github.com/7byteDev/vin-decoder/discussions)