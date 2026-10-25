# `--prefill-head-alias`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されなかった。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ビルド実行ファイル `strata`） |
| オプション | `--prefill-head-alias` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は無効 |

## 役割

`--serve` 中、ネイティブ出力 head の GPU メモリを新しい prompt の prefill 用ワークスペースとして一時的に使います。起動時に head を MTP に bind してから unload し、各リクエストの prompt 読み込み前にも head を unload して prefill path を作り直します。prompt の読み込み後は head を復元してから decode します（`src/program/generate.cpp:933-934, 5574-5597, 12528-12537, 14139-14154`）。

## 使い方

```sh
strata --pack /path/to/pack --native-head-gguf /path/to/model-shard.gguf \
  --stream-token --mtp /path/to/mtp.gguf --spec 4 --expert-cache auto \
  --serve --prefill-head-alias
```

これは構文例です。`--serve` はリクエストから token を受け取るため、通常の `--tokens` は不要です（`src/program/generate.cpp:808-812, 860, 933-934, 2501, 2623, 3168-3172`）。`--native-head-gguf` は `--stream-token` を要求します（同 `src/program/generate.cpp:860, 3455`）。

## 値と既定値

parser は引数なしで `o.prefill_head_alias = true` にし、オプションのない既定値は `false` です。複数回指定しても同じ真偽値を設定します。値の変換や専用の parser validation はありません（`src/program/generate.cpp:766, 2670`）。

## 実行時の動作

有効化すると、起動時に `--serve`、単一 GPU、`--batch` 無効、`--pipeline-windows` 無効、`--short-read 0`、`--expert-cache 1` または `auto`、MTP、ロード済み native output head を確認します。全条件を満たさない場合、標準エラーに `--prefill-head-alias is unavailable: ...` を出し、終了コード 2 で終了します（`src/program/generate.cpp:5576-5589`）。

条件を通ると `mtp.bind(wt, &native_head, ...)` を行って head を unload し、head の byte 数を標準エラーに記録します（`src/program/generate.cpp:5590-5597`）。検証器は unload 済み head の参照を受け取り、この経路では通常の MTP bind を重ねず、検証器の最終 residual を MTP の window 入力に設定します（`src/program/generate.cpp:9167-9174`）。

prefill 用の expert-cache loan は slot 1 から始め、空きメモリと loan byte 数を見ながら chunk 候補 2048、1536、1024、512 tokens の順で選びます。必要な buffer サイズに 512 MiB の余裕を加えて候補を判定し、選択結果と借用量を標準エラーに出します（`src/program/generate.cpp:8711-8730`）。`Prefill::init` には alias 用の `borrow_spill` を渡します（同 `src/program/generate.cpp:8801-8803`）。prefill 内部では借用領域に収まらない配置を所有 buffer 側へ spill する hybrid layout となり、この layout は request 間で変更できません（`src/prefill/prefill.cpp:1444-1448, 1534-1543, 1677-1685`）。

各リクエストでは prompt path の処理前に head を unload し、session/prompt state を reset して prompt path を再構築します。prompt の読み込み後は lent slots を refill してから head をロードし、以前と異なる GPU address に戻った場合は captured verify graph が解放済みメモリを読むのを避けるためエラー終了します（`src/program/generate.cpp:12528-12537, 14135-14154`）。

## 適用条件と副作用

- `--serve` 専用です。単一 GPU 以外、`--batch`、`--pipeline-windows`、`--short-read` の正値、`--expert-cache` の `1`/`auto` 以外、`--mtp` なし、native output head なしでは利用できません（`src/program/generate.cpp:5576-5585`）。
- head の unload/load と prefill path の再初期化がリクエストごとに発生します。head の復元失敗、prompt path 再構築失敗、borrowed slot の refill 失敗はいずれも serve を終了する経路です（`src/program/generate.cpp:12528-12537, 14135-14145`）。
- SYCL port では `Prefill::init` が hybrid borrowed/owned layout を未実装として拒否します。engine 側の上記事前条件に SYCL を除外する判定は見当たらず、該当 build では初期化時に失敗し得ます（`sycl/src/prefill/prefill.cpp:1179-1187`）。

## 出力とエラー

適用条件違反は標準エラーに理由を出して終了コード 2。MTP bind 失敗は標準エラーに内容を出して終了コード 1 です（`src/program/generate.cpp:5586-5592`）。通常時は head を prompt workspace に使うこと、prompt workspace の再構築時間、head 復元時間を標準エラーに出します（同 `src/program/generate.cpp:5596-5597, 12536-12537, 14153-14154`）。prompt path 再構築失敗、slot refill 失敗、head 復元失敗、復元 address の不一致は標準出力に `ERR ...` を出し、終了コード 1 で serve を抜けます（同 `src/program/generate.cpp:12532-12535, 14135-14150`）。

## 根拠

- parser の既定値・フラグ受理・help: `src/program/generate.cpp:766, 933-934, 2670`
- 起動時の制約と head/MTP の bind・unload: `src/program/generate.cpp:5574-5597`
- prefill chunk、loan、初期化: `src/program/generate.cpp:8711-8730, 8801-8803`
- Prefill の hybrid buffer 配置と relayout 制約: `src/prefill/prefill.cpp:1444-1448, 1534-1543, 1677-1685`
- request ごとの unload/rebuild と head の復元・失敗経路: `src/program/generate.cpp:12528-12537, 14135-14154`
- SYCL port の制約: `sycl/src/prefill/prefill.cpp:1179-1187`

この調査ではソース parser と実使用箇所を確認しました。checkout に一致する既存 CLI バイナリや Release artifact は実行・照合していません。
