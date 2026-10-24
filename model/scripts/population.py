import pandas as pd

file_path = "data/combined_barangay_population.csv"
df = pd.read_csv(file_path)

# 2. Inspect the dataset
print("=== Dataset Shape ===")
print(f"Rows: {df.shape[0]}, Columns: {df.shape[1]}")

print("\n=== Column Names ===")
print(df.columns.tolist())

print("\n=== Data Types ===")
print(df.dtypes)

print("\n=== First 5 Rows ===")
print(df.head())

print("\n=== Missing Values ===")
print(df.isnull().sum())

# 3. Inspect population-related columns
print("\n=== Population Columns ===")
for col in df.columns:
    if "pop" in col.lower():
        print(f"\nColumn: {col}")
        print("Data type:", df[col].dtype)
        print("Sample values:", df[col].head(10).tolist())
        print("Unique values:", df[col].nunique())
        print("Missing values:", df[col].isna().sum())

# 4. Convert the population column to integers
# Change this to the exact column name printed above.
population_col = "population"

# Handle commas in numeric strings, e.g. "12,345"
population = pd.to_numeric(
    df[population_col].astype(str).str.replace(",", "", regex=False),
    errors="coerce"
)

# Inspect values that could not be converted
invalid = population.isna() & df[population_col].notna()

print("\n=== Invalid Population Values ===")
print(df.loc[invalid, population_col].head(20))

# Stop if values are missing or invalid rather than silently losing data.
if population.isna().any():
    raise ValueError(
        f"{population.isna().sum()} population values are missing or invalid. "
        "Inspect and resolve them before converting."
    )

# Ensure values are whole numbers before integer conversion.
if ((population % 1) != 0).any():
    raise ValueError(
        "Population contains fractional values. Decide whether to round "
        "or truncate them before converting."
    )

df[population_col] = population.astype("int64")

print("\n=== Converted Population ===")
print(df[population_col].head(10))
print("New data type:", df[population_col].dtype)

# 5. Save the cleaned dataset
output_path = "data/census_2024_cleaned.csv"
df.to_csv(output_path, index=False)

print(f"\nSaved cleaned CSV to: {output_path}")
