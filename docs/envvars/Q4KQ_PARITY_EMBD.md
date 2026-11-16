# `Q4KQ_PARITY_EMBD`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`native_expert_parity` 診断プログラムが expert の embedding 幅として使う `H` を上書きする。ソース上の既定値は `2560` で、コメントは Q4-KQ の expert 幅 `512` の指定例を示している。`H` は CPU/GPU の parity 参照計算、合成 expert の生成、GPU kernel の形状・バッファ計算などに使われる。通常の `strata` エンジンやサーバーの設定ではなく、診断実行ファイル内の検査形状を変える値である（CUDA/HIP: `src/kernels/native_expert_parity.cpp:63, 909-910, 971-1012`; SYCL: `sycl/src/kernels/native_expert_parity.cpp:88-90, 102-149, 281-348`; build 条件: `CMakeLists.txt:645-649`, `sycl/CMakeLists.txt:503-508`）。

## 値と判定

両 backend は `main` 冒頭で環境変数が設定されているかを `std::getenv` で調べ、値があれば `std::atoll` の結果を `H` に代入する。未設定時は `2560`。空文字も設定済みとして読み取られ、`atoll("")` は `0` を返す。整数変換の成否や範囲を別途検査せず、clamp もない。`atoll` は先頭の空白と符号を許し、先頭から変換できる数字列を読み、後続の非数字はエラー扱いせず変換を終える。このため、例えば `512xyz` は `512`、`xyz` は `0` になる。数値として不正な入力に対する専用警告や fallback はない（`src/kernels/native_expert_parity.cpp:909`; `sycl/src/kernels/native_expert_parity.cpp:89`）。

| 条件 | unset | 有効になる値の例 | 無効・注意が必要な値の例 |
|---|---|---|---|
| CUDA/HIP または SYCL の `native_expert_parity` | `H=2560` | `512` はコメントにある Q4-KQ 用幅の例。型ごとの block 幅条件を満たす必要がある | 空文字、`xyz`、`0` は `H=0`。`512xyz` は `512`。負数・範囲外値の検査や拒否は実装されない |

ここで「有効」は変換できるという意味であり、任意の値が正しい検査形状になることを保証しない。`native_fmt` は型に応じた block 幅の割り切れを検査するが、正の寸法かどうかは検査しない。形状が block 条件に合わない場合は `native_expert_parity` の処理がその pair/layer を失敗として数える（`src/kernels/cpu/native_expert.cpp:262-287`; `src/kernels/native_expert_parity.cpp:971-975, 1003-1006`; SYCL: `sycl/src/kernels/native_expert_parity.cpp:102-106, 117-119`）。

## 有効になる条件

- CUDA/HIP では `STRATA_ENABLE_CUDA` または `STRATA_ENABLE_HIP` の構成で `native_expert_parity` がビルドされていること。SYCL では `STRATA_NATIVE_EXPERTS` が有効であること（`CMakeLists.txt:645-649`; `sycl/CMakeLists.txt:503-508`）。
- `native_expert_parity` 診断実行ファイルを起動すること。通常の engine/server の読み取り箇所は確認されなかった。
- expert parity の対象型が `H` の値に必要な block 幅条件を満たすこと。合成モードでは `native_fmt` に加え GPU expert kernel の対応型・形状判定も通る必要がある（`src/kernels/native_expert_parity.cpp:971-975`; `sycl/src/kernels/native_expert_parity.cpp:102-106`）。
- 実 GGUF モードでは指定した `H` と `Q4KQ_PARITY_FF` の寸法がファイル内 expert tensor の実寸法に合っている必要がある。該当経路は型から `native_fmt` を作って blob の範囲をコピーするが、ここで tensor の寸法と環境変数の寸法を照合していない（`src/kernels/native_expert_parity.cpp:993-1012`; SYCL: `sycl/src/kernels/native_expert_parity.cpp:110-125`）。

CLI 引数で `H` を上書きする経路や、別の環境変数が `Q4KQ_PARITY_EMBD` より優先する経路はない。`Q4KQ_PARITY_FF` は別の寸法 `FF` を同じ `atoll` 方法で設定し、`H` と合わせて expert 形状を決める（`src/kernels/native_expert_parity.cpp:63, 909-910`; SYCL: `sycl/src/kernels/native_expert_parity.cpp:88-90`）。

## 実行時の詳細

環境値はプロセス起動時、`ggml_cpu_init()` の直後かつ `argv` モードの判定前に一度読み込まれ、グローバル `H` に保存される。実行中の環境変更を再読込する箇所はない。CUDA/HIP の `--synthetic` / `--synthetic-hadamard` と実 GGUF expert 検査では、`H` が参照配列、ランダム入力、GPU/CPU 計算、expert blob のサイズ・配置に伝播する（`src/kernels/native_expert_parity.cpp:903-910, 945-984, 987-1012`）。SYCL でも `main` 内の合成・実 GGUF 検査と各配列・kernel 形状に伝播する（`sycl/src/kernels/native_expert_parity.cpp:74-103, 108-149, 281-348`）。

`H` が不正な寸法である場合の統一された入力エラー処理はない。block 幅条件に合わなければ `native_fmt` が `native experts: expert geometry is not whole blocks` を返す一方、正数チェックがないため、ゼロや負値・過大値を含む不適切な寸法が後続のサイズ計算、確保、量子化や kernel 呼び出しへ進む可能性がある。特に実 GGUF 検査では環境値と実 tensor shape の一致検査が示された経路にないため、任意の override を実モデルに適用した場合の安全な動作は保証されない（`src/kernels/cpu/native_expert.cpp:282-308`; `src/kernels/native_expert_parity.cpp:1003-1012`）。

## ログと測定値

環境変数を読み取ったことや `H` の値を表示する専用ログはない。寸法が block 条件に合わない場合、CUDA/HIP は `layer <番号>: native experts: expert geometry is not whole blocks`、SYCL は合成 pair なら `<pair>: native experts: expert geometry is not whole blocks`、実 GGUF なら同様の `layer` 行を出し、そのケースを失敗に数える（`src/kernels/native_expert_parity.cpp:971-975, 1003-1006`; `sycl/src/kernels/native_expert_parity.cpp:102-106, 117-119`）。検査の最後には `native_expert_parity: %d failures` を出し、失敗数が 0 でなければ終了コード 1、0 なら 0 を返す（CUDA/HIP: `src/kernels/native_expert_parity.cpp:1015-1016`; SYCL: `sycl/src/kernels/native_expert_parity.cpp:359-360`）。`docs/DETAILS.md` にこの環境変数固有の測定値は見つからなかった。

## 根拠

- 読み取り、既定値、実行開始位置: `src/kernels/native_expert_parity.cpp:63, 903-910`; `sycl/src/kernels/native_expert_parity.cpp:74-90`
- `H` の参照・寸法伝播: `src/kernels/native_expert_parity.cpp:66-105, 945-1012`; `sycl/src/kernels/native_expert_parity.cpp:48-65, 126-149, 281-348`
- 型の block 条件と拒否理由: `src/kernels/cpu/native_expert.cpp:262-308`
- 診断ターゲットの build 条件: `CMakeLists.txt:645-649`; `sycl/CMakeLists.txt:503-508`
- 結果表示と終了コード: `src/kernels/native_expert_parity.cpp:1015-1016`; `sycl/src/kernels/native_expert_parity.cpp:359-360`
