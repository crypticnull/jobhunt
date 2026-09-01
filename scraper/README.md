# scraper

ATS pollers, scoring, the postings store and the weekly digest. Built in
milestones 2 through 4, widened in milestone 9. Python 3.12, standard
library only (ADR-0004). `scraper/store.py` will be the only writer of
`data/local/postings.db`.
