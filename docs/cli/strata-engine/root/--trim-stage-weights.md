# `--trim-stage-weights`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--trim-stage-weights` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

複数 GPU の layer split で、stage が担当しない層の dense weights をその GPU にロードしないよう要求します。省いた weights の VRAM は expert cache に使えます。既定では無効です。CUDA/HIP 系の実装と SYCL 実装の parser・判定・ロード経路を確認しました（`src/program/generate.cpp:2611, 3797-3819`、`sycl/src/program/generate.cpp:1914, 2879-2901`）。

## 使い方

2 GPU で layer 27 から後段 GPU に割り当てる明示 split の例です。`/path/to/pack` は実際のモデル pack のパスに置き換えてください。

```sh
strata --serve --pack /path/to/pack --layer-split 27 --trim-stage-weights
```

`--layer-split` は `--serve` とともに使い、明示 split では各 K が後段 GPU の最初の層番号です（`src/program/generate.cpp:2633, 2637, 2970-2974, 2998-3026`）。

## 値と既定値

値や数値範囲はありません。parser はこの引数を受けると bool を `true` にし、初期値は `false` です。同じフラグを複数回指定しても true のままです。専用の値 validation はありません。値を続けて渡す構文ではなく、たとえば `--trim-stage-weights 1` の `1` は未知引数として usage とともに stderr に出て、終了コード 2 になります（`src/program/generate.cpp:664, 2611, 2787-2792`）。

## 実行時の動作

CLI フラグと `STRATA_STAGE_TRIM` のどちらかが有効なら trim 要求になります。環境変数は未設定・空文字・文字列全体が `0` の場合だけ無効で、それ以外の非空文字列は有効です。したがって `false` や `00` も有効扱いです。両者は OR 判定なので、環境変数 `0` で CLI フラグを取り消すことはできません（`src/program/generate.cpp:3802-3806`、SYCL 版 `sycl/src/program/generate.cpp:2884-2888`）。

効果があるのは複数 GPU の layer split が実際に残る場合です。明示 split では各 GPU について担当範囲 `[lb, le)` の外にある `blk.*` weights を skip 集合に加え、名前に `ple` を含む tensor は除外して残します。その範囲で native dense weights の layer range も設定し、縮小した weight pool を確保してロードします（`src/program/generate.cpp:3823-3841, 4306-4339`）。`--mmap-experts` を使う場合、先頭 GPU では routing-aware prefetch 用に全層の `.ffn_gate_inp.weight` も残します（同 `src/program/generate.cpp:3820-3833`）。

`--layer-split auto` では split 判定時点で先頭 GPU の arena がすでに作られているため、先頭 GPU は trim されません。要求がある場合は後続 GPU の weights を split 判定後にロードし、それらを担当範囲に trim します（`src/program/generate.cpp:3807-3819, 4352-4357, 5162-5172`。SYCL 版 `sycl/src/program/generate.cpp:2889-2901, 3447-3452, 3953-3961`）。

## 適用条件と副作用

- layer split なし、単一 GPU、または実行時に split が解除された場合は trim されません。CLI フラグ指定時に `multi_gpu` でなければ `needs a layer split across GPUs (ignored)` を stderr に出します。環境変数だけの要求にはこの警告はありません（`src/program/generate.cpp:3813-3819`）。
- `--layer-split auto --split-skip-if-fits` が CUDA0 だけで実行可能と判定されると split が解除されるため、trim は適用されません（`src/program/generate.cpp:4190-4227`）。
- trim で増えた cache 容量により GPU に載る expert が変わる可能性があり、ソース付属資料は trim なしの場合と出力がわずかに異なる可能性を記しています（`docs/MULTI_GPU.md:205-211`）。このオプションによる性能向上は保証されません。

## 出力とエラー

trim を行う stage のロード時には、担当 GPU と層範囲を stderr に表示します（`src/program/generate.cpp:4310-4318`）。重み arena の確保・ロードに失敗すると、必要量と GPU の空き容量を含む診断を stderr に出してロード関数が失敗し、呼び出し元は終了コード 1 で処理を終えます（同 `src/program/generate.cpp:4322-4333, 4354-4357`）。無効な `--layer-split` 自体は別途検証され、条件を満たさなければ診断を stderr に出して終了コード 2 になります（同 `src/program/generate.cpp:3022-3027`）。

## 根拠

- parser・既定値・help 表示: `src/program/generate.cpp:662-664, 921, 2611`。SYCL parser・help: `sycl/src/program/generate.cpp:625-627, 839, 1914`。
- 環境変数との判定、適用条件、明示 split の範囲選択: `src/program/generate.cpp:3797-3841`。
- 後続 GPU の weight pool とロード・失敗経路: `src/program/generate.cpp:4306-4339, 4352-4357`。auto split 後のロード: 同 `5162-5186`。
- ユーザー向け説明と出力差の注意: `docs/MULTI_GPU.md:205-211`。
- 環境変数の個別文書は [`STRATA_STAGE_TRIM`](../../../STRATA_STAGE_TRIM.md) を参照できます。ただし同文書の調査対象 commit は本書と異なるため、この option 文書の挙動根拠には使っていません。

調査制約: 同一 revision の既存 CLI バイナリの `--help` は確認していません。ソースの parser と usage 表示を照合しました。ビルド、実行、GPU 確認、性能測定、テストは行っていません。
