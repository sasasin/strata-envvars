# `STRATA_SMALL_UNR`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

2 つの小さい BF16/GDN CUDA カーネルで、入力長 2560 のときに使う定数回ロードループを選ぶビットマスクです。bit 0 は BF16 router projection、bit 1 は GDN a/b projection を選びます。通常のループと積和演算の順序を同じに保ちつつ、ロードを複数回分まとめて発行する経路です。対象カーネルの `fast` 条件も満たさない呼び出しには影響しません。

## 値と判定

両カーネルは `std::getenv` の結果が null でなければ `std::atoi` で整数化し、対象ビットを検査します。文字列全体の妥当性検査や範囲検査はありません。`atoi` が整数として読めない文字列（空文字を含む）は 0 となり、数値の後ろの非数値部分は判定に使われません。従って、例えば `3tail` は両ビットを立て、`true` や空文字はどちらも立てません。値を設定した場合は、カード別既定値よりもその値が優先されます。

| 設定値の `atoi` 結果 | BF16 router (bit 0) | GDN a/b (bit 1) |
|---|---:|---:|
| 未設定 | 実行経路に応じた既定値 | 実行経路に応じた既定値 |
| `0`、空文字、数値に読めない文字列 | OFF | OFF |
| `1` | ON | OFF |
| `2` | OFF | ON |
| `3` | ON | ON |
| bit 0/1 以外のみが立つ整数 | OFF | OFF |

整数範囲外の文字列に対する `atoi` の動作は Strata 側で検証・処理していません。

## 有効になる条件

- **CUDA の未設定時**: BF16/GDN の helper はデバイスの compute capability が 12.0 で、かつ `STRATA_SM120_PERF` が既定で有効なら両ビットを既定 ON にします。他の capability、または `STRATA_SM120_PERF=0` なら OFF です。`STRATA_SM120_PERF` は unset または `atoi` が 0 以外なら ON で、判定は helper 内で一度だけキャッシュされます。`STRATA_DEFAULTS=026` は 12.0 の既定スイッチ群を止めるため `STRATA_SMALL_UNR` の未設定既定も OFF にします。
- **HIP の未設定時**: CUDA カーネル helper 自身は `__HIPCC__` 分岐で OFF を返します。ただし Strata の起動時 `apply_arch_defaults()` が AMD gfx12（gfx1200/gfx1201）を判定した場合、`STRATA_GFX12_DEFAULTS` が先頭文字 `0` でなく、かつ `STRATA_DEFAULTS=026` でなければ、未設定の変数を `3` に設定します。従って通常の gfx12 エンジン起動では両ビットが ON になります。`STRATA_GFX12_DEFAULTS=0` は表全体を止め、`STRATA_DEFAULTS=026` はこの変数を含む追加 decode switches を止めます。
- **明示設定**: `STRATA_SMALL_UNR` が存在するだけで既定値より優先します。例えば `STRATA_SMALL_UNR=` は空文字として明示設定され、`atoi` の 0 により両方を OFF にします。gfx12 の起動時既定注入も既存の値を上書きしません。
- 値が有効でも、BF16 経路ではカーネルの `BLOCK_SIZE == 256`、`fast != 0`、`n_in == 2560` が必要です。GDN 経路では `fast != 0` かつ `n == 2560` が必要です。それ以外は通常ループに進みます。別の CLI 引数からこのビットマスクを設定する処理は確認できません。

## 実行時の詳細

BF16 側の `mmvf_fast_bit()` と GDN 側の `gdn_ab_fast()` は、カーネル launch のたびに環境変数を読みます。変数が設定されている場合、その場で `atoi` と対象ビットの判定を行い、変数値自体はキャッシュしません。未設定の場合だけ、CUDA デバイスごとの既定値を `per_dev[64]` に初回使用時キャッシュします。デバイス取得や compute capability 取得に失敗した場合は、そのデバイスで既定 OFF です。HIP 分岐では capability を調べず OFF を返します。

gfx12 AMD の既定値注入は `generate.cpp` の HIP 起動処理が `apply_arch_defaults()` を呼ぶ際に行われます。既存値は維持し、設定したスイッチ名は stderr の `strata: gfx12 (RDNA4): ... exact speed switches on by default ...` 行に列挙されます。CUDA 側の `STRATA_SMALL_UNR` の値 parse には専用ログや無効値警告がありません。

## 根拠

- `include/strata/core/bw_dense_defaults.hpp:18-19`: unset 時の bit 定義と sm_120 / `STRATA_DEFAULTS=026` に基づく既定値。
- `include/strata/core/sm120_series.hpp:30-40,58-59`: `STRATA_SM120_PERF` の一回限りの判定と compute capability 12.0 条件。
- `src/kernels/cuda/native_bf16.cu:340-358`: bit 0 の読み取り、明示値優先、CUDA device 既定値のキャッシュと HIP の OFF 分岐。
- `src/kernels/cuda/native_bf16.cu:72-83,413-418,441-467,478-490`: BF16 カーネル側の fast 条件と launch 経路。
- `src/kernels/cuda/verify_kernels.cu:98-138,1184-1203,1204-1219`: bit 1 の読み取り、適用条件、GDN kernel launch。
- `src/core/arch_defaults.cpp:27-61,185-191,221-230,257-265`: gfx12 の既定値 `3`、既定値を保つ設定処理、ユーザー設定優先、stderr の既定スイッチ報告。
- `src/program/generate.cpp:3702-3719`: HIP 起動時に `apply_arch_defaults()` を呼ぶ位置。
- `docs/DETAILS.md` にはこの変数の説明・測定条件を確認できなかったため、性能値は記載していません。
