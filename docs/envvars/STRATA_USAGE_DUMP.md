# `STRATA_USAGE_DUMP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL エンジンの `strata generate` で speculative verify のデバイスプランが数えた routed expert 数を、指定パスへバイナリ trace として書き出す計測用フック。通常の生成計算やトークン選択を切り替える設定ではなく、カウント用デバイス配列の確保・初期化と終了時のファイル出力を追加する。読み取りは `generate.cpp` の speculative decoding 経路だけにあり、サーバー経路では `STRATA_USAGE_DUMP` を読まない。CUDA/HIP 側の読み取りもない。`terminal/tools/collect_profile_traces.py` は既定の `--mode usage` でこの変数を子エンジンに設定し、SYCL の routed trace を収集する。 (`engine/sycl/src/program/generate.cpp:13747-13753,14277-14293`; `terminal/tools/collect_profile_traces.py:7-12,77-86`)

## 値と判定

SYCL の speculative 経路に入った時点で `std::getenv` の返す文字列を読み、そのポインターを後の書き出しに使う。数値や真偽値への変換、空白除去、大文字小文字の判定はない。未設定または空文字列なら無効、空でない任意の文字列はパスとして有効になる。`0`、`false`、`true`、`0anything` も、空でなければその文字列のファイル名として扱われる。CLI 引数や別環境変数による値の上書きはない。 (`engine/sycl/src/program/generate.cpp:13747-13753,14280`)

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `mirror_table_d` が存在する SYCL speculative `generate` 経路 | カウント配列を確保せず、usage trace を出さない | 空でないパス。例: `trace.bin`, `0`, `false`, `0anything` | 空文字列。例: `STRATA_USAGE_DUMP=` |
| `mirror_table_d` がない経路（またはサーバー） | trace なし | 該当なし。値を読んでも配列確保に進まない／サーバーは変数を読まない | 該当なし |

パスの存在・書き込み可否は事前検証されない。出力時に `fopen(path, "wb")` が成功するとファイルを新規作成または切り詰める。 (`engine/sycl/src/program/generate.cpp:13749-13753,14280-14291`)

## 有効になる条件

- SYCL ビルドの `strata generate` で speculative decoding 経路に到達すること。`--spec` の設定などにより speculative verify が実行されない場合、環境変数の読み取り箇所まで進まない。読み取りと初期化は speculative 経路の中にある。 (`engine/sycl/src/program/generate.cpp:13712-13720,13747-13760`)
- その経路で `thits.d_res` が必要になる（コードは未設定なら `--spec needs the device residency table...` を stderr に出して終了コード 2）。さらに `mirror_table_d` が必要で、これは `--stream-experts`、GGUF source、`--expert-cache > 0` の条件下で、VRAM にない experts の pinned mirror が作られ device-readable table が確保・設定された場合に立つ。mirror の候補がなく作成されない場合や mirror 作成に失敗した場合は usage 配列を確保しない。 (`engine/sycl/src/program/generate.cpp:5431-5435,5486-5506,13738-13753`)
- `STRATA_VERIFY_NO_HOST` は変数自体の判定条件ではない。ただし collector の説明では、このデバイスカウント経路は `STRATA_VERIFY_NO_HOST` と併用できる。mirror 不足時に同変数が有効なら別の起動拒否経路がある。 (`terminal/tools/collect_profile_traces.py:9-12`; `engine/sycl/src/program/generate.cpp:5510-5532`)
- `terminal/tools/collect_profile_traces.py` から使う場合、`--mode usage`（既定）が `env["STRATA_USAGE_DUMP"]` を trace パスに設定する。`--mode routing` は環境変数を設定せず `--dump-routing PATH` を付ける。ツールは設定ファイルの `--serve` と `--batch` を引数から除いて子エンジンを起動する。 (`terminal/tools/collect_profile_traces.py:49-56,63-66,77-86`)

## 実行時の詳細

変数は speculative 経路の初期化時に一度読み、`usage_dump` ポインターと `usage_dev` をその実行経路内で保持する。関数内 `static` cache ではないが、カウント配列の確保判定を後から再評価しない。プロセス稼働中に環境値を変更した場合の追随は実装されていない。 (`engine/sycl/src/program/generate.cpp:13747-13753`)

`mirror_table_d && usage_dump && *usage_dump` のとき、層数×expert 数の `int32_t` デバイス配列をゼロ初期化し、`resident_plan_set_mirror` に渡す。SYCL の resident plan は有効な expert ID ごとに対応カウンターを device-scope relaxed atomic で 1 増やす。 (`engine/sycl/src/program/generate.cpp:13749-13753`; `engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2521-2531,2796-2809`)

生成終了時にカウンターを host へコピーし、layer/expert ごとの回数 `c` に対して 16-byte record を `c` 個書く。各 record は `int32 layer, int32 1, int32 expert_id, float 0`（実装上は 3 個の int32 と `wgt[0]`）で、routing weight は保存しない。初期 prompt 経路および speculative ではない通常 token 経路の routing trace ではなく、この device plan を通る speculative verify のカウントである。書き込み順は layer、expert ID 順で、元の routing の時系列順ではない。形式は `make_profile.py` の trace reader が読む `(layer, k, k expert IDs, k weights)` record と一致する。 (`engine/sycl/src/program/generate.cpp:14277-14292`; `engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2521-2531`; `terminal/tools/make_profile.py:47-58`)

## ログと測定値

ファイルを開けた場合のみ stdout に `usage dumped             <path> (<N> routed entries counted on the device)` 相当の行を出す。`fopen` が失敗した場合、同ブロックには警告・エラー出力がなく、usage trace の成功行も出ない。`fwrite` と `fclose` の戻り値も検査しないため、書き込み途中の失敗をこの処理が報告する経路はない。 (`engine/sycl/src/program/generate.cpp:14280-14293`)

この変数による性能測定値は資料にない。`docs/DETAILS.md` は一般の profile 用 trace 作成手段として `--dump-routing` を案内しており、本変数固有の挙動は記載していない。 (`docs/DETAILS.md:84-87`)

## 根拠

- `engine/sycl/src/program/generate.cpp:13712-13760,14277-14293` — speculative 経路、環境読み取り、カウント配列初期化、出力。
- `engine/sycl/src/program/generate.cpp:5431-5506` — mirror table が作られる条件。
- `engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2521-2531,2796-2809` — expert ID の device-side カウントと resident plan への接続。
- `terminal/tools/collect_profile_traces.py:7-12,49-56,63-86` — collector の mode と環境引き渡し。
- `terminal/tools/make_profile.py:47-58`; `docs/DETAILS.md:84-87` — trace record の読み取りと既存資料。
