import pandas as pd

# Load the two datasets
file_wisata = 'wisata_jogja.csv'
file_sekitar = '../../dataset-wisata-jogja-sekitar.csv'

df_wisata = pd.read_csv(file_wisata)
df_sekitar = pd.read_csv(file_sekitar)

# We want to add the 'image' column to df_wisata based on 'nama'
# df_wisata already has 'vote_average' and 'vote_count', but we will update them just in case
# or keep the ones from df_wisata if they exist.
# Let's just pull 'image' from df_sekitar

# Create a mapping from nama -> image
# To be safe against minor capitalization differences, we map using lowercase
image_map = dict(zip(df_sekitar['nama'].str.lower().str.strip(), df_sekitar['image']))
rating_map = dict(zip(df_sekitar['nama'].str.lower().str.strip(), df_sekitar['vote_average']))
vote_count_map = dict(zip(df_sekitar['nama'].str.lower().str.strip(), df_sekitar['vote_count']))

# Apply the mapping
df_wisata['image'] = df_wisata['nama'].str.lower().str.strip().map(image_map)

# For ratings, if the user wants them added/updated:
# If vote_average doesn't exist or we want to overwrite with df_sekitar's data:
df_wisata['vote_average'] = df_wisata['nama'].str.lower().str.strip().map(rating_map).fillna(df_wisata['vote_average'])
df_wisata['vote_count'] = df_wisata['nama'].str.lower().str.strip().map(vote_count_map).fillna(df_wisata['vote_count'])

# Check if any are still missing images
missing_images = df_wisata['image'].isna().sum()
print(f"Images missing after mapping: {missing_images}")

# Save back to wisata_jogja.csv
df_wisata.to_csv(file_wisata, index=False)
print("Berhasil menambahkan kolom image dan update rating ke wisata_jogja.csv")
