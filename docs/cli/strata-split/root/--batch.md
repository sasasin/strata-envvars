# `strata-split --batch`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（N は build 対象カード数 2 / 3 / 4） |
| オプション | `--batch` |
| 別名 | なし |
| 値 | 整数。1〜8 |

## 役割

sFNX engine が保持する要求 slot 数を指定します。複数 slot を有効にすると、複数の decode 要求を同じ window に載せて処理するプロトコル `BGEN` / `BGENI` を使えます。この値は同時要求数の厳密な上限やスケジューラ設定ではなく、engine の slot/lane 数です。

## 使い方

```sh
strata-split-2 --serve --native model.gguf --mtp /path/to/mtp --batch 4
```

`--serve`、`--native`、`--mtp` は必須です。実際の実行ファイル名は build 対象と GPU によって異なります。CMake は `strata-split-2/3/4` target を生成し、配布名は NVIDIA で `strata-split-N-sm<cc>`、AMD で `strata-split-N-<arch>` です。

## 値と既定値

- 省略時は `1` です。
- `1` から `8` までを受理します。上限 `8` は `sfnx_input.hpp` の `MAX_SLOTS` です。
- parser は `std::stoi` で値を整数化し、範囲外なら `--batch must be 1..8` 相当のエラーにします。値がない場合は `--batch needs a value` で失敗します。整数に変換できない値や整数範囲を超える値も例外経路になります。`std::stoi` の呼び出しでは消費文字数を検査しないため、数値の後ろに変換不能な文字が続く値は整数部分として解釈されます。
- 同じオプションを複数回指定した場合、parser は都度同じフィールドに代入するため最後の値が使われます。

## 実行時の動作

起動時に `--batch` の値で slot 配列を作り、slot 0 の lane/session を作成します。追加 slot についても lane を初期化し、engine に渡した lane 数に応じて K/V pool の追加ページを確保します。値が 1 より大きく、かつ `FNX_BATCH_DRAFTS` が batch draft を無効にしていない場合は batch decoder も作ります。いずれの場合も起動時に graph を warm up します。そのため値を大きくすると、最初の要求より前に必要な GPU/host 資源が増え、起動時確保や初期化が失敗する可能性があります。値に比例した性能向上や同時処理保証はソースからは確認できません。

`--batch 1` は有効な値ですが、batch 要求は有効になりません。`BGEN` / `BGENI` 行は `ERR ...: sfnx runs without --batch` として拒否されます。2 以上では各 slot が lane となり、slot ごとの要求を共有 decode window で進めます。起動時の `INFO` に `batch_slots=<値> slot_cache=1` が追加されます。

## 適用条件と副作用

- `strata-split` の serve 起動時に適用されます。通常の `GEN` と batch 用の `BGEN` は異なる入力プロトコルです。batch で使う slot 番号は 0 始まりで、存在しない slot や使用中 slot への要求は拒否されます。
- この値は `--native` のモデルやカード数を変更しませんが、lane 数を engine に渡し、K/V pool のページ数に反映されます。実際の資源量は model、context、build、GPU 状態に依存します。
- `--batch` は server 起動に必要な `--serve`、`--native`、`--mtp` と併用します。`--serve` がない、または必須パスが欠けると起動前に失敗します。

## 出力とエラー

- 引数の不足・不正値、`--serve` の欠落、必須の `--native` / `--mtp` の欠落、範囲外の batch 数は stderr に `sfnx: <理由>` を出して終了コード 2 になります。
- model / MTP / engine / lane 初期化中の例外は、protocol stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` を出し、終了コード 1 で終了します。
- `--batch 1` で `BGEN` 系 protocol 行を送った場合は、起動後に stdout へ `ERR BGEN: sfnx runs without --batch` 相当を出して要求を続行せず、プロセス自体はその経路では終了しません。

## 根拠

- parser、既定値、必要引数、整数変換、範囲検査: `src/split/tools/sfnx.cpp:65-104`。
- 最大 slot 数: `src/split/tools/sfnx_input.hpp:15-17`。
- slot/lane の生成、batch decoder の条件、graph 初期化: `src/split/tools/sfnx.cpp:435-445`。
- engine lane 数と K/V pool 追加ページ数: `src/split/src/engine.cu:31,70-80`。
- batch protocol の有効条件と拒否出力: `src/split/tools/sfnx.cpp:961-1002`。
- 起動時 INFO、READY、初期化失敗の終了経路: `src/split/tools/sfnx.cpp:1030-1089`。
- `strata-split-N` target 名と N の build 制約: `src/split/CMakeLists.txt:92-97`。

## 調査範囲と制約

この文書は指定 revision のソースを調査したものです。同一 revision の既存 `strata-split` バイナリや Release artifact は実行・照合していません。GPU 資源の実消費量や実機上の性能差は測定していません。
