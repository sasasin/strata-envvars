# `STRATA_ONE_TOKEN_COMMIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

一トークンの verify window では、window の処理中に GDN convolution history と recurrence state を進め、後続の `Verifier::commit` が commit graph をもう一度実行しないようにする制御です。CUDA と SYCL では既定で有効、HIP では既定で無効です。HIP で有効にすると同じ一トークン経路を選びます。これは verify 内の処理を切り替えるもので、CLI 引数を追加したり、commit 数を指定したりするものではありません（`engine/src/core/verify.cpp:447-451,553-567,1948-2007,4527-4584`; `engine/sycl/src/core/verify.cpp:265-292,1045-1047,1267-1269,3171-3176`）。

## 値と判定

値は `std::getenv` で取得し、設定されている場合は `std::atoi(v) != 0` で判定します。文字列全体の検証ではありません。`atoi` が先頭の整数部分を読めるとその値で判定し、整数に変換できない先頭なら 0 になります。したがって空文字、`true`、`false`、`0anything` は無効、`1`、`2`、`-1`、`1anything` は有効です。先頭空白や符号は `atoi` の変換規則に従います。値域の検査や clamp はなく、`int` に収まらない数値文字列については `atoi` の結果を保証できません。大文字小文字を比較する判定はありません。

| 実装 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA engine と SYCL | 有効（`v == nullptr`） | `1`, `2`, `-1`, `1anything` | `0`, `0anything`, 空文字, `true`, `false` |
| HIP engine | 無効（`v == nullptr`） | `1`, `2`, `-1`, `1anything` | `0`, `0anything`, 空文字, `true`, `false` |

CUDA/HIP の区別は `STRATA_USE_HIP` のビルド分岐です。SYCL の実装は `STRATA_USE_HIP` が定義された分岐ではなく、CUDA と同じ未設定時の既定値を持ちます（`engine/src/core/verify.cpp:553-567`; `engine/sycl/src/core/verify.cpp:282-292`）。

## 有効になる条件

- CUDA/HIP engine または SYCL verifier を使うこと。環境変数の判定実装はこれらの verify 実装内にあります（`engine/src/core/verify.cpp:553-567`; `engine/sycl/src/core/verify.cpp:282-292`）。
- 処理対象が一トークンの window であること（`T == 1` または `last_t_ == 1`）。複数トークンの window では self-commit 経路に入りません（`engine/src/core/verify.cpp:1488,4537`; `engine/sycl/src/core/verify.cpp:1046-1047,3171`）。
- CUDA engine では `always_publish_` が偽で、`STRATA_QFUSE` が有効でないこと。さらに window 側では `batch_rec_` でないことが必要です（`engine/src/core/verify.cpp:1488,4537-4540`）。
- SYCL では `STRATA_QFUSE` が有効でなく、`batch_rec_` でなく、`self_commit_off_` が偽であることが window 側の条件です。serial と pipelined の commit 側も `self_commit_off_` を確認します（`engine/sycl/src/core/verify.cpp:135,1046-1047,3171-3173,4530`）。
- HIP でこの機能を使うには、上記の条件に加えて環境変数を設定し、`atoi` の結果を非ゼロにする必要があります。`STRATA_ONE_TOKEN_COMMIT=0` も無効です（`engine/src/core/verify.cpp:553-559`）。

CLI 引数による値の上書きはこの変数の読み取り関数にはありません。`STRATA_QFUSE` は併用時に self-commit を止めます。`STRATA_COMMIT_SYNC` は非同期 commit の選択に関係しますが、self-commit の有効判定には使われません（`engine/src/core/verify.cpp:320,4524-4525,4537-4540`; `engine/sycl/src/core/verify.cpp:135,3161-3162`）。

## 実行時の詳細

`one_token_self_commit()` 内の関数ローカル `static const bool` が初回呼び出し時に環境を読み、そのプロセス内で結果を保持します。起動後に環境値を変更しても再評価されません。呼び出しは window 作成時と commit 時にあります（`engine/src/core/verify.cpp:553-567,1488,4537,4592`; `engine/sycl/src/core/verify.cpp:282-292,1046-1047,3171,4530`）。

有効な一トークン window では、window の GDN convolution と recurrence が state を進めるよう `self_commit` を渡します。後続の `Verifier::commit` は commit graph の起動を省略します。CUDA の通常経路では `always_publish_` と `STRATA_QFUSE` の条件も確認し、SYCL では `self_commit_off_` が立っている場合に commit graph を省略しません（`engine/src/core/verify.cpp:1488,1948-1956,2005-2007,4532-4540`; `engine/sycl/src/core/verify.cpp:1046-1047,1267-1269,3171-3176`）。

`STRATA_PIPELINE_DUMP` が設定されている SYCL の pipelined commit は stderr に `strata commit: n_keep=%d T=%d pos0=%lld self_skip=%d` を出します。ただし `self_skip` の値は window の長さと環境判定だけから作られ、`self_commit_off_` を含む実際の skip 条件すべては表しません。この変数自体についての有効化ログや警告はありません（`engine/sycl/src/core/verify.cpp:4493-4502,4530-4541`）。

条件を満たさず commit graph を実行する経路では、起動失敗時にエラー文字列 `verify: commit launch: ...` が返ります。CUDA はさらに同期失敗時 `verify: commit: ...`、commit event の登録失敗時 `verify: commit event: ...` を返します。これらは commit 処理一般の失敗経路であり、この環境変数専用のエラーではありません（`engine/src/core/verify.cpp:4561-4575`; `engine/sycl/src/core/verify.cpp:3174-3214`）。

## ログと測定値

`docs/DETAILS.md` にこの変数の説明や、この切り替えに関する測定条件付きの数値は見つかりませんでした。ソースコメントは一トークン window が state を進めるため commit graph を省く設計を説明しています。性能向上や生成結果の一般的な同一性は、この調査では断定しません（`engine/src/core/verify.cpp:447-451`; `engine/sycl/src/core/verify.cpp:265-269,4525-4529`）。

## 根拠

- 値の読み取り、backend ごとの既定値とキャッシュ: `engine/src/core/verify.cpp:553-567`; `engine/sycl/src/core/verify.cpp:282-292`
- CUDA window 内の判定と GDN state 更新: `engine/src/core/verify.cpp:1488,1948-1956,2005-2007`
- CUDA commit graph の省略と条件: `engine/src/core/verify.cpp:4527-4584,4587-4594`
- SYCL window 内の判定と GDN state 更新: `engine/sycl/src/core/verify.cpp:1045-1047,1267-1269`
- SYCL commit と pipelined commit の省略: `engine/sycl/src/core/verify.cpp:3164-3193,4493-4541`
- 設計資料との照合: `docs/DETAILS.md` に当該変数の記述なし。
