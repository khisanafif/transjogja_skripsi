import pandas as pd

df1 = pd.read_csv('wisata_jogja.csv')
df2 = pd.read_csv('../../dataset-wisata-jogja-sekitar.csv')

print(f"Total rows in wisata_jogja.csv: {len(df1)}")
print(f"Total rows in dataset-wisata-jogja-sekitar.csv: {len(df2)}")

df1_names = set(df1['nama'].str.lower().str.strip())
df2_names = set(df2['nama'].str.lower().str.strip())

missing = df1_names - df2_names
print(f"Missing from dataset-wisata-jogja-sekitar.csv: {len(missing)}")

# Merge df1 and df2
merged = pd.merge(df1, df2[['nama', 'image', 'vote_average', 'vote_count']], on='nama', how='left')

# In df1, the columns for rating are 'vote_average' and 'vote_count'
# Wait, df1 ALREADY has 'vote_average' and 'vote_count' as we saw from the headers!
# Did the user mean it's missing for SOME rows? Or they just want to make sure it's populated?
# Let's check how many rows are missing images or ratings.

print(f"Missing image: {merged['image'].isna().sum()}")
print(f"Missing vote_average in df1: {df1['vote_average'].isna().sum()}")

# Let's save the merged one to see
merged.to_csv('merged_test.csv', index=False)
