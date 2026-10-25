# `--spec-oracle`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの root。内部の生成処理名は `generate`） |
| オプション | `--spec-oracle` |
| 別名 | なし |
| 値 | token ID 列を記録したテキストファイルのパス |

## 役割

speculative decoding の verify window で、通常の draft 供給元の代わりにファイル内の token ID を使います。ソースコメントは「期待 continuation を使う exactness test」と説明しており、通常利用向けの生成設定ではなく、推測デコードの検証・比較用の入力です（`src/program/generate.cpp:650-652`）。

## 使い方

```sh
strata --model model.gguf --tokens 1,2,3 --max-new 32 --spec 4 --spec-oracle expected-ids.txt
```

`--spec` が正の値で speculative loop が動く実行経路で指定します。実際に使うにはモデルと prompt token IDs など、エンジンが要求する他の入力も必要です。

## 値と既定値

- 値はファイルパスです。相対パスはプロセスの作業ディレクトリを基準に解決されます（`std::ifstream` にそのまま渡します。`src/program/generate.cpp:16103-16107`）。
- ファイル内容はカンマまたは空白で区切った整数 token ID の列です。各値は `0` 以上 `2147483647` 以下でなければならず、空の列は拒否されます（`src/program/generate.cpp:1097-1114`）。
- この読み取り処理では token ID の上限を整数型の範囲まで確認しますが、モデルの語彙数との照合はしていません（`src/program/generate.cpp:1097-1114`）。
- 省略時は空文字列で、oracle ファイルを読みません（`src/program/generate.cpp:671`）。同じオプションを複数回指定すると parser の代入により最後のパスが残ります（`src/program/generate.cpp:2619`）。
- `--spec` の既定値は Metal build で `2`、それ以外で `0` です。`--spec` が `0` 以下なら speculative loop に入らず、このオプションのファイルも読みません（`src/program/generate.cpp:653-657,16091-16092`）。

## 実行時の動作

speculative loop に入るとファイル全体を読み込み、読み取りまたは整数列の解析に失敗した場合は `strata generate: cannot read --spec-oracle <path>` を stderr に出して終了コード `2` で戻ります（`src/program/generate.cpp:16102-16112`）。ファイルは読み取り専用で開かれます。

verify window の各 draft 位置では、suffix draft を選んでいれば suffix の値、MTP が有効なら MTP の draft、それ以外では oracle 列の値を使います。oracle 値は生成済み continuation の位置に対応して参照されます。列が必要な位置まで届かない場合は token ID `0` を draft として補います（`src/program/generate.cpp:16591-16598`）。モデルの verify 結果と draft が一致する範囲が受理され、最初に異なる位置で window の出力が決まります（`src/program/generate.cpp:16646-16647,16668-16686`）。したがって、MTP または suffix draft が選ばれる場合、その箇所では oracle が優先されるわけではありません。

## 適用条件と副作用

- 通常の `src/program/generate.cpp` parser では受理されますが、値の形式検査とファイルアクセスは speculative loop に進んだ場合だけです。`--spec` が無効、生成上限に到達、または loop が開始されない場合、ファイル指定が不正でもこの経路では検査されません（`src/program/generate.cpp:16091-16112`）。
- Qwen3.6-35B family は model header による切替後、`src/qwen35/q36_engine.cu` の独自 parser に渡ります。同 parser に `--spec-oracle` の処理はなく、通常の生成モードでは未知 option として usage を出して終了コード `2` になります。serve mode では独自 parser が未知の `--` option を警告して読み飛ばす経路があります（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3735-3795`）。
- 読み取った値は token file のみを参照し、Strata がそのファイルを書き換える処理は確認できません。生成出力は通常どおり標準出力に prompt と出力 token ID 列、生成統計を表示します（`src/program/generate.cpp:16867-16875`）。

## 出力とエラー

- 値の欠落は parser の `next()` が `<option> needs a value` を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:2416-2421`）。
- ファイルを開けない場合、または内容が空・整数列として不正の場合は、`cannot read --spec-oracle <path>` を stderr に出して終了コード `2` です。解析関数が返す詳細理由（不正な token ID／空列）はこの option のエラー表示には含まれません（`src/program/generate.cpp:1097-1114,16103-16112`）。
- speculative verify や commit 自体の失敗は別の実行エラー経路で stderr に出力され、終了コード `1` で戻ります（`src/program/generate.cpp:16609-16620,16668-16673`）。

## 根拠

- parser と option state: `src/program/generate.cpp:650-657,671,2619`。
- token 列の形式検査: `src/program/generate.cpp:1097-1114`。
- ファイル読み込みと失敗処理: `src/program/generate.cpp:16102-16112`。
- draft 値の選択、verify、受理・出力: `src/program/generate.cpp:16591-16598,16609-16620,16646-16647,16668-16686`。
- Qwen3.6 family への切替と別 parser: `src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3735-3795`。
