# `--gpu-stages`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--gpu-stages` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

モデルの通常生成を行わず、層ごとに分けた GPU graph を再生し、`mixer`、`ffn front + router`、`post` の時間を計測します。さらに mixer の層種別ごとの内訳などを標準出力へ表示します。これは診断用の計測モードで、実際の推論速度を測る通常実行とは目的が異なります（`src/program/generate.cpp:597-600,985-987,7136-7169`）。

## 使い方

```sh
strata generate --pack DIR --tokens "1,2,3" --gpu-stages
```

`--pack` はモデルの pack ディレクトリ、`--tokens` はカンマ区切りの入力 token ID です。どちらかの入力方法が必要です（`src/program/generate.cpp:806-812`）。例の `DIR` と token ID は手元のモデルに合わせてください。

## 値と既定値

- 値や引数を取りません。parser は指定されると `gpu_stages = true` にし、初期値は `false` です。未指定ならこの計測分岐は実行されません（`src/program/generate.cpp:597-600,2753`）。
- parser に値の範囲検証はありません。同じフラグを繰り返しても真にするだけです（`src/program/generate.cpp:2753`）。フラグの後ろに別の値を置く構文は定義されていません。

## 実行時の動作

指定すると graph capture 時に `split=true` を渡し、各層の処理を mixer、FFN 前半＋router、post に分けて capture します。続いて各層の graph を順に再生し、GPU event の区間時間から集計します（`src/program/generate.cpp:6952-6962`; `src/core/session.cpp:205-223,332-376,379-386`）。CUDA/HIP の実装では主な集計を20回行い、平均 ms/token、ms/layer、比率などを表示します（`src/program/generate.cpp:7149-7169`）。

計測分岐は capture 後、通常の生成ループへ進む前に実行され、終了コード 0 でプロセスを終えます。出力先ファイルを指定するオプションではなく、この分岐自身はファイルやネットワークへ出力しません。GPU 上では graph capture と replay を実行し、セッションの計測用状態を使います（`src/program/generate.cpp:7136-7147,7277-7283`）。

## 適用条件と副作用

- `--layer-split` で複数 GPU に層を分ける構成とは併用できません。検出時はモデル読み込み前の validation で拒否されます。単一の全層セッションで再生する計測のためです（`src/program/generate.cpp:3386-3392`）。
- `--native-flash-attn-short` とも併用できません。この計測モードは通常 decode loop の status validation を通らないため、組み合わせると拒否されます（`src/program/generate.cpp:3378-3384`）。
- `--no-capture` も指定すると graph capture が省略されます。既定の pool 設定では先に `--no-capture` の validation が終了コード 2 で拒否します。`--no-pool` も指定してその検査を通した場合は、後段の stage replay が split graph 未 capture のエラーで終了コード 1 になります。`--gpu-stages` との専用 validation はありません（`src/program/generate.cpp:6954-6962,6974-6979,7137-7147`; `src/core/session.cpp:332-337`）。
- native (IQ) pack では per-layer graph を capture しないため、この計測は利用できません。replay 失敗となり、serve 経路で `STRATA_VERIFY_PROFILE=1` と `STRATA_DECODE_TIMING=1` を使う代替案が stderr に案内されます（`src/program/generate.cpp:3753-3765,6954-6962,7140-7147`; [DETAILS.md「Where a decode window's time goes」](../../../DETAILS.md#where-a-decode-windows-time-goes)）。
- `--gpu-stages` が有効なときは fused GR kernel を無効にし、計測に使う非 fused の layout を選びます。したがってこの出力は、その fused 経路の性能値を表しません（`src/program/generate.cpp:3924-3931`）。
- capture・replay とイベント計測で GPU を使用し、計測用 graph と状態を確保します。通常生成を実行せずに終了します。計測は複数回 replay するため、負荷や時間を要しますが、性能測定や実機実行は本調査では行っていません。

## 出力とエラー

成功時は標準出力に `per-stage GPU time on the CAPTURED graph` の表、各 stage の ms/token・ms/layer・比率、合計などを表示して終了コード 0 を返します（`src/program/generate.cpp:7160-7169,7277-7283`）。

失敗時は標準エラーへ理由を出します。相互作用の validation エラーは終了コード 2 です（`src/program/generate.cpp:3378-3392`）。capture または stage replay の失敗はエラー文を出して終了コード 1 です。native pack では per-layer graph がない旨と serve 経路の代替設定も追加表示します（`src/program/generate.cpp:6958-6962,7140-7147`）。GPU event 作成、graph launch、最終同期の失敗は `session_replay_stages_per_layer` が失敗として返します（`src/core/session.cpp:345-364`）。

## 根拠

- parser の既定値・help 表示・フラグ設定: `src/program/generate.cpp:597-600,985-987,2753`。
- graph capture と split の指定: `src/program/generate.cpp:6952-6962`、capture の split graph 生成: `src/core/session.cpp:205-223,231-253`。
- GPU event による計測、集計、出力・正常終了: `src/core/session.cpp:332-386`、`src/program/generate.cpp:7136-7169,7277-7283`。
- 適用制限と fused GR への影響: `src/program/generate.cpp:3378-3392,3924-3931`。
- SYCL 実装でも同じフラグを parser が受理し、split capture と stage replay を行います: `sycl/src/program/generate.cpp:5469-5479,5681-5691`、`sycl/src/core/session.cpp:194-219,413-495`。本調査では既存 CLI の help 実行、ビルド、GPU/SYCL 実行、テストは行っていません。
