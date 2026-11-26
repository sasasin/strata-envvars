# `STRATA_NO_NORM_ROPE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は、native RoPE 経路で QSA の重み付き RMSNorm と RoPE を一つのカーネルにまとめる処理を止める。また、入力と出力が同じバッファである native RoPE の起動幅 32 スレッド最適化も止める。変数自体は `native_rope_enabled()` を有効にせず、通常の RoPE を native RoPE に切り替えない。CUDA/HIP と SYCL の各 `native_norm_rope_usable()` が値を読み、利用可否を返す（`engine/src/kernels/cuda/native_rope.cu:180-192,213-214`; `engine/sycl/src/kernels/cuda/native_rope.dp.cpp:230-242,262-265`）。

## 値と判定

両実装とも `std::getenv()` の結果を関数内 `static const bool` に一度だけ保存する。変数が設定され、かつ先頭文字が NUL でも `'0'` でもないとき、この変数は fused 処理を無効にする。文字列の数値変換や全体比較はしない。大文字小文字は判定せず、先頭の空白は `'0'` ではないため無効化側に入る。`0anything` や `0.5` は先頭が `'0'` なので無効化しない（同 `native_rope.cu:181-190`; 同 `native_rope.dp.cpp:231-240`）。

| ビルド条件 | unset | `STRATA_NO_NORM_ROPE` が無効化しない値 | 同変数が無効化する値 |
|---|---|---|---|
| `__HIPCC__` 以外 | fused 可 | 空文字、`0`、`0anything`、`0.5` | `1`、`true`、`false`、` 0`、`00` など先頭が `'0'` 以外の非空値 |
| `__HIPCC__` 定義あり | `STRATA_NORM_ROPE` が unset / 空 / 先頭 `0` なら fused 不可 | 同左条件を満たす値 | 左欄にかかわらず、先頭が `'0'` 以外の非空値 |

HIP ビルドでは、対象変数が無効化しない場合に限り `STRATA_NORM_ROPE` も同じ先頭文字規則で調べ、非空で先頭が `'0'` 以外の値が設定されているときだけ利用可にする。HIP 以外のプリプロセッサ分岐では `STRATA_NORM_ROPE` を読まず利用可とする（`engine/src/kernels/cuda/native_rope.cu:181-190`; SYCL 側実装も同じ分岐: `engine/sycl/src/kernels/cuda/native_rope.dp.cpp:231-240`）。

## 有効になる条件

- `native_norm_rope_usable()` が true になるのは、`head_dim` が 128 または 256 で、`n_rot == 64` の場合だけ（`engine/src/kernels/cuda/native_rope.cu:191`; `engine/sycl/src/kernels/cuda/native_rope.dp.cpp:241`）。
- 通常の QSA forward / verify の融合には native QSA と native RoPE の両方が有効である必要がある。初期値では native RoPE は無効で、CLI の `--native-rope` または `--native` preset がそれぞれ有効化する（`engine/src/program/generate.cpp:802,3922,3926,5160-5164,6123`; SYCL 側 `engine/sycl/src/program/generate.cpp:486,1961,2592-2596,3238`; 判定箇所 `engine/src/core/verify.cpp:2037-2044`）。
- MTP の K / Q 融合経路も native RoPE と上記の利用可判定を必要とする。K は `T == 1` の場合だけ fused カーネルに進み、複数 token では RMSNorm と RoPE を別々に行う（`engine/src/core/mtp.cpp:1259-1269,2406-2418`; Q 経路 `engine/src/core/mtp.cpp:1324-1339,2457-2477`。SYCL 側の K と Q: `engine/sycl/src/core/mtp.cpp:963-973,1028-1048`）。
- HIP ビルドは `STRATA_NO_NORM_ROPE` が無効化しなくても `STRATA_NORM_ROPE` による明示的な opt-in が必要。対象ソースは `__HIPCC__` で分岐する（`engine/src/kernels/cuda/native_rope.cu:184-189`）。
- `native_rope_apply()` の通常の RoPE 計算はこの変数だけでは停止しない。`x == out`、回転幅 64、利用可能判定 true の場合に選ぶ 32 スレッド起動を抑え、128 スレッド起動にする。`x != out` などではこの利用判定は起動幅に影響しない（`engine/src/kernels/cuda/native_rope.cu:213-220`; SYCL 側 `engine/sycl/src/kernels/cuda/native_rope.dp.cpp:262-265`）。

## 実行時の詳細

環境値は `native_norm_rope_usable()` の初回呼び出し時に関数ローカル static として評価・キャッシュされる。したがって、プロセス起動後に環境を書き換えても再評価されない。static 初期化後は呼び出しごとに引数の head dimension と回転幅を確認する（`engine/src/kernels/cuda/native_rope.cu:180-192`; `engine/sycl/src/kernels/cuda/native_rope.dp.cpp:230-242`）。

利用可なら QSA 経路は `native_qsa_rms_norm_rope()` を呼び、不可なら RMSNorm の後に native RoPE（native RoPE が有効な場合）または `rope_neox_apply()` を呼ぶ。つまり対象変数による fallback は二つの演算を個別に実行すること。環境値から出力の差や性能差はこのコードだけでは断定しない（`engine/src/core/verify.cpp:2028-2044`; MTP K `engine/src/core/mtp.cpp:1259-1269`; SYCL verify `engine/sycl/src/core/verify.cpp:1328-1338`）。

## ログと測定値

この変数の値や fused 可否を報告するログ、または無効値時のエラー処理は、確認した読み取り・呼び出し経路にはない。無効化した場合の動作は上記の個別演算への分岐である。条件付きの測定値を示す Strata 資料は確認できなかった。

## 根拠

- `engine/src/kernels/cuda/native_rope.cu:180-192,213-220` — CUDA/HIP の値判定、HIP 分岐、利用条件と native RoPE 起動幅。
- `engine/sycl/src/kernels/cuda/native_rope.dp.cpp:230-242,262-265` — SYCL 実装の同等判定と起動幅。
- `engine/src/core/verify.cpp:2028-2044`、`engine/sycl/src/core/verify.cpp:1328-1338` — QSA forward/verify の fused と fallback 経路。
- `engine/src/core/mtp.cpp:1256-1269,1324-1339,2406-2418,2457-2477`、`engine/sycl/src/core/mtp.cpp:960-973,1028-1048` — MTP における K/Q 処理と条件。
- `engine/src/program/generate.cpp:802,3922,3926,5160-5164,6123`、`engine/sycl/src/program/generate.cpp:486,1961,2592-2596,3238` — native RoPE の CLI 設定とカーネルへの有効状態設定。
