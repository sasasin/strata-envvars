# `--verify-hash`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（CUDA/HIP） |
| オプション | `--verify-hash` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

`--selfcheck` と併用すると、モデルを開いた後、backend の初期化・selfcheck より前に `.strata` モデルの Section 0〜5 の SHA-256 を照合します。モデルを破損していないか確かめる用途です。parser はこのフラグ単独でも受理しますが、selfcheck 以外の実行モードではハッシュ検証に使われません。

## 使い方

```sh
strata-inkling --selfcheck --native ./model.strata --verify-hash --cpu
```

モデルを開き、ハッシュを照合した後、CPU backend の selfcheck まで実行します。`--cpu` を省略すると backend 選択は既定の実装に委ねられます。

## 値と既定値

値は不要です。指定すると真になり、未指定時は偽です。重ねて指定した場合も同じ真偽値を設定するだけです。parser にこのフラグ固有の値検証はありません。次の引数を値として消費しないため、後続引数は通常どおり別 option として解析されます。(`engine/src/inkling2/ink_main.cpp:374,379-400`)

## 実行時の動作

- `--selfcheck` の処理では、`--native`（alias `--model`）でモデルパスが指定されている場合にモデルを開きます。`--verify-hash` が有効なら Section 0〜5 の検証メッセージを stdout に出し、検証に失敗した時点で stderr に失敗理由を出して終了コード 1 を返します。成功後は backend 初期化と backend selfcheck に進みます。(`engine/src/inkling2/ink_main.cpp:101-127`)
- `.strata` 形式の場合、Section 0 から `STRATA_NUM_SECTIONS - 1` まで順に処理し、Section 4 を含め、長さ 0 の section は飛ばします。各 section の内容を最大 8 MiB のバッファで読み込み、ヘッダーに記録された SHA-256 と照合します。読み取り失敗は失敗として返し、ハッシュ不一致時の理由は `SHA-256 mismatch in Section <番号>` です。(`engine/src/inkling2/ink_manifest.h:339,532-555`)
- safetensors と GGUF は `InkModelFile::open` で形式別 adapter に振り分けられます。その場合 `verify_sections` は SHA-256 を計算せず `true` を返します。コードコメントではこれらの入力は open 時に header/bounds 検証されるとしていますが、`--verify-hash` による内容ハッシュ照合は行いません。(`engine/src/inkling2/ink_manifest.h:454-477,532-534`)
- `--selfcheck` を伴わない場合、フラグは保存されますが他の処理から参照されません。`--info` や `--export-tokenizer` は selfcheck より先に dispatch されるため、これらと同時指定してもハッシュ検証は実行されません。(`engine/src/inkling2/ink_main.cpp:388-400,544-549`)
- `--selfcheck` を指定し、モデルパスを省略した場合はモデル open とハッシュ検証を行わず、backend selfcheck に進みます。parser は `--verify-hash` にモデル必須の validation を設けていません。(`engine/src/inkling2/ink_main.cpp:101-127,551-553`)

## 適用条件と副作用

この option のハッシュ照合対象は `.strata` 入力だけです。照合はモデルファイルの各対象 section を読み取りますが、検証処理自体によるファイル書き換えはありません。照合成功後も `--selfcheck` は backend の初期化と selfcheck を実行し、backend の選択によってはデバイス処理を伴います。(`engine/src/inkling2/ink_manifest.h:532-555`; `engine/src/inkling2/ink_main.cpp:117-126`)

ハッシュ検証が selfcheck のみに適用されること、対象モデル形式が `.strata` のみであることはコードから確認できます。一方、section header のハッシュ値がどの段階で生成・信頼されるかは、この option の実装箇所だけでは確認していません。

## 出力とエラー

- 照合開始時: stdout に `[selfcheck] Verifying SHA-256 of Sections 0..5...` を出します。
- ハッシュ不一致または section 読み取り失敗時: stderr に `[selfcheck] FAIL hash: <理由>` を出し、終了コード 1 を返します。
- 検証成功後、selfcheck 全体が成功すると stdout に `[selfcheck] PASS backend=<名前> (<デバイス情報>)` を出します。hash 成功時の専用成功メッセージはありません。
- モデル open 失敗、backend 初期化失敗、backend selfcheck 失敗もそれぞれ stderr に `[selfcheck] FAIL ...` を出し、終了コード 1 です。(`engine/src/inkling2/ink_main.cpp:105-126`)

## 根拠

- `engine/src/inkling2/ink_main.cpp:373-400` — 既定値と parser 登録。値を取らない真偽フラグ。
- `engine/src/inkling2/ink_main.cpp:101-127` — selfcheck 内でのモデル open、hash 検証、backend 初期化・selfcheck、出力と失敗処理。
- `engine/src/inkling2/ink_main.cpp:488-497,544-553` — help 表示、selfcheck を含む実行モードの dispatch 順、モデル未指定時の通常経路。
- `engine/src/inkling2/ink_manifest.h:454-477` — `.strata` / safetensors / GGUF の形式判定と open 経路。
- `engine/src/inkling2/ink_manifest.h:532-555` — 対象形式、section の走査、空 section の扱い、SHA-256 照合とエラー。
