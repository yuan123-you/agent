ALTER TABLE user_address
  ADD COLUMN province VARCHAR(64) NULL AFTER receiver_phone,
  ADD COLUMN city VARCHAR(64) NULL AFTER province,
  ADD COLUMN district VARCHAR(64) NULL AFTER city,
  ADD COLUMN detail_address VARCHAR(255) NULL AFTER district;
