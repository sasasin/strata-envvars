# `--sync-every-layer`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ engine の root parser） |
| オプション | `--sync-every-layer` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

デバッグ用に、非 capture 実行時の各層の処理後に GPU stream を同期し、非同期 GPU エラーを発生した層の位置で検出しやすくします。エラーを後続の層や token 処理末尾で検出する代わりに、該当層の後で報告する用途です（`include/strata/core/session.hpp:117-120`、`src/core/session.cpp:834-844`）。

## 使い方

`strata generate` に指定します。`--sync-every-layer` の効果を有効にするには、各層を直接実行する `--no-capture` も指定します。

```sh
strata generate --pack PATH --tokens "1,2,3" --no-capture --sync-every-layer
```

エンジンの usage は `--pack DIR` と `--tokens LIST` を基本形として示しています（`src/program/generate.cpp:806-812`）。

## 値と既定値

値は不要です。parser はフラグを見つけると `Options::sync_every_layer` を `true` にし、初期値は `false` です。したがって未指定時は層ごとの同期を追加しません。複数回指定しても同じ bool を `true` にするだけです（`src/program/generate.cpp:507-510,2504-2507`）。

値の検証処理はありません。値を付けた `--sync-every-layer=...` などはこの parser のフラグ表記に一致せず、未知引数として扱われます（`src/program/generate.cpp:2787-2793`）。

## 実行時の動作

`session_token` はモデルの各層を順に処理し、`sync_every_layer` が真なら各層の処理成功後に `cudaStreamSynchronize` を呼びます。同期エラーがあれば、その層番号と CUDA のエラー文字列を `err` に設定して失敗を返します（`src/core/session.cpp:805-807,812-844`）。

この値が `session_token` に渡されるのは、`--no-capture` が有効な分岐だけです。capture 経路は `session_run_token` または `session_loop` を使い、このフラグを渡しません。そのため `--no-capture` なしで指定しても同期は追加されず、ソース上では警告も出しません（`src/program/generate.cpp:15932-15945`）。両方を指定する例では、`--no-capture` が直接実行経路を選び、このフラグがその各層後の同期を有効にします。

## 適用条件と副作用

- 対象となるのは `--no-capture` による直接実行経路です。capture 実行では効果がありません（`src/program/generate.cpp:15932-15945`）。
- 有効時は層ごとに GPU stream の完了を待つため、通常の非同期実行に同期と待ち時間が加わります。ヘッダーの説明でも、fast path では行わないデバッグ用同期として位置づけています（`include/strata/core/session.hpp:117-120`）。
- このフラグ自体はファイルやネットワークを操作しません。同期・エラー検査は `session_token` の層ループ内で行います（`src/core/session.cpp:812-844`）。

## 出力とエラー

`session_token` が失敗すると、呼び出し元は標準エラーに `strata generate: session_token: ...` を出して終了コード `1` を返します。層後の同期エラーではメッセージに `layer N:` と CUDA エラー文字列が含まれます（`src/core/session.cpp:839-842`、`src/program/generate.cpp:15933-15937`）。

未対応の表記など未知の引数は標準エラーに `unknown argument: ...` と usage を出して終了コード `2` になります（`src/program/generate.cpp:2787-2793`）。

## 根拠

- `src/program/generate.cpp:507-510,806-812,967-969` — option state の初期値、usage、help 表記。
- `src/program/generate.cpp:2504-2507,2787-2793` — parser の受理と未知引数のエラー経路。
- `src/program/generate.cpp:15932-15945` — `--no-capture` 分岐でのみ値を渡す実行経路。
- `include/strata/core/session.hpp:117-123`、`src/core/session.cpp:805-844` — option の意味、各層後の stream 同期、エラー伝播。
- SYCL 実装にも同名 option の parser と同様の `--no-capture` 分岐があります（`sycl/src/program/generate.cpp:490-495,1845-1849,12173-12179`、`sycl/src/core/session.cpp:1146-1149,1176-1184`）。この文書の主な根拠は索引の対象境界に従い `src/program/generate.cpp` の parser と CUDA 実装です。
