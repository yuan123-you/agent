# Sampled catalog records

Each populated category was inspected against its public source page. Records below were
selected deterministically (first record per category in the emitted manifest) and each was
verified to exist at the recorded `source_url` with matching name/brand/price/SKU semantics
and a content-addressed WebP image present in MinIO (`aimall/catalog/<sha256>.webp`).

| Category | Sample key (source / source_product_id) | Name | Brand | Currency/Price | Image sha256 |
| --- | --- | --- | --- | --- | --- |
| PHONE | www.apple.com / FTP13ZD/A | Refurbished iPhone 15 128 GB - Pink (ohne Vertrag) | Apple | EUR 719.00 | 4bae94c3d4eb3cffcb978a251cadf24ea699408bcfbb78a5f6488f634e53abf1 |
| DIGITAL | www.apple.com / MUVT3ZE/A | 20W USB-C Power Adapter | Apple | AED 79.00 | 6837f124d909e2e18c6127321d1fe9e1b2338052ab6a505c7fb6e2c8a29da321 |
| COMPUTER | www.apple.com / G1H71FN/A | MacBook Air 13 pouces reconditionné avec puce Apple M4 | Apple | EUR 1339.00 | 0e8f323336fbc105b57ffe49da8c3a07f22d9ccb907f1ee48fadc2b65236609a |
| CLOTHING | www.adidas.com / DV2872 | 3-Stripes Pants | adidas | KWD 8.80 | d54f4463163a123483b5e2a516088db7f1482814479d94d53795d5ee74edd8d1 |
| SHOES | www.adidas.com / FY8861 | COMFORT SANDAL I | adidas | USD 30.90 | 1bedeae08ca4a6380821136683fda1fb72efa34acedb25a29f05ee33c3e6cd77 |
| BAGS | www.adidas.com / IT2184_500 | AP/Syst. Backpack | adidas | BHD 32.25 | 832ede2259b37213c0ab8f91328b3bcc3240e670e19a706d327fcf2de86878fe |
| SPORTS | www.adidas.com / IL7271 | 3-Stripes Swim Leggings | adidas | BHD 35.50 | 376f10f323187681bac1d8186b86f7384d9143d363ad80b6bef993241951e2c7 |
| JEWELRY | www.apple.com / MXMC3FE/A | 42-mm Gold Link Bracelet | Apple | AUD 549.00 | 5a875bbdc047f350330e47b13b2056cb6a9563c68d3bf6966dc6a841fe11a8db |

Populated categories: PHONE, DIGITAL, COMPUTER, CLOTHING, SHOES, BAGS, SPORTS, JEWELRY (8 of 21).
