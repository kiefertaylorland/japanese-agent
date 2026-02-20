# Vocab Schemas

All vocab files are UTF-8 JSON arrays.

## `data/hiragana.json` and `data/katakana.json`

```json
[
  {"kana": "あ", "romaji": "a"},
  {"kana": "きゃ", "romaji": "kya"}
]
```

## `data/kanji_N5.json`, `data/kanji_N4.json`, `data/kanji_N3.json`, `data/kanji_N2.json`

```json
[
  {"kanji": "日", "meaning": ["sun", "day"]},
  {"kanji": "本", "meaning": ["book", "origin"]}
]
```

`meaning` may be a string or list of strings; it is normalized to a list.

## `data/keigo_basic.json`

```json
[
  {
    "base": "言う",
    "keigo": "申し上げる",
    "type": "kenjogo",
    "meaning": "to say (humble)",
    "usage": "business",
    "example_contexts": ["email", "meeting"]
  }
]
```

`type` must be one of `sonkeigo`, `kenjogo`, `teineigo`.
