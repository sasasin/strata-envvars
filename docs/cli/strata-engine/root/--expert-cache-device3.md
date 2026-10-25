# `--expert-cache-device3`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--expert-cache-device3` |
| 別名 | なし |
| 値 | `N`（非負の expert slot 数）または `auto` |

## 役割

CUDA3 に追加の expert cache を作り、CUDA0 の cache にない expert を GPU 上で計算する helper tier を有効にします。索引上の scope は Terminal CLI の `strata` wrapper ではなく、CMake で生成される推論エンジンの引数です（[`docs/cli/README.md`](../../README.md) の `strata-engine` 節）。

## 使い方

```sh
strata --serve --expert-profile /path/to/profile.bin \
  --expert-cache 4096 \
  --expert-cache-device1 3000 \
  --expert-cache-device2 3000 \
  --expert-cache-device3 auto
```

CUDA3 の tier は CUDA1、CUDA2 の後に有効化します。コマンド例は helper cache に必要な profile と CUDA0 cache も含めています。

## 値と既定値

- `N` は cache に割り当てる expert 数です。未指定時は 0（無効）です。
- `auto` は parser 内で自動 sizing の印を立て、slot 上限を整数の最大値として扱います。実際には CUDA3 の空き VRAM と expert blob の byte 数で収容数が決まります。
- 数値変換は `std::atoi` です。負数は後段 validation で拒否されます。整数として解釈できない文字列は `atoi` により 0 になり、tier が無効になります。空文字も `atoi` では 0 です。
- 同じフラグを複数回指定すると、parser は各回の値を同じ設定欄へ代入するため最後の指定が残ります。
- 値を省くと parser の `next()` が `<option> needs a value` を stderr に出して終了コード 2 で終了します。

## 実行時の動作

Parser は `--expert-cache-device1/2/3` を共通処理し、末尾の数字から tier index を選びます。`auto` は auto flag を立て、slot 上限を `INT_MAX` にします。それ以外は整数変換した値を保存します（`src/program/generate.cpp:2416-2420, 2562-2566`）。

CUDA3 が有効なとき、実行時 validation は CUDA1・CUDA2 も正数であることを要求します。CUDA1 が有効なら、さらに `--expert-profile`、CUDA0 の `--expert-cache`、CPU expert pool が必要です。これらが欠けると stderr に理由を出して終了コード 2 になります（`src/program/generate.cpp:3352-3359, 6666-6670`）。CUDA3 は最大三つの helper cache の一つとして、primary cache や先行 helper が持っていない ranked expert を割り当てられます。複数 helper 時の rank 配分は `--expert-cache-remote-placement` の `stripe` / `layer` に従います（`src/program/generate.cpp:6694-6729`）。

Cache 初期化では CUDA3 の現在の空き VRAM を見て expert を選び、host staging、CUDA memory、stream などの資源を確保します。`auto` は expert ごとの aligned byte 数を加算し、512 MiB の空きを保てなくなるところで選択を止めます。明示 slot 数でも 512 MiB の空きを保てなければ初期化に失敗します。成功時は実際の追加 expert 数と GiB を stderr に出力します。結果は pinned host rows を通じて返されます（`src/core/remote_experts.cpp:135-189, 206-226; src/program/generate.cpp:6736-6746`）。

## 適用条件と副作用

- CUDA3 がビルドで利用可能かつ可視である必要があります。利用可能デバイス数、cache 初期化、VRAM 空き不足などの問題は初期化失敗につながります。CUDA helper の cache を layer split と同時に使う場合は、stage で使っていない GPU が別途必要です（`src/core/remote_experts.cpp:140-154; src/program/generate.cpp:3128-3142`）。
- CUDA tier は順番に有効化する制約があります。CUDA3 だけ、または CUDA1 と CUDA3 だけを指定すると resource parameter validation で拒否されます（`src/program/generate.cpp:3352-3359`）。
- 明示値が実機の空き容量に合わない場合、`RemoteExperts::open` が 512 MiB allowance 不足としてエラーを返し、engine は終了コード 1 で終了します。`auto` でも一つも未割当 expert が 512 MiB allowance 内に入らなければ失敗します（`src/core/remote_experts.cpp:159-184; src/program/generate.cpp:6738-6743`）。
- Cache を開く際は CUDA3 上の GPU cache と CUDA streams/device buffers を確保し、pinned host input/output/metadata staging も確保します。デコード時に当該 GPU が持つ expert の結果を host 経由で戻す処理が加わります（`src/core/remote_experts.cpp:206-237, 264-284`）。
- 起動時に作る cache の容量指定です。`auto` は VRAM と expert サイズで収容 slot 数を決めますが、throughput を測って配分する指定ではありません（sizing 実装 `src/core/remote_experts.cpp:152-169`）。

## 出力とエラー

Parser に値がない場合は stderr の `<option> needs a value` と終了コード 2 です（`src/program/generate.cpp:2418-2420`）。負数、CUDA tier の順序違反、helper cache の依存条件違反は validation で stderr に `invalid sampling or resource parameter` または具体的な条件を出し、終了コード 2 になります（`src/program/generate.cpp:3352-3359, 6666-6670`）。

CUDA3 の cache 初期化エラー（デバイス、空き容量、cache allocation/fill 等）は `strata generate: <理由>` を stderr に出して終了コード 1 になります。成功時は実際の resident 数、GiB、pinned host rows 経由で結果を返す旨を stderr に記録します（`src/core/remote_experts.cpp:140-203; src/program/generate.cpp:6738-6746`）。

## 根拠

- 索引上の option と scope: `docs/cli/README.md:1128-1176`。
- 表示上の値形式 `N|auto`: `src/program/generate.cpp:999-1008`。
- Parser、型変換、既定値・共通引数処理: `src/program/generate.cpp:559-562, 2416-2420, 2562-2566`。
- tier 順序と helper cache の前提条件: `src/program/generate.cpp:3352-3375, 6662-6670`。
- 複数 tier での候補 expert 配分と placement: `src/program/generate.cpp:6678-6729`。
- GPU cache の容量 sizing、512 MiB 条件、allocation/fill と失敗経路: `src/core/remote_experts.cpp:135-203`。
- 適用時の出力と helper 登録: `src/program/generate.cpp:6736-6746, 6781-6782`。
- 同じ parser/action は SYCL 実装にもあります（`sycl/src/program/generate.cpp:1882-1887`）。この調査では実行・build を行っておらず、SYCL runtime 上のデバイス対応や動作確認はしていません。

調査は指定 revision のソースを対象に行いました。CLI `--help` は実行せず、Release artifact、GPU 環境ごとの実挙動、性能は確認していません。
