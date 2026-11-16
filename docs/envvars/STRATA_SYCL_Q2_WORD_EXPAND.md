# `STRATA_SYCL_Q2_WORD_EXPAND`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の grouped expert down 経路で、Q2_0（内部 type `42`）の重みを Q8_1 activation と積和する際に、通常 decoder ではなく word-expand decoder を使うかを制御する。未設定時はこの経路を有効にする。ただし、Battlemage 以外では実行されず、対象経路の条件を満たさない場合も通常の down kernel に進む。環境変数は gate/up や他の量子化形式の計算を切り替えない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:944-961, 3702-3714, 5857-5884`）。

この実装には同じ名前の読み取りが二つある。`q2_word_expand_enabled()` の読み取り結果は実際の kernel 選択に使われる。一方、同ファイルの `g_q2_word_expand` は `env_on()` の結果を保持するが、HEAD 内で参照されていないため、挙動には影響しない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3692, 3933, 5863-5868`）。

## 値と判定

| 読み取り箇所 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `q2_word_expand_enabled()` の実使用判定 | 有効 | 空文字、`1`、`true`、`0anything` 以外の任意文字列 | `0`、`0anything`（先頭文字が `0`） |
| 未使用の `g_q2_word_expand` | 無効 | 先頭文字が `0` 以外で、かつ空でない値（例 `1`, `true`, `2x`） | unset、空文字、`0`, `0anything` |

実使用判定は `std::getenv` で得た文字列の先頭1文字だけを確認し、値が存在して先頭文字が `0` の場合に無効、それ以外は有効とする。空文字は有効、前後空白や大文字小文字、文字列全体の妥当性、数値変換は判定しない。したがって `false` や `no` も有効扱いである。既定値は有効（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3704-3709`）。

未使用の `g_q2_word_expand` は共通 `env_on()` を使い、未設定・空文字・先頭が `0` の値を false、それ以外を true とする。この値は `iq_kernels.dp.cpp` 内で読み取り後に利用されない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3692, 3933`）。

## 有効になる条件

- SYCL の grouped expert down 処理で `L.d_type == 42`（Q2_0）であること。型ごとの dispatch は `STRATA_D_FMTS` から `launch_down<T>` に到達する（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7515-7521`）。
- `STRATA_OLD_IQ_MMVQ` による旧 kernel が無効で、`STRATA_EXPERT_SPLIT` による split multi 経路が無効であること（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3693-3700, 5863-5866`）。これらのフラグも未設定・空文字・先頭 `0` 以外を有効とする。
- `STRATA_DOWN_LANES`（未設定時は `STRATA_EXPERT_LANES` の build-time 値）が 8 になること。値は `atoi` で変換し、4/8/16/32 以外は build-time default に戻る。ここが 8 でなければ通常 down kernel に進む（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:1124-1128, 4240-4249, 5863-5880`）。
- `STRATA_SYCL_Q2_WORD_EXPAND` の実使用判定が有効で、現在の SYCL device が `IntelGpuGen::Battlemage` と判定されること。それ以外の device はこの変数が有効でも helper が false を返し、通常経路に進む（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3704-3714, 5863-5868`）。
- `L.n_embd == 2560 && L.n_ff == 640` かつ `ps_enabled(device)` の場合は、`launch_down_q2_word_expand()` 内で `launch_ps_down()` に分岐して戻るため、word-expand kernel 自体は使われない。`ps_enabled` は `STRATA_PRIVATE_PACKED_REGISTER` が先頭文字 `1` で始まり、B60 main actor / packed weights 条件を満たす Battlemage device で true になる（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4466-4469, 5727-5741`）。

この判定は SYCL 側の down kernel 選択にある。資料上の `Intel Arc` という分類より、実行時の実装条件は Battlemage device 判定である（候補一覧: `docs/SETTINGS.md:371`、実装: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3702-3714`）。

## 実行時の詳細

`q2_word_expand_enabled()` の関数内 `static` が環境値を初回呼び出し時に一度だけ読み、その結果をプロセス内で保持する。device 世代判定は `thread_local` の `(device, bool)` cache で保持され、呼び出し thread ごとに device が変われば再評価する。従って関数の初回呼び出し後にプロセス環境を変更しても、有効/無効判定は更新されない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3704-3714`）。別の未使用 global `g_q2_word_expand` の読み取り時期はグローバル初期化時だが、kernel 選択には関与しない（同: `3933, 5863-5868`）。

条件を満たすと `launch_down_q2_word_expand()` が `native_down_kernel<42, 8, true, true>` を起動する。テンプレート分岐により Q2_0 の各 word を `q2_0_decode8()` で展開し、Q8_1 activation と DP4A の積和を行う。条件を満たさないと `launch_down_lanes<TD>()` または split multi 経路を選ぶ。出力は expert down の各出力行に書かれ、追加の CLI 引数や設定ファイルによる上書きはこの分岐にはない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:946-961, 2167-2176, 2393-2414, 2739-2780, 5727-5741, 5857-5884`）。

## ログと測定値

この環境変数の読み取りや kernel 選択に専用の有効/無効ログ、警告、終了処理はない。選択された kernel の起動後は共通 `check("native_expert_grouped/down")` を通るが、失敗時の具体的な出力は `check` の実装による（呼び出し位置: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7515-7521`）。この変数についての条件付き測定値は `docs/DETAILS.md` に見つからなかった。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3714` — `env_on()`、実使用読み取り、既定値、device 判定と cache。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3933` — 同名変数を読む未使用 global。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:944-961, 1136-1148, 2146-2176, 2384-2421, 2739-2780` — Q2_0 word-expand の計算経路。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4240-4249, 4466-4469, 5727-5741, 5857-5884, 7515-7521` — 相互作用、device/shape 条件、kernel dispatch。
- `docs/SETTINGS.md:371` — 設定一覧の記載。
