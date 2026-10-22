# `STRATA_EXPDEC_D20`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。対象ソースツリーは `main` で、調査開始時の作業ツリーは clean。外部ライブラリの環境変数は対象外。

## 役割

CUDA の native expert grouped 計算で、EXPDEC の down カーネルを IQ4_NL にも使えるようにする補助スイッチです。この変数は IQ4_NL down の可否だけを指定します。EXPDEC 自体と down 側を有効にする `STRATA_EXPDEC`、`STRATA_EXPDEC_DOWN` が有効でなければ、この変数を設定しても IQ4_NL down は EXPDEC に切り替わりません。

## 値と判定

初期化時に `env_int_or("STRATA_EXPDEC_D20", 0)` で読み、整数値として 0 かどうかではなく、後段で C++ の真偽値として扱います。`env_int_or` は変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi` の結果を返します。

| 環境変数の値 | 読み取り後の値 | D20 条件での扱い |
|---|---:|---|
| 未設定 | 0 | 無効 |
| 空文字 | 0 | 無効 |
| `0`、`0abc`、数字で始まらない文字列 | 0 | 無効 |
| `1`、`2`、`-1`、` 1`、`1abc` | 非0 | 有効 |

`atoi` は文字列全体の妥当性を検証しません。先頭の空白の後から整数として読める部分を変換し、数字を読めなければ 0 になります。大文字小文字の判定はありません。値を読み取るのは `iq_kernels.cu` のグローバル初期化時で、以後は `g_expdec_d20` に保持されます。通常の engine 経路では起動後の環境変更を再読しません。

## 有効になる条件

IQ4_NL down で EXPDEC を実行するには、すべての条件を満たす必要があります。

- `STRATA_EXPDEC` が有効である。値判定は `env_on` に従い、未設定・空文字・`0` で始まる値は無効、それ以外の非空値は有効。
- `STRATA_EXPDEC_DOWN` が非0として読み取られている。未設定時の既定値は 0。
- down の型 `L.d_type` が 20（IQ4_NL）であり、`STRATA_EXPDEC_D20` の読み取り結果が非0。
- `L.n_ff == 32 * ED_HB`（`ED_HB` は 20 なので `n_ff == 640`）、`L.n_embd` が正で 128 の倍数。
- 旧カーネル指定 `STRATA_OLD_IQ_MMVQ` が有効でない。旧カーネル指定時は EXPDEC 経路が使われず、既定 down カーネルに進む。

AMD の EXP layout down 経路で型 20 を含む AMD 専用カーネルが選ばれる場合は、その分岐が EXPDEC 判定より先に down を処理します。その呼び出しでは D20 は使われません。

down の型が 42（Q2_0）の場合は D20 条件を使いません。`STRATA_EXPDEC_DOWN` が有効で形状条件を満たせば D20 の値とは独立に EXPDEC down の対象です。条件が揃わない場合、呼び出し元は `launch_down` の既定カーネルを選びます。

## 実行時の詳細

`native_expert_grouped` の CUDA 経路は down の前に `expdec_down(...)` を呼びます。関数は EXPDEC モード、旧カーネル指定、down の有効化とレイアウト条件を確認し、条件を満たすと IQ4_NL (`d_type == 20`) 用の `expdec_down_kernel<20,...>` を launch します。条件を満たさない場合は `false` を返し、呼び出し元が通常の型別 `launch_down` に進みます。D20 は gate/up カーネルの選択には影響しません。

EXPDEC モードが有効で旧カーネル指定が無効のとき、down 型・形状が対象外なら初回に stderr へ `strata expdec: CUDA%d down type %d (n_embd %lld, n_ff %lld) not covered: the default kernel runs` を出します。適用時は `strata expdec: CUDA%d down type %d: expdec_down_kernel ...` の形式で launch 条件を出します。EXPDEC モードが無効、または旧カーネル指定で EXPDEC 関数を早期 return した場合は、この判定ログは出ません。ログは D20 の真偽だけを示すものではなく、down の型と形状に対する EXPDEC 適用結果を示します。

`expdec_bench` は `native_expert_set_expdec_params` を介して D20 設定を上書きできます。ベンチの `dec:x0` / `dec:x1` がこの値を指定し、フィールド省略時は起動時に読んだ環境設定を使います。この上書きは同ベンチの選択機能です。

## 文書・測定値との照合

`docs/EXPERTDEC.md` は IQ4_NL down を `STRATA_EXPDEC_D20=1` の場合の対象とし、down 全体の切替には `STRATA_EXPDEC_DOWN=1` が必要と説明しています。コードの条件分岐と一致します。同資料の micro-bench では IQ4_NL down が 0.95–1.07x で「no gain」と記載され、既定カーネルを維持する理由になっています。資料の測定条件は RTX 2080 Ti / RTX 3060 上の `expdec_bench`、合成 expert blob、T=1–4 の範囲です（`docs/EXPERTDEC.md:55-70,85-87`）。この値は記載条件下のベンチ結果で、別の機器や実行条件での性能を示すものではありません。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:3273-3276` — `env_on` の判定規則。
- `src/kernels/cuda/iq_kernels.cu:3933-3961` — `env_int_or`、D20 の既定値 0、EXPDEC down のレイアウト条件。
- `src/kernels/cuda/iq_kernels.cu:4063-4070,5200-5205,5253-5268` — down カーネル選択、AMD 経路、既定カーネルへの fallback。
- `src/kernels/cuda/iq_kernels.cu:5022-5042` — ベンチ用 setter と現在値の取得。
- `src/kernels/expdec_bench.cpp:75-107` — `dec:x0` / `dec:x1` の入力検証と設定反映。
- `docs/EXPERTDEC.md:16-17,31-42,55-70,85-87` — 対象形式、相互条件、ログ、ベンチ結果。
