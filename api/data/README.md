# Training data

sms.tsv is the existing 5,572-row SMS Spam Collection supplied with this project.
It uses two tab-separated columns: ham/spam and text.

Source: [UCI SMS Spam Collection](https://archive.ics.uci.edu/dataset/228/sms+spam+collection).
Attribution: Tiago A. Almeida and Jose Maria Gomez Hidalgo, SMS Spam Collection (2011),
DOI [10.24432/C5CC84](https://doi.org/10.24432/C5CC84).
UCI lists the dataset under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The file is preserved as supplied; training performs normalization, deduplication and label-conflict removal in memory.
Its SHA-256 is recorded in each model's metrics.json.
Synthetic Indian examples are generated from app/indian_data.py; no user submissions are used for training.

This corpus labels spam, not all forms of scams. The synthetic examples are educational templates, not independently verified fraud reports.
