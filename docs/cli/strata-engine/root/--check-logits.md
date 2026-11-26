# `strata --check-logits`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（通常の推論 engine parser） |
| オプション | `--check-logits` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

`--stream-token` を使う推論で、各生成位置の全語彙 logits をホストへ読み戻し、非有限値（NaN / ±Inf）を検出します。stream-token を使わない通常経路では logits の読み戻しと検査が元から有効なので、このフラグを追加しても検査範囲は変わりません（`engine/src/program/generate.cpp:24358-24372`）。

## 使い方

```sh
strata --pack model.gguf --stream-token --check-logits
```

`--pack` には推論対象の pack を指定します。`--check-logits` 自体に引数はありません（`engine/src/program/generate.cpp:1230-1244, 3851-3852, 3910-3912`）。

## 値と既定値

- 値を取らず、parser は指定されたとき `o.check_logits = true` にします。既定値は `false` です（`engine/src/program/generate.cpp:776-777, 3910-3912`）。
- 繰り返し指定を拒否する分岐はなく、複数指定しても同じ真偽値を `true` にするだけです（`engine/src/program/generate.cpp:3910-3912`）。
- 値の validation はありません。値を続けて書く構文はこのフラグの引数として消費されず、後続の引数として処理されます。未認識の引数は usage を表示して終了コード `2` になります（`engine/src/program/generate.cpp:3842-3847, 4268-4274`）。

## 実行時の動作

各生成位置で、実装は `read_logits = !o.stream_token || o.check_logits || emit_logits` を判定します。したがって stream-token 経路ではこのフラグが全位置の読み戻しを有効にし、選択位置だけを出力する `--dump-logits` が併用されている場合も、dump 選択の有無とは別に全位置を検査します（`engine/src/program/generate.cpp:24358-24372`）。通常経路では `!o.stream_token` が真のため、フラグなしでも読み戻しと検査が行われます。

CUDA 実装は語彙数分の float logits を device-to-host コピーし、token stream を同期した後、各値に `std::isfinite` を適用します。SYCL 実装も同じ条件でコピーと queue wait を行ってから同じ有限値検査をします（`engine/src/program/generate.cpp:24360-24372`; `engine/sycl/src/program/generate.cpp:13585-13607`）。この追加読み戻しは stream-token の非同期処理に同期点を加え、全 logits のホスト走査を行います。

`--native` の通常 engine preset は `o.stream_token = true` に設定します。その経路でも `--check-logits` を指定すれば全位置の読み戻し・検査が有効です（`engine/src/program/generate.cpp:5160-5165`）。

## 適用条件と副作用

このオプションの効果が追加されるのは通常 engine parser の stream-token 経路です。フラグなしの stream-token 実行は、dump 対象位置を除いて logits のホスト読み戻しを省略します（`engine/src/program/generate.cpp:24358-24372`）。

Qwen3.6 family は通常 parser より前に専用 engine へ振り分けられます。専用 parser はこのフラグを登録しておらず、通常実行では未認識引数として usage を出して終了コード `2` にします。serve mode では未対応オプションを stderr に無視すると出力します（`engine/src/program/generate.cpp:3804-3818`; `engine/src/qwen35/q36_engine.cu:5339-5358, 5405-5418`）。索引上も Qwen3.6 は別の `qwen36/` scope です（`docs/cli/README.md:1240-1244`）。

## 出力とエラー

- logits の device-to-host 読み戻しまたは同期に失敗すると、`strata generate: reading the logits back failed` を stderr に出し、終了コード `1` を返します（CUDA: `engine/src/program/generate.cpp:24361-24365`; SYCL: `engine/sycl/src/program/generate.cpp:13594-13600`）。
- 非有限値が1つ以上あれば、個数・語彙数・生成位置を stderr に出し、終了コード `1` を返します（CUDA: `engine/src/program/generate.cpp:24367-24372`; SYCL: `engine/sycl/src/program/generate.cpp:13601-13607`）。
- 正常時、このフラグ固有のメッセージは出力しません。

## 根拠

- `engine/src/program/generate.cpp:776-777, 1242-1244, 3910-3912` — 通常 engine parser の状態、help 表記、フラグ設定。
- `engine/src/program/generate.cpp:24358-24372` — 読み戻し条件、CUDA 同期、有限値検査と失敗経路。
- `engine/sycl/src/program/generate.cpp:13585-13607` — SYCL 実装の同等処理。
- `engine/src/program/generate.cpp:3804-3818`; `engine/src/qwen35/q36_engine.cu:5339-5358, 5405-5418` — Qwen3.6 専用 parser への振り分けと未対応引数処理。
