# CSV Datasets for PinchBench Benchmark Tasks

This directory contains sample CSV datasets for use in AI agent benchmark tasks. All datasets are public domain or have permissive licenses and are small enough (<100KB each) to be easily processed.

## Datasets

### 1. `apple_stock_2014.csv` (5.5 KB)
- **Source**: [Plotly Datasets](https://github.com/plotly/datasets)
- **Rows**: 240
- **Description**: Daily stock prices for Apple Inc. (AAPL) during 2014.
- **Columns**: Date, Stock Price
- **Good for**: Time series analysis, trend detection, financial calculations
- **License**: MIT (Plotly datasets)

### 2. `gapminder_life_expectancy.csv` (82 KB)
- **Source**: [Plotly Datasets](https://github.com/plotly/datasets) (derived from Gapminder)
- **Rows**: 1,704
- **Description**: Country-level data on life expectancy, GDP per capita, and population from 1952-2007, sampled every 5 years.
- **Columns**: country, year, pop (population), continent, lifeExp (life expectancy), gdpPercap (GDP per capita)
- **Good for**: Cross-country comparisons, correlation analysis, demographic trends
- **License**: CC-BY (Gapminder)

### 3. `global_temperature.csv` (84 KB)
- **Source**: [DataHub Global Temperature](https://github.com/datasets/global-temp)
- **Rows**: 3,823
- **Description**: Monthly global temperature anomalies from 1850 to present, combining data from multiple sources (GCAG and GISTEMP).
- **Columns**: Source, Year-Month, Mean (temperature anomaly in Celsius)
- **Good for**: Climate trend analysis, anomaly detection, long-term time series
- **License**: CC0 (Public Domain)

### 4. `idaho_weather_stations.csv` (19 KB)
- **Source**: [University of Idaho Geocatalog](https://geocatalog-uidaho.hub.arcgis.com/) via [Data.gov](https://data.gov)
- **Rows**: 213
- **Description**: Weather station locations across Idaho including station name, managing agency, county, coordinates, and elevation.
- **Columns**: OBJECTID, Station Name, Station Code, Managing Agency, County, Longitude, Latitude, Elevation (feet), x, y
- **Good for**: Geospatial queries, elevation analysis, agency distribution
- **License**: Public Domain (US Government)

### 5. `iris_flowers.csv` (4.6 KB)
- **Source**: [Plotly Datasets](https://github.com/plotly/datasets)
- **Rows**: 150
- **Description**: Classic machine learning dataset with measurements of iris flowers from three species.
- **Columns**: SepalLength, SepalWidth, PetalLength, PetalWidth, Name (species)
- **Good for**: Classification tasks, statistical analysis, pattern recognition
- **License**: Public Domain (classic dataset)

### 6. `us_cities_top1000.csv` (54 KB)
- **Source**: [Plotly Datasets](https://github.com/plotly/datasets)
- **Rows**: 1,000
- **Description**: Top 1000 US cities by population with geographic coordinates.
- **Columns**: City, State, Population, lat, lon
- **Good for**: Geographic analysis, population ranking, distance calculations
- **License**: MIT (Plotly datasets)

### 7. `us_pension_by_state.csv` (25 KB)
- **Source**: [Pension Benefit Guaranty Corporation (PBGC)](https://www.pbgc.gov/) via [Data.gov](https://data.gov)
- **Rows**: 563
- **Description**: Pension benefit payments by US state and territory, including payee counts and deferred counts.
- **Columns**: STATE_ABBREV_NAME, DISTRICT, PAYEE_AMOUNT, PAYEE_COUNT, DEFERRED_COUNT
- **Good for**: Financial aggregation, state comparisons, benefit analysis
- **License**: Public Domain (US Government)

### 8. `world_gdp_2014.csv` (4.5 KB)
- **Source**: [Plotly Datasets](https://github.com/plotly/datasets)
- **Rows**: 222
- **Description**: GDP (in billions USD) for countries worldwide in 2014.
- **Columns**: COUNTRY, GDP (BILLIONS), CODE (ISO country code)
- **Good for**: Economic comparisons, regional analysis, top/bottom rankings
- **License**: MIT (Plotly datasets)

## Usage Notes

- All files use comma delimiters with header rows
- Character encoding is UTF-8
- These datasets are intentionally small for quick processing in benchmark tasks
- Great for testing: data loading, filtering, aggregation, sorting, and analysis capabilities

## License Summary

Most datasets are either Public Domain (US Government sources) or MIT licensed (Plotly datasets). The Gapminder data is CC-BY. All are free to use for research and commercial purposes with appropriate attribution where noted.
