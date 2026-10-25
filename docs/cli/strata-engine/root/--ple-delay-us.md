# `--ple-delay-us`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--ple-delay-us` |
| 別名 | なし |
| 値 | マイクロ秒単位の非負数（`double`） |

## 役割

PLE（Per-Layer Embedding）の行読み込み完了を意図的に遅らせる fault injection 用オプションです。通常動作の調整値ではなく、PLE の読み込み遅延を含む挙動を調べるための値です。ヘルプも「各行読み込みが U マイクロ秒より早く完了しない」と説明しています（`src/program/generate.cpp:825`）。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --ple-gguf /path/to/ple.gguf --ple-delay-us 1000
```

`1000` は各行読み込みに対する最小遅延を 1000 マイクロ秒にする例です。モデルと PLE テーブルを使う実行例であり、この調査では実行していません。コマンド形式は parser の usage に基づきます（`src/program/generate.cpp:806-808`）。

## 値と既定値

- 値は `std::atof` で `double` に変換されます。既定値は `0` で、遅延注入は行われません（`src/program/generate.cpp:484,2478`）。
- `0` は有効で、負数は後段 validation で拒否されます。NaN も `!(value >= 0)` に該当して拒否されます。一方、この validation は正の無限大を拒否しません（`src/program/generate.cpp:3181-3184`）。極端に大きな値は読み込み完了を長時間保留させるため、通常の値として使わないでください。
- `atof` のため、数値として解釈できない文字列は `0` に変換されて受理され得ます。厳密な数値形式検証はありません（`src/program/generate.cpp:2478`）。
- 同じオプションを複数回指定すると、parser が順に代入するため最後の値が残ります（`src/program/generate.cpp:2416-2421,2478`）。値を省略すると `--ple-delay-us needs a value` を標準エラーに出して終了コード 2 になります（`src/program/generate.cpp:2418-2420`）。

## 実行時の動作

PLE テーブルが構築されるとき、値が `0` より大きければ `PleTable` に注入値を設定します（`src/program/generate.cpp:4033-4040,4161-4164`）。PLE reader は実際の行読み込み完了を受け取った後、行の発行時刻から指定時間が経過していなければ完了を保留し、経過後に行データを確定します（`src/ngram/ple_reader.cpp:253-271,274-285`）。したがって、指定値は実ディスク読み込みを遅くする設定ではなく、完了通知を遅らせる fault injection です。

この値は PLE テーブルの利用が前提です。`--ple-gguf` などによって PLE テーブルが指定されず構築ブロックに入らない場合、このオプション値は reader に設定されません（`src/program/generate.cpp:4033,4163`）。`--no-ple` は別の PLE 無効化指定であり、このオプション自体が PLE を有効化することはありません（`src/program/generate.cpp:2473-2478,3290-3298`）。遅延値による専用の警告や出力経路は parser/reader の該当処理にはありません。

## 適用条件と副作用

遅延は PLE reader が完了した行読み込みに対して適用されます。 reader は保留した完了を後で処理し、その間は該当する行データの利用が待たされます（`src/ngram/ple_reader.cpp:108-109,253-285`）。実行時間や待ち時間が増える可能性があります。GPU、ネットワーク、ファイル生成への追加処理は、このオプションの実装箇所では確認できません。

## 出力とエラー

共通の PLE 設定 validation で負値または NaN が見つかると、標準エラーに `strata generate: invalid --ple-io/--ple-row-cache/--ple-inflight/--ple-delay-us` と出し、終了コード 2 で戻ります（`src/program/generate.cpp:3181-3184`）。値の欠落時も標準エラーと終了コード 2 です（`src/program/generate.cpp:2418-2420`）。遅延注入は完了を保留する処理であり、それ自体がエラーを生成する分岐は確認できません（`src/ngram/ple_reader.cpp:253-285`）。

## 根拠

- parser のヘルプ表記・既定値・値の読み込み: `src/program/generate.cpp:484,825,2416-2421,2478`
- 値の validation と失敗出力: `src/program/generate.cpp:3181-3184`
- PLE reader の構築設定と注入適用箇所: `src/program/generate.cpp:4033-4040,4161-4164`
- 読み込み完了の保留と解放: `src/ngram/ple_reader.cpp:253-285`
- 調査範囲: checkout の parser と PLE reader の実装を確認しました。同一 revision の CLI `--help` 実行、ビルド、テスト、GPU 実行、性能測定は行っていません。
