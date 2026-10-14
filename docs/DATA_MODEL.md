# Data model

strio's data model is the contract between every module that uses it: the EPG-Renderer,
planned statistics modules and future format readers and writers. This page describes
it and records the design decisions behind it.

```text
Dataset
├── source: SourceInfo        format, path, encoding, delimiter, header, extra columns
├── diagnostics: (Diagnostic, ...)
└── samples: {id: Sample}     source order
     └── loci: {marker: Locus}     source order, keyed by exported marker name
          ├── key, dye, extra, line
          └── alleles: (Allele, ...)   increasing index
               └── label, value, height, size_bp, area, mutation, comment
```

## Types

| Type | Fields | Invariants |
| --- | --- | --- |
| `Allele` | `index`, `label`, `height`, `size_bp`, `area`, `mutation`, `comment`; derived `value` | `index` ≥ 1; non-blank `label`; `height`, `area` whole numbers ≥ 0 or `None`; `size_bp` finite `Decimal` ≥ 0 or `None`; blank text → `None` |
| `Locus` | `marker`, `dye`, `alleles`, `extra`, `line`; derived `key` | non-blank `marker`; allele indexes unique and increasing; `extra` string → string |
| `Sample` | `id`, `loci`, `display_name`, `sample_name`, `sample_file`, `source_sample_id`, `run_name` | non-blank `id`; mapping keys equal `Locus.marker`; no two loci equal ignoring case and whitespace; `display_name` defaults to `id` |
| `SourceInfo` | `format`, `header`, `delimiter`, `sample_id_column`, `path`, `encoding`, `extra_columns` | non-empty header without blank names; one-character delimiter |
| `Dataset` | `samples`, `source`, `diagnostics` | mapping keys equal `Sample.id` |
| `AlleleValue` | `kind`, `number` | `number` only for `NUMERIC`, finite and ≥ 0 |
| `Diagnostic` | `code`, `message`, `lines` | non-blank message; lines ≥ 1 |

All types are frozen dataclasses. Constructors copy their inputs; mappings are exposed
as read-only views. An object that exists is valid.

## Design decisions

**Exported text stays authoritative.** `Locus.marker` and `Allele.label` are exactly
what the file says. Normalised forms (`Locus.key`, `Allele.value`) are derived alongside
and can be recomputed; they never replace the source. A converter can therefore write
back what it read.

**Missing is `None`, never `0`.** A height of `0` and an absent height mean different
things in casework.

**Nothing is guessed.** An allele label that is not clearly a repeat number, `X`, `Y`
or `OL` is `AlleleKind.OTHER`. Marker synonyms are an explicit, short list
(`MARKER_SYNONYMS`), not fuzzy matching. Two loci that share a key make
`Sample.locus()` raise instead of choosing.

**Extras live where they are in the file: on the row.** A column such as `Panel` may
describe the whole sample in one export and differ per row in another. Storing extras
per row keeps the model the same for every file; `Sample.common_extra()` checks the
"same in every row" condition explicitly when a caller needs a sample-level value.
Numbered uninterpreted columns (`Data Point n`) are row extras too; `Locus.indexed_extra`
pairs them with an allele. They are not attached to alleles automatically, because a
numbered column is not necessarily allele-bound, and failing on a column strio does not
understand would block files that are otherwise readable.

**No instrument or kit knowledge.** Height ceilings, kit panels, ladders, dye colours
and thresholds belong to the programs that use the data. The reader accepts an optional
`max_height` because a ceiling is easy to enforce while reading and gives precise line
numbers.

**Sample identity is the injection, not the name.** See the
[GeneMapper reader reference](GENEMAPPER.md#sample-identity).

## Planned extensions

These are not part of 0.1.0. They are listed so that nobody builds on assumptions that
would contradict them.

- Reading GeneMapper reference-profile exports (needs a real example export).
- Deriving a genotype (one or two alleles per locus) from a locus for kinship
  statistics, with explicit handling of more than two alleles and off-ladder calls.
- Combining several datasets of one person (different kits, replicates).
- Writing formats (GeneMapper table first).
