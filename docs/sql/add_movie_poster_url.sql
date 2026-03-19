-- Add poster URL field for movie cards.
ALTER TABLE movie
ADD COLUMN IF NOT EXISTS poster_url VARCHAR(512) NULL;
