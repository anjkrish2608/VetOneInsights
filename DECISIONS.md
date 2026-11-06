# Decisions

## Repo setup
- **using github as repo**

- **.gitignore: Python template#.**
  Why: the template already covers `.env` and virtual environments
  Rejected: Node and Terraform templates (not relevant to this project).
  Change if: XX
- **No license.**
  Why: it's a case submission, so a license adds nothing.
  Change if: the code were meant to be reused.
- **Public repo.**
  Why: the brief asks for a link that opens without an invite.
  Change if: they'd prefer a zip, in which case I'd send that instead.
- **created `.env` and `.env.example`.**
  Why: need to keep client id and client secret hidden but wanted to show example of what the pipeline requires
  Change if: the client secrets can be made public
- **.gitignore: Added `data/` and `.env` .**
  Why:  `data/` keeps API pulls and the database out of git, as the brief asks for no data dumps. `.env`need to keep client id and client secret hidden
  Change if: I needed to share a small sample file with reviewers, in which case I'd add an exception for it.

## Language
- **Python & SQL.**
  Why:
  Rejected: 
  Change if: 
- **decision made**
  Why: XX
  Change if: XX

## Data Observations
- **Set timeout to 60 in `explore.py`**
  
- **Token response has no expiry field**
  Documentation says tokens expire but toke  response has no expiry field.
  Handling: on a 401 will need to fetch a new token and retry
